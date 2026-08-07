from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Evento:
    identificador: str
    tipo: str
    ciclo: int
    dados: dict[str, Any] = field(default_factory=dict)
