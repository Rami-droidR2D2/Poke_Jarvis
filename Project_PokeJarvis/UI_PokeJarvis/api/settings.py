"""API configuration."""

from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    pokejarvis_root: str = Field(default="", validation_alias="POKEJARVIS_ROOT")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="CORS_ORIGINS",
    )

    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def resolved_root(self) -> Path:
        raw = self.pokejarvis_root.strip()
        if not raw:
            raise ValueError(
                "Set POKEJARVIS_ROOT (or pokejarvis_root in .env) to the Project_PokeJarvis directory"
            )
        p = Path(raw).expanduser().resolve()
        if not p.is_dir():
            raise ValueError(f"POKEJARVIS_ROOT is not a directory: {p}")
        return p


settings = Settings()
