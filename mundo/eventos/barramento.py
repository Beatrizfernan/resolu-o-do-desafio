from __future__ import annotations

import itertools
from typing import Callable

from .evento import Evento


class BarramentoDeEventos:
    def __init__(self) -> None:
        self._contador = itertools.count(1)
        self._registro: list[Evento] = []
        self._assinantes: list[Callable[[Evento], None]] = []

    def assinar(self, callback: Callable[[Evento], None]) -> None:
        self._assinantes.append(callback)

    def publicar(self, tipo: str, ciclo: int, dados: dict) -> Evento:
        identificador = f"evt-{next(self._contador)}"
        evento = Evento(identificador=identificador, tipo=tipo, ciclo=ciclo, dados=dados)
        self._registro.append(evento)
        for assinante in self._assinantes:
            assinante(evento)
        return evento

    def consultar_eventos(self, desde_ciclo: int = 0) -> list[Evento]:
        return [e for e in self._registro if e.ciclo >= desde_ciclo]
