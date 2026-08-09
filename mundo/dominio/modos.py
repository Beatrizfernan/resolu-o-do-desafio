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
        taxa_de_desgaste: float = 0.0,
        recuperacao_de_desgaste_por_ciclo: float = 0.0,
        sensibilidade_ao_desgaste: float = 0.0,
        sensibilidade_a_raridade_em_transito: float = 0.0,
    ) -> None:
        self._extracao = extracao
        self._transporte = transporte
        self.fator_base_de_energia = fator_base_de_energia
        self._multiplicador_por_local = multiplicador_por_local
        self.fator_escassez_maximo = fator_escassez_maximo
        self.expoente_escassez = expoente_escassez
        self.taxa_de_desgaste = taxa_de_desgaste
        self.recuperacao_de_desgaste_por_ciclo = recuperacao_de_desgaste_por_ciclo
        self.sensibilidade_ao_desgaste = sensibilidade_ao_desgaste
        self.sensibilidade_a_raridade_em_transito = sensibilidade_a_raridade_em_transito

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
            dados["taxa_de_desgaste"],
            dados["recuperacao_de_desgaste_por_ciclo"],
            dados["sensibilidade_ao_desgaste"],
            dados["sensibilidade_a_raridade_em_transito"],
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

    def fator_de_raridade_em_transito(self, raridade: float) -> float:
        """Quanto a raridade acelera a perda de qualidade durante a viagem.

        Minério raro é instável fora de um armazém: quanto mais raro, mais
        depressa cada ciclo de viagem o degrada. É isto que dá ao transporte
        rápido uma razão de existir — carga comum pode viajar devagar e barato,
        carga rara não pode.

        Vale só em trânsito. Parada num armazém a raridade não pesa: o que
        castiga é o tempo exposto no caminho, não a posse.
        """
        return 1.0 + max(0.0, raridade) * self.sensibilidade_a_raridade_em_transito

    def fator_de_desgaste(self, desgaste: float) -> float:
        """Quanto o desgaste acumulado encarece a próxima operação.

        Cresce linearmente e sem teto: um robô nunca é bloqueado, só fica
        progressivamente caro de operar até que descanse.
        """
        return 1.0 + max(0.0, desgaste) * self.sensibilidade_ao_desgaste

    def mult_do_local(self, local: str) -> float:
        if local not in self._multiplicador_por_local:
            raise ValueError(f"Local desconhecido: {local}")
        return self._multiplicador_por_local[local]
