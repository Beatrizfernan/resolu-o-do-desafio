from __future__ import annotations

from dataclasses import dataclass


def clamp_qualidade(valor: float) -> float:
    return max(0.0, min(100.0, valor))


@dataclass
class CargaMineral:
    identificador: str
    mineral: str
    quantidade: float
    qualidade: float = 100.0

    def __post_init__(self) -> None:
        self.qualidade = clamp_qualidade(self.qualidade)

    def degradar(self, taxa_degradacao: float, fator_contexto: float = 1.0) -> None:
        perda = taxa_degradacao * fator_contexto
        self.qualidade = clamp_qualidade(self.qualidade - perda)

    def valor_efetivo(self, valor_por_unidade: float) -> float:
        return self.quantidade * valor_por_unidade * (self.qualidade / 100)
