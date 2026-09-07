from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LRC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Lean Report Card"
    environment: str = "development"
    public_base_url: str = "http://localhost"
    secret_key: str = "development-only"

    database_url: str = "sqlite+pysqlite:///./.data/lean-report-card.db"
    redis_url: str = "redis://localhost:6379/0"
    analyzer_version: str = "0.2.0"
    runner_image: str = "lean-report-card-runner:local"
    runner_mode: str = "docker"

    github_token: str | None = None
    big_repo_threshold_kib: int = 100_000
    known_big_repos: str = "leanprover-community/mathlib4,leanprover/lean4"

    small_timeout_seconds: int = 1_800
    big_timeout_seconds: int = 7_200
    small_memory: str = "4g"
    big_memory: str = "12g"
    small_cpus: float = 2.0
    big_cpus: float = 6.0
    small_lean_threads: int = 2
    big_lean_threads: int = 6
    max_log_bytes: int = 1_000_000
    runner_network_mode: str = "bridge"
    elan_cache_volume: str = "lrc_elan_cache"
    lake_cache_volume: str = "lrc_lake_cache"

    # Public PostHog project token (phc_...). This identifies the project to the
    # browser SDK; it is not a secret personal API key.
    posthog_project_token: str = "phc_s94Q4HVoFQHHZCXNvYYY84f9FKuDjGFKgwpBCWjwGr2K"
    posthog_host: str = "https://eu.i.posthog.com"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
