from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CondicaoDaRota(str, Enum):
    LIVRE = "livre"
    INTERDITADA = "interditada"


@dataclass
class Rota:
    identificador: str
    origem: str
    destino: str
    distancia: float
    tempo_base: int
    risco: float
    condicao: CondicaoDaRota = CondicaoDaRota.LIVRE
