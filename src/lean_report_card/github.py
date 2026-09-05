from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from urllib.parse import quote, urlparse

import httpx

from lean_report_card.config import Settings

_OWNER_REPO = re.compile(r"^[A-Za-z0-9_.-]+$")
_SAFE_REF = re.compile(r"^[A-Za-z0-9_./@+-]+$")
_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


class RepositoryInputError(ValueError):
    pass


class RepositoryLookupError(RuntimeError):
    pass


@dataclass(frozen=True)
class ParsedRepository:
    owner: str
    name: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def canonical_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}.git"


@dataclass(frozen=True)
class ResolvedRepository:
    parsed: ParsedRepository
    commit_sha: str
    requested_ref: str | None
    default_branch: str | None
    size_kib: int | None


def parse_github_repository(value: str) -> ParsedRepository:
    raw = value.strip()
    if raw.startswith("github.com/"):
        raw = f"https://{raw}"
    if raw.count("/") == 1 and "://" not in raw:
        raw = f"https://github.com/{raw}"

    parsed = urlparse(raw)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise RepositoryInputError("Only public HTTPS GitHub repositories are accepted.")
    if parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:
        raise RepositoryInputError("Repository URLs may not contain credentials, ports or queries.")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise RepositoryInputError("Use a repository URL of the form github.com/owner/name.")
    owner, name = parts
    name = name.removesuffix(".git")
    if not owner or not name or not _OWNER_REPO.fullmatch(owner) or not _OWNER_REPO.fullmatch(name):
        raise RepositoryInputError("The GitHub owner or repository name is invalid.")
    return ParsedRepository(owner=owner, name=name)


def validate_ref(ref: str | None) -> str | None:
    if ref is None or not ref.strip():
        return None
    normalized = ref.strip()
    if (
        len(normalized) > 250
        or not _SAFE_REF.fullmatch(normalized)
        or ".." in normalized
        or "//" in normalized
        or normalized.startswith(("-", "/"))
        or normalized.endswith(("/", "."))
    ):
        raise RepositoryInputError("The requested Git ref is invalid.")
    return normalized


async def _git_ls_remote(url: str, ref: str | None) -> str:
    target = ref or "HEAD"
    process = await asyncio.create_subprocess_exec(
        "git",
        "ls-remote",
        "--exit-code",
        url,
        target,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=25)
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise RepositoryLookupError("Timed out resolving the repository ref.") from exc
    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RepositoryLookupError(message or "Unable to resolve the repository ref.")
    lines = stdout.decode("utf-8", errors="replace").splitlines()
    if not lines:
        raise RepositoryLookupError("Git returned no matching repository ref.")
    sha = lines[0].split()[0]
    if not _SHA.fullmatch(sha):
        raise RepositoryLookupError("GitHub returned an invalid commit hash.")
    return sha.lower()


async def resolve_repository(
    repository: str,
    ref: str | None,
    settings: Settings,
) -> ResolvedRepository:
    parsed = parse_github_repository(repository)
    safe_ref = validate_ref(ref)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "lean-report-card/0.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    default_branch: str | None = None
    size_kib: int | None = None
    sha: str | None = safe_ref.lower() if safe_ref and _SHA.fullmatch(safe_ref) else None

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False, headers=headers) as client:
            repo_response = await client.get(
                f"https://api.github.com/repos/{parsed.owner}/{parsed.name}"
            )
            if repo_response.status_code == 404:
                raise RepositoryLookupError("GitHub repository not found or not public.")
            repo_response.raise_for_status()
            payload = repo_response.json()
            if payload.get("private"):
                raise RepositoryLookupError("Private repositories are not supported.")
            default_branch = payload.get("default_branch")
            raw_size = payload.get("size")
            size_kib = int(raw_size) if isinstance(raw_size, int) else None
            if sha is None:
                commit_ref = safe_ref or default_branch or "HEAD"
                encoded_ref = quote(commit_ref, safe="")
                commit_response = await client.get(
                    "https://api.github.com/repos/"
                    f"{parsed.owner}/{parsed.name}/commits/{encoded_ref}"
                )
                commit_response.raise_for_status()
                candidate = str(commit_response.json().get("sha", ""))
                if _SHA.fullmatch(candidate):
                    sha = candidate.lower()
    except RepositoryLookupError:
        raise
    except (httpx.HTTPError, ValueError, TypeError):
        # Public API rate limits or transient API failures should not prevent a scan.
        # The strict URL parser above keeps this fallback away from arbitrary hosts.
        pass

    if sha is None:
        sha = await _git_ls_remote(parsed.canonical_url, safe_ref)

    return ResolvedRepository(
        parsed=parsed,
        commit_sha=sha,
        requested_ref=safe_ref,
        default_branch=default_branch,
        size_kib=size_kib,
    )
