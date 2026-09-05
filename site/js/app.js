const OWNER_REPO = /^[A-Za-z0-9_.-]+$/;
const PAGE_SIZE = 20;

let reportIndex = [];
let pendingSubmission = null;

function parseGithubRepository(value) {
  let raw = value.trim();
  if (raw.startsWith("github.com/")) raw = `https://${raw}`;
  if ((raw.match(/\//g) || []).length === 1 && !raw.includes("://")) {
    raw = `https://github.com/${raw}`;
  }
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error("Enter a GitHub repository URL.");
  }
  if (parsed.protocol !== "https:" || parsed.hostname !== "github.com") {
    throw new Error("Only public HTTPS GitHub repositories are accepted.");
  }
  if (parsed.username || parsed.password || parsed.port) {
    throw new Error("Repository URLs may not contain credentials or ports.");
  }
  const parts = parsed.pathname.split("/").filter(Boolean);
  if (parts.length !== 2) {
    throw new Error("Use a repository URL of the form github.com/owner/name.");
  }
  const owner = parts[0];
  const name = parts[1].replace(/\.git$/, "");
  if (!OWNER_REPO.test(owner) || !OWNER_REPO.test(name)) {
    throw new Error("The GitHub owner or repository name is invalid.");
  }
  return { owner, name, slug: `${owner}/${name}`, url: `https://github.com/${owner}/${name}` };
}

function capture(event, properties) {
  if (!window.posthog || typeof window.posthog.capture !== "function") {
    return Promise.resolve(false);
  }
  window.posthog.capture(event, { $process_person_profile: false, ...properties });
  return Promise.resolve(true);
}

function setHidden(el, hidden) {
  if (el) el.hidden = hidden;
}

function showSubmitError(message) {
  const el = document.getElementById("score-error");
  el.textContent = message;
  setHidden(el, false);
  document.getElementById("repository").focus();
}

function clearSubmitError() {
  const el = document.getElementById("score-error");
  el.textContent = "";
  setHidden(el, true);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function params() {
  return new URLSearchParams(window.location.search);
}

function findEntry(slug) {
  return reportIndex.find((item) => item.slug.toLowerCase() === slug.toLowerCase()) || null;
}

function formatDate(iso) {
  if (!iso) return "—";
  return iso.slice(0, 10);
}

function renderList(page) {
  const total = reportIndex.length;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const current = Math.min(Math.max(page, 1), pageCount);
  const start = (current - 1) * PAGE_SIZE;
  const slice = reportIndex.slice(start, start + PAGE_SIZE);
  const list = document.getElementById("repo-list");
  list.innerHTML = slice
    .map((entry) => {
      const gradeClass = `grade-${escapeHtml((entry.grade || "f").toLowerCase())}`;
      return `<a class="repo-row" href="?repo=${encodeURIComponent(entry.slug)}">
        <span class="repo-grade ${gradeClass}">${escapeHtml(entry.grade || "—")}</span>
        <span class="repo-score">${entry.score == null ? "—" : escapeHtml(entry.score)}</span>
        <span class="repo-slug">${escapeHtml(entry.slug)}</span>
        <span class="repo-summary">${escapeHtml(entry.summary || "")}</span>
        <span class="repo-date">${escapeHtml(formatDate(entry.updated_at))}</span>
      </a>`;
    })
    .join("");

  const nav = document.getElementById("pagination");
  const links = [];
  if (current > 1) links.push(`<a href="?page=${current - 1}">Previous</a>`);
  for (let n = 1; n <= pageCount; n += 1) {
    links.push(
      n === current ? `<span class="current" aria-current="page">${n}</span>` : `<a href="?page=${n}">${n}</a>`,
    );
  }
  if (current < pageCount) links.push(`<a href="?page=${current + 1}">Next</a>`);
  nav.innerHTML = links.join("");
  document.getElementById("report-count").textContent = String(total);
}

function renderDetails(details) {
  if (!details || typeof details !== "object") return "";
  const rows = Object.entries(details)
    .map(
      ([key, value]) =>
        `<div><dt>${escapeHtml(key.replaceAll("_", " "))}</dt><dd>${escapeHtml(value)}</dd></div>`,
    )
    .join("");
  return `<details><summary>Measurements</summary><dl>${rows}</dl></details>`;
}

function renderReport(report, entry) {
  const checks = (report.checks || [])
    .map(
      (check) => `
      <article class="check-card">
        <div class="check-topline">
          <span class="status status-${escapeHtml(check.status)}">${escapeHtml(check.status)}</span>
          <strong>${escapeHtml(check.score)}/${escapeHtml(check.maximum)}</strong>
        </div>
        <h3>${escapeHtml(check.title)}</h3>
        <p>${escapeHtml(check.summary)}</p>
        ${renderDetails(check.details)}
      </article>`,
    )
    .join("");
  const repo = report.repository || {};
  const slug = `${repo.owner || ""}/${repo.name || ""}`;
  const caveat =
    report.caveat ||
    (entry && !entry.file
      ? "This line is from the published index. A full check breakdown appears when the analyzer writes a JSON file for the repository."
      : "");
  return `
    <a class="back-link" href="./">← Index</a>
    <section class="report-hero">
      <div>
        <p class="eyebrow">${escapeHtml(report.status || "published")}</p>
        <h2>${escapeHtml(slug)}</h2>
        <p class="lede"><a href="${escapeHtml(repo.url || "#")}">Repository</a>${
          repo.commit_sha ? ` at <code>${escapeHtml(repo.commit_sha)}</code>` : ""
        }</p>
      </div>
      <div class="grade-card">
        <span class="grade">${escapeHtml(report.grade || "…")}</span>
        <span class="score">${report.score == null ? "pending" : `${escapeHtml(report.score)}/100`}</span>
      </div>
    </section>
    <div class="meta-grid">
      <div><span>Analyzer</span><strong>${escapeHtml(report.analyzer_version || "index")}</strong></div>
      <div><span>Analyzed</span><strong>${escapeHtml(formatDate(report.analyzed_at || entry?.updated_at))}</strong></div>
      <div><span>Summary</span><strong>${escapeHtml(entry?.summary || "—")}</strong></div>
    </div>
    ${checks ? `<div class="check-grid">${checks}</div>` : ""}
    <p class="caveat">${escapeHtml(caveat)}</p>
  `;
}

function reportFromIndex(entry) {
  const [owner, name] = entry.slug.split("/");
  return {
    status: "published",
    grade: entry.grade,
    score: entry.score,
    analyzer_version: "index",
    analyzed_at: entry.updated_at,
    repository: { owner, name, url: entry.url, commit_sha: "" },
    checks: [],
    caveat: "",
  };
}

async function loadFullReport(entry) {
  if (!entry.file) return reportFromIndex(entry);
  const report = await fetch(`reports/${entry.file}`, { cache: "no-store" }).then((response) => {
    if (!response.ok) throw new Error("The published report could not be loaded.");
    return response.json();
  });
  return report;
}

function showResult(html) {
  const result = document.getElementById("result");
  result.innerHTML = html;
  setHidden(result, false);
}

function openContact() {
  setHidden(document.getElementById("contact-panel"), false);
  setHidden(document.getElementById("contact-backdrop"), false);
  document.getElementById("contact-open").setAttribute("aria-expanded", "true");
}

function closeContact() {
  setHidden(document.getElementById("contact-panel"), true);
  setHidden(document.getElementById("contact-backdrop"), true);
  document.getElementById("contact-open").setAttribute("aria-expanded", "false");
}

async function queueScan(parsed, email, rescan, publish) {
  clearSubmitError();
  await capture("score_requested", {
    repository: parsed.url,
    repository_slug: parsed.slug,
    email,
    rescan,
    publish,
  });
  document.getElementById("score-form").hidden = true;
  setHidden(document.getElementById("rescan-confirm"), true);
  setHidden(document.getElementById("score-queued"), false);
}

function askRescan(parsed, email, entry, publish) {
  pendingSubmission = { parsed, email, entry, publish };
  const box = document.getElementById("rescan-confirm");
  box.innerHTML = `
    <p><a href="?repo=${encodeURIComponent(entry.slug)}">${escapeHtml(entry.slug)}</a>
    already has a published report (${escapeHtml(entry.grade)} · ${escapeHtml(entry.score)}).
    Do you want to trigger another scan?</p>
    <div class="rescan-actions">
      <a href="?repo=${encodeURIComponent(entry.slug)}">View report</a>
      <button type="button" id="confirm-rescan">Scan again</button>
    </div>`;
  setHidden(box, false);
  document.getElementById("confirm-rescan").addEventListener("click", async () => {
    await queueScan(parsed, email, true, publish);
  });
}

async function onScoreSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  clearSubmitError();
  setHidden(document.getElementById("rescan-confirm"), true);
  let parsed;
  try {
    parsed = parseGithubRepository(String(data.get("repository") || ""));
  } catch (error) {
    showSubmitError(error instanceof Error ? error.message : "Enter a GitHub repository URL.");
    return;
  }
  const email = String(data.get("email") || "").trim();
  const publish = data.get("publish") === "on";
  const existing = findEntry(parsed.slug);
  if (existing) {
    askRescan(parsed, email, existing, publish);
    return;
  }
  await queueScan(parsed, email, false, publish);
}

async function onContactSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  await capture("contact_submitted", {
    email: String(data.get("email") || "").trim(),
    message: String(data.get("message") || "").trim(),
  });
  form.hidden = true;
  setHidden(document.getElementById("contact-queued"), false);
}

