from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EstadoDaJazida(str, Enum):
    DESCONHECIDA = "desconhecida"
    IDENTIFICADA = "identificada"
    DISPONIVEL = "disponivel"
    INTERDITADA = "interditada"
    ESGOTADA = "esgotada"


class TransicaoDeEstadoInvalidaError(Exception):
    pass


_TRANSICOES_VALIDAS: dict[EstadoDaJazida, set[EstadoDaJazida]] = {
    EstadoDaJazida.DESCONHECIDA: {EstadoDaJazida.IDENTIFICADA},
    EstadoDaJazida.IDENTIFICADA: {EstadoDaJazida.DISPONIVEL, EstadoDaJazida.INTERDITADA},
    EstadoDaJazida.DISPONIVEL: {EstadoDaJazida.INTERDITADA, EstadoDaJazida.ESGOTADA},
    EstadoDaJazida.INTERDITADA: {EstadoDaJazida.DISPONIVEL},
    EstadoDaJazida.ESGOTADA: set(),
}


@dataclass
class Jazida:
    identificador: str
    localizacao: str
    mineral: str
    quantidade_disponivel: float
    dificuldade_extracao: float
    risco: float
    estado: EstadoDaJazida = EstadoDaJazida.DESCONHECIDA
    quantidade_inicial: float | None = None
    composicao_real: dict[str, float] | None = None
    composicao_estimada: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.quantidade_inicial is None:
            self.quantidade_inicial = self.quantidade_disponivel
        if self.composicao_real is None:
            self.composicao_real = {self.mineral: 1.0}

    @property
    def fracao_restante(self) -> float:
        """Quanto da jazida ainda existe, entre 0.0 (exaurida) e 1.0 (intacta)."""
        if not self.quantidade_inicial:
            return 0.0
        return max(0.0, min(1.0, self.quantidade_disponivel / self.quantidade_inicial))

    def transicionar(self, novo_estado: EstadoDaJazida) -> None:
        if novo_estado not in _TRANSICOES_VALIDAS[self.estado]:
            raise TransicaoDeEstadoInvalidaError(f"{self.estado} -> {novo_estado}")
        self.estado = novo_estado

    def estimar_composicao(self) -> dict[str, str]:
        estimativa: dict[str, str] = {}
        for mineral, fracao in self.composicao_real.items():
            if fracao <= 0.0:
                continue
            if fracao <= 0.05:
                estimativa[mineral] = "tracos"
            elif fracao <= 0.20:
                estimativa[mineral] = "baixa"
            elif fracao <= 0.50:
                estimativa[mineral] = "media"
            else:
                estimativa[mineral] = "alta"
        return estimativa

    def extrair(self, quantidade: float) -> None:
        if self.estado != EstadoDaJazida.DISPONIVEL:
            raise ValueError("Jazida não disponível para extração")
        if quantidade > self.quantidade_disponivel:
            raise ValueError("Quantidade solicitada excede o disponível")
        self.quantidade_disponivel -= quantidade
        if self.quantidade_disponivel == 0:
            self.transicionar(EstadoDaJazida.ESGOTADA)
