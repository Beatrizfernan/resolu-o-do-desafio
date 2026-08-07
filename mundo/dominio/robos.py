from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EstadoDoRobo(str, Enum):
    DISPONIVEL = "disponivel"
    EXECUTANDO = "executando"
    AGUARDANDO = "aguardando"
    RETORNANDO = "retornando"
    INDISPONIVEL = "indisponivel"


@dataclass
class Robo:
    identificador: str
    estado: EstadoDoRobo
    energia_necessaria: int
    desgaste: float
    localizacao: str
    capacidade: float


@dataclass
class UnidadeMineradora(Robo):
    pass


@dataclass
class UnidadeTransportadora(Robo):
    viagens_disponiveis: int = 0
