from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mundo.dominio.minerais import Mineral


class LocalDaCarga(str, Enum):
    EM_JAZIDA = "em_jazida"
    EM_ARMAZEM = "em_armazem"
    EM_TRANSITO = "em_transito"
    ENTREGUE = "entregue"


def clamp_qualidade(valor: float) -> float:
    return max(0.0, min(100.0, valor))


@dataclass
class CargaMineral:
    identificador: str
    mineral: str
    quantidade: float
    qualidade: float = 100.0
    local: LocalDaCarga = LocalDaCarga.EM_JAZIDA
    mult_degradacao_local: float = 1.0

    def __post_init__(self) -> None:
        self.qualidade = clamp_qualidade(self.qualidade)

    def degradar(self, taxa_degradacao: float, fator_contexto: float = 1.0) -> None:
        perda = taxa_degradacao * fator_contexto
        self.qualidade = clamp_qualidade(self.qualidade - perda)

    def valor_efetivo(self, valor_por_unidade: float) -> float:
        return self.quantidade * valor_por_unidade * (self.qualidade / 100)

    def sensibilidade_aplicavel(self, mineral: Mineral) -> float:
        if self.local == LocalDaCarga.EM_ARMAZEM:
            return mineral.sensibilidade_armazenagem
        if self.local == LocalDaCarga.EM_TRANSITO:
            return mineral.sensibilidade_transporte
        return 1.0