async function boot() {
  const index = await fetch("reports/index.json", { cache: "no-store" }).then((response) => {
    if (!response.ok) throw new Error("The report index is unavailable.");
    return response.json();
  });
  reportIndex = index.reports || [];
  const query = params();
  const repo = query.get("repo");
  if (repo) {
    document.getElementById("intro").hidden = true;
    document.getElementById("registry").hidden = true;
    const entry = findEntry(repo);
    if (!entry) {
      showResult(`<a class="back-link" href="./">← Index</a><div class="alert error">No published report for ${escapeHtml(repo)}.</div>`);
    } else {
      try {
        const report = await loadFullReport(entry);
        showResult(renderReport(report, entry));
      } catch (error) {
        showResult(`<div class="alert error">${escapeHtml(error.message)}</div>`);
      }
    }
  } else {
    renderList(Number(query.get("page") || "1"));
  }
}

document.getElementById("score-form").addEventListener("submit", onScoreSubmit);
document.getElementById("contact-form").addEventListener("submit", onContactSubmit);
document.getElementById("contact-open").addEventListener("click", openContact);
document.getElementById("contact-close").addEventListener("click", closeContact);
document.getElementById("contact-backdrop").addEventListener("click", closeContact);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeContact();
});
boot().catch((error) => {
  showResult(`<div class="alert error">${escapeHtml(error.message)}</div>`);
});
