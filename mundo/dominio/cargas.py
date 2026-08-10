from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mundo.dominio.minerais import Mineral


class LocalDaCarga(str, Enum):
    EM_JAZIDA = "em_jazida"
    EM_ARMAZEM = "em_armazem"
    EM_TRANSITO = "em_transito"
    NA_MAO = "na_mao"
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
    analisada: bool = False

    def __post_init__(self) -> None:
        self.qualidade = clamp_qualidade(self.qualidade)

    def mover_para(self, local: LocalDaCarga, mult_degradacao_local: float = 1.0) -> None:
        """Troca o local e o multiplicador de degradação juntos.

        Os dois campos são um par: um multiplicador nasce de um contexto (o modo
        da viagem, por exemplo) e deixa de valer quando a carga sai dele. Escrever
        um sem o outro deixa o modificador colado num local onde ele não se aplica
        mais, e a carga passa a degradar mais rápido ou mais devagar para sempre.
        """
        self.local = local
        self.mult_degradacao_local = mult_degradacao_local

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
