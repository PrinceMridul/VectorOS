"""Application settings.

Every pedagogical constant lives here rather than being sprinkled through the
code, because these are *product decisions* that a founder should be able to
tune in one place and A/B test later.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VECTOROS_",
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Core ────────────────────────────────────────────────────────────────
    env: Literal["development", "staging", "production"] = "development"
    secret_key: str = "dev-secret-change-me"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # ── Database ────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./vectoros.db"
    database_echo: bool = False

    auto_seed: bool = False
    """Load the template curricula at startup if they are missing.

    Off by default — a production process should not mutate content on boot.
    On in Docker, so that `docker compose up` yields a working tutor rather than
    an empty goal list and a confused first impression.
    """

    # ── AI provider layer ───────────────────────────────────────────────────
    llm_provider: Literal["mock", "gemini", "openai", "anthropic"] = "mock"
    model_fast: str = "gemini-2.5-flash-lite"
    model_balanced: str = "gemini-2.5-flash"
    model_deep: str = "claude-sonnet-5"
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2

    embedding_provider: Literal["mock", "gemini", "openai"] = "mock"
    embedding_model: str = "text-embedding-004"
    embedding_dim: int = 768

    google_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # ── Pedagogy (see ARCHITECTURE.md §5) ───────────────────────────────────
    mastery_threshold: float = 0.85
    """P(mastery) required on every prerequisite before a node unlocks."""

    mastery_floor: float = 0.05
    """Decay never drives mastery to zero — you never fully un-learn."""

    zpd_target_low: float = 0.50
    zpd_target_high: float = 0.80
    """Desirable-difficulty band. Below → boredom, above → cognitive overload."""

    struggle_floor_seconds: int = 45
    """Minimum think time before 'Request guidance' unlocks. Productive failure has a floor."""

    offload_lock_threshold: int = 3
    """Answer-demands tolerated before the client locks free text."""

    mastery_half_life_days: float = 14.0
    """Time constant of the forgetting curve used for review scheduling."""

    max_scaffold_level: int = 4
    """0 none · 1 orient · 2 targeted probe · 3 structural hint · 4 worked step.
    There is no rung 5, because rung 5 would be the answer."""

    challenge_pass_threshold: float = 0.75
    """Graded correctness at which an attempt counts as *correct*.

    Deliberately below 1.0. The Examiner's taxonomy puts "sound reasoning, minor
    execution error" at 0.7 and calls that a slip — and coaching someone through
    a slip they did not make a conceptual error on wastes their time and reads as
    the tutor not listening. Above this bar the learner goes to the reflection
    gate, which is a harder test than the challenge was.
    """

    reflection_pass_threshold: float = 0.6
    """Semantic coverage of the canonical model required to clear the metacognitive gate."""

    guard_leak_similarity: float = 0.86
    """Cosine similarity to the canonical answer above which a draft counts as a leak."""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    def api_key_for(self, provider: str) -> str:
        return {
            "gemini": self.google_api_key,
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
        }.get(provider, "")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
