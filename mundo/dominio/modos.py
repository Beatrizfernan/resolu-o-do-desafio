from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ModoDeExtracao(str, Enum):
    CUIDADOSO = "cuidadoso"
    NORMAL = "normal"
    AGRESSIVO = "agressivo"


class ModoDeTransporte(str, Enum):
    ECONOMICO = "economico"
    NORMAL = "normal"
    RAPIDO = "rapido"


@dataclass(frozen=True)
class PerfilDeExtracao:
    mult_energia: float
    mult_duracao: float
    qualidade_inicial: float
    fator_desperdicio: float


@dataclass(frozen=True)
class PerfilDeTransporte:
    mult_energia: float
    mult_duracao: float
    mult_degradacao: float


class CatalogoDeModos:
    def __init__(
        self,
        extracao: dict[str, PerfilDeExtracao],
        transporte: dict[str, PerfilDeTransporte],
        fator_base_de_energia: float,
        multiplicador_por_local: dict[str, float],
        fator_escassez_maximo: float = 1.0,
        expoente_escassez: float = 0.0,
    ) -> None:
        self._extracao = extracao
        self._transporte = transporte
        self.fator_base_de_energia = fator_base_de_energia
        self._multiplicador_por_local = multiplicador_por_local
        self.fator_escassez_maximo = fator_escassez_maximo
        self.expoente_escassez = expoente_escassez

    @classmethod
    def carregar_de_arquivo(cls, caminho: Path) -> "CatalogoDeModos":
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        extracao = {nome: PerfilDeExtracao(**valores) for nome, valores in dados["extracao"].items()}
        transporte = {
            nome: PerfilDeTransporte(**valores) for nome, valores in dados["transporte"].items()
        }
        return cls(
            extracao,
            transporte,
            dados["fator_base_de_energia"],
            dados["multiplicador_por_local"],
            dados["fator_escassez_maximo"],
            dados["expoente_escassez"],
        )

    def obter_extracao(self, modo: ModoDeExtracao) -> PerfilDeExtracao:
        if modo.value not in self._extracao:
            raise ValueError(f"Modo de extração desconhecido: {modo}")
        return self._extracao[modo.value]

    def obter_transporte(self, modo: ModoDeTransporte) -> PerfilDeTransporte:
        if modo.value not in self._transporte:
            raise ValueError(f"Modo de transporte desconhecido: {modo}")
        return self._transporte[modo.value]

    def fator_de_escassez(self, fracao_restante: float) -> float:
        """Encarece a extração à medida que a jazida se esvazia.

        O minério que sobra numa jazida quase exaurida está mais fundo e mais
        disperso: o custo por unidade cresce como o inverso da fração restante,
        limitado por `fator_escassez_maximo` para o custo continuar finito.
        Numa jazida intacta o fator é 1.0 e nada muda.

        É este fator que dá preço ao desperdício: um modo que consome 1.4 da
        jazida por unidade entregue empurra a jazida para a faixa cara 40% mais
        depressa do que um modo que consome 1.0.
        """
        if fracao_restante <= 0.0:
            return self.fator_escassez_maximo
        fracao = min(1.0, fracao_restante)
        return min(self.fator_escassez_maximo, fracao ** -self.expoente_escassez)

    def mult_do_local(self, local: str) -> float:
        if local not in self._multiplicador_por_local:
            raise ValueError(f"Local desconhecido: {local}")
        return self._multiplicador_por_local[local]
