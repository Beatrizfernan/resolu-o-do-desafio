from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Comando:
    tipo: str
    central_origem: str
    payload: dict[str, Any]
    executar: Callable[[], None]


class FilaDeComandos:
    def __init__(self) -> None:
        self._fila: deque[Comando] = deque()

    def enfileirar(self, comando: Comando) -> None:
        self._fila.append(comando)

    def drenar(self) -> list[Comando]:
        comandos = list(self._fila)
        self._fila.clear()
        return comandos
