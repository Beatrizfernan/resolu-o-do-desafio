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
    ) -> None:
        self._extracao = extracao
        self._transporte = transporte
        self.fator_base_de_energia = fator_base_de_energia
        self._multiplicador_por_local = multiplicador_por_local

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
        )

    def obter_extracao(self, modo: ModoDeExtracao) -> PerfilDeExtracao:
        if modo.value not in self._extracao:
            raise ValueError(f"Modo de extração desconhecido: {modo}")
        return self._extracao[modo.value]

    def obter_transporte(self, modo: ModoDeTransporte) -> PerfilDeTransporte:
        if modo.value not in self._transporte:
            raise ValueError(f"Modo de transporte desconhecido: {modo}")
        return self._transporte[modo.value]

    def mult_do_local(self, local: str) -> float:
        if local not in self._multiplicador_por_local:
            raise ValueError(f"Local desconhecido: {local}")
        return self._multiplicador_por_local[local]
