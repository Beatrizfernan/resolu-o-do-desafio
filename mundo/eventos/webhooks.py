from __future__ import annotations

import asyncio
import logging

from .evento import Evento

logger = logging.getLogger(__name__)


class DispatcherDeWebhooks:
    def __init__(self) -> None:
        self._urls: set[str] = set()

    def registrar(self, url: str) -> None:
        self._urls.add(url)

    def urls_registradas(self) -> set[str]:
        return set(self._urls)

    def notificar(self, evento: Evento) -> None:
        for url in self._urls:
            asyncio.create_task(self._enviar(url, evento))

    async def _enviar(self, url: str, evento: Evento) -> None:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=2.0) as cliente:
                await cliente.post(url, json={
                    "identificador": evento.identificador,
                    "tipo": evento.tipo,
                    "ciclo": evento.ciclo,
                    "dados": evento.dados,
                })
        except httpx.HTTPError:
            logger.warning("Falha ao entregar webhook para %s (evento %s)", url, evento.identificador)
