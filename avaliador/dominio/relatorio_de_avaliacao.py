from __future__ import annotations

from dataclasses import dataclass

from .resultado_da_seed import ResultadoDaSeed


@dataclass(frozen=True)
class RelatorioDeAvaliacao:
    integridade_aprovada: bool
    divergencias_de_integridade: list[str]
    configuracao: dict
    resultados: list[ResultadoDaSeed]
    faturamento_medio: float
    faturamento_mediano: float
    ciclo_medio_de_encerramento: float
    energia_encalhada_media: float
    taxa_de_falha_operacional: float
