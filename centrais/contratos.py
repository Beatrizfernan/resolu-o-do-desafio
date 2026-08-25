from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HandoffDeTransporte:
    identificador_da_carga: str
    mineral: str
    prioridade: str
    destino_primario: str
    destino_fallback: str
    armazem_recomendado: str
    motivo: str
    ciclo_limite_recomendado: int
