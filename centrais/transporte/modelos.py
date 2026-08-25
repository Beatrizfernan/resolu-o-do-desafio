from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PerfilMineral:
    mineral: str
    valor: float
    raridade: float
    taxa_degradacao: float
    sensibilidade_transporte: float
    prioridade: int
    modos: tuple[str, ...]
    pesos: tuple[float, float, float, float, float]


@dataclass(frozen=True)
class ModoTransporte:
    nome: str
    mult_energia: float
    mult_duracao: float
    mult_degradacao: float


@dataclass(frozen=True)
class CargaDisponivel:
    identificador: str
    mineral: str
    quantidade: float
    ciclo_de_entrada: int


@dataclass(frozen=True)
class UnidadeProjetada:
    identificador: str
    estado: str
    desgaste: float = 0.0
    viagens_restantes: int = 10


@dataclass(frozen=True)
class CandidatoDeTransporte:
    carga: CargaDisponivel
    unidade: UnidadeProjetada
    rota: dict
    modo: str
    duracao: int
    energia: float
    perda_de_valor: float
    risco: float
    desgaste: float
    score: float = 0.0

    @property
    def saldo_minimo(self) -> float:
        return self.energia + 2.0 + 0.05 * self.duracao
