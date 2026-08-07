from __future__ import annotations

from dataclasses import dataclass, field


class CapacidadeExcedidaError(Exception):
    pass


@dataclass
class Armazem:
    identificador: str
    capacidade: float
    localizacao: str
    condicoes: str
    compatibilidades: set[str] = field(default_factory=set)
    ocupacao: float = 0.0

    def reservar_espaco(self, quantidade: float) -> None:
        if self.ocupacao + quantidade > self.capacidade:
            raise CapacidadeExcedidaError(self.identificador)
        self.ocupacao += quantidade

    def liberar_espaco(self, quantidade: float) -> None:
        self.ocupacao = max(0.0, self.ocupacao - quantidade)

    def compativel_com(self, mineral: str) -> bool:
        return not self.compatibilidades or mineral in self.compatibilidades
