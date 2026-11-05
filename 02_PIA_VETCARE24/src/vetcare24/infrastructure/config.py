"""Configuración leída del entorno. Un solo lugar, sin valores escondidos en el código."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_DB = "postgresql://vetcare:vetcare_dev@localhost:5432/vetcare24"
_DEFAULT_DATA = Path(__file__).resolve().parents[3] / "data" / "alumno"


@dataclass(frozen=True)
class Settings:
    database_url: str
    data_dir: Path


def load_settings() -> Settings:
    return Settings(
        database_url=os.environ.get("DATABASE_URL", _DEFAULT_DB),
        data_dir=Path(os.environ.get("DATA_DIR", str(_DEFAULT_DATA))),
    )
