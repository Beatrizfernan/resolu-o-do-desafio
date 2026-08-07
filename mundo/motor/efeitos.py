from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from typing import Callable


@dataclass(order=True)
class _ItemAgenda:
    ciclo_alvo: int
    sequencia: int
    callback: Callable[[], None] = field(compare=False)


class AgendaDeEfeitos:
    def __init__(self) -> None:
        self._heap: list[_ItemAgenda] = []
        self._contador = itertools.count()

    def agendar(self, ciclo_alvo: int, callback: Callable[[], None]) -> None:
        heapq.heappush(self._heap, _ItemAgenda(ciclo_alvo, next(self._contador), callback))

    def disparar_ate(self, ciclo_atual: int) -> None:
        while self._heap and self._heap[0].ciclo_alvo <= ciclo_atual:
            item = heapq.heappop(self._heap)
            item.callback()
