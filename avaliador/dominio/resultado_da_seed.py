from __future__ import annotations

from dataclasses import dataclass

from .status_de_avaliacao import StatusDeAvaliacao


@dataclass(frozen=True)
class ResultadoDaSeed:
    seed: int
    status: StatusDeAvaliacao
    ciclo_final: int
    faturamento_total: float
    energia_encalhada: float
    operacoes_invalidas: int = 0
    autorizacoes_emitidas: int = 0
    cargas_entregues: int = 0
    cargas_analisadas: int = 0
    jazidas_esgotadas: int = 0
    erro_operacional: str | None = None
