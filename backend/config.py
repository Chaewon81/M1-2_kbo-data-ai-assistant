from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def season_files(folder: str, prefix: str) -> tuple[str, ...]:
    root = Path(__file__).resolve().parents[1]
    return tuple(path.relative_to(root).as_posix() for path in sorted((root / folder).glob(f"{prefix}_*.csv"))
                 if re.fullmatch(rf"{prefix}_\d{{4}}\.csv", path.name))


@dataclass(frozen=True)
class Settings:
    app_name: str = "KBO Data AI Assistant"
    allowed_origins: tuple[str, ...] = ("http://localhost:5500", "http://127.0.0.1:5500")
    data_path: str = "M1-1_summary/data/processed/game_results.csv"
    data_paths: tuple[str, ...] = ()
    pitcher_data_path: str = "data/raw/pitcher_stats.csv"
    pitcher_data_paths: tuple[str, ...] = ()
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    ai_provider: str = "openai"
    openrouter_api_key: str | None = None
    openrouter_model: str = "openrouter/free"
    openai_mock_mode: bool = False
    require_firestore: bool = False
    chat_requests_per_minute: int = 10
    auto_sync_enabled: bool = False
    app_env: str = 'development'
    demo_access_key: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        chat_limit = int(os.getenv("CHAT_REQUESTS_PER_MINUTE", "10"))
        if chat_limit < 1:
            raise ValueError("CHAT_REQUESTS_PER_MINUTE must be >= 1")
        raw_origins = os.getenv("ALLOWED_ORIGINS", "")
        origins = tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())
        # 복수 경로를 명시하면 DATA_PATH보다 우선한다. 단일 파일 설정은 계속 지원한다.
        raw_paths = os.getenv("DATA_PATHS", "")
        data_paths = tuple(path.strip() for path in raw_paths.split(";") if path.strip())
        if not data_paths and not os.getenv("DATA_PATH"):
            data_paths = season_files("data/games", "game_results")
        raw_pitcher_paths = os.getenv("PITCHER_DATA_PATHS", "")
        pitcher_paths = tuple(path.strip() for path in raw_pitcher_paths.split(";") if path.strip())
        if not pitcher_paths and not os.getenv("PITCHER_DATA_PATH"):
            pitcher_paths = season_files("data/pitchers", "pitcher_stats")
        return cls(
            allowed_origins=origins or cls.allowed_origins,
            data_path=os.getenv("DATA_PATH", cls.data_path),
            data_paths=data_paths,
            pitcher_data_path=os.getenv("PITCHER_DATA_PATH", cls.pitcher_data_path),
            pitcher_data_paths=pitcher_paths,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            ai_provider=os.getenv("AI_PROVIDER", "openai").lower(),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            openrouter_model=os.getenv("OPENROUTER_MODEL", "openrouter/free"),
            openai_mock_mode=os.getenv("OPENAI_MOCK_MODE", "false").lower() in {"1", "true", "yes"},
            require_firestore=os.getenv("REQUIRE_FIRESTORE", "false").lower() in {"1", "true", "yes"},
            chat_requests_per_minute=chat_limit,
            auto_sync_enabled=os.getenv("AUTO_SYNC_ENABLED", "false").lower() in {"1", "true", "yes"},
            app_env=os.getenv('APP_ENV', 'development').lower(),
            demo_access_key=os.getenv('DEMO_ACCESS_KEY') or None,
        )


settings = Settings.from_env()
