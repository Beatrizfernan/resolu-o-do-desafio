from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.motor.motor_de_simulacao import ConfiguracaoDaSimulacao

from .dependencias import instancia_do_mundo

INTERVALO_DE_CICLO_SEGUNDOS = 1.0
CAMINHO_CATALOGO_PADRAO = Path(__file__).parent.parent / "config" / "minerais.json"

logger = logging.getLogger(__name__)


async def _loop_real_time() -> None:
    while True:
        await asyncio.sleep(INTERVALO_DE_CICLO_SEGUNDOS)
        if instancia_do_mundo.motor is not None:
            try:
                instancia_do_mundo.motor.avancar_ciclo()
            except Exception:
                logger.exception("Falha ao avançar o ciclo da simulação")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO_PADRAO)
    instancia_do_mundo.inicializar(ConfiguracaoDaSimulacao(semente=0), catalogo)
    if not app.state.com_loop_real_time:
        yield
        return
    tarefa = asyncio.create_task(_loop_real_time())
    try:
        yield
    finally:
        tarefa.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarefa


def criar_app(*, com_loop_real_time: bool = True) -> FastAPI:
    from . import armazenagem, extracao, missao, pesquisa, transporte

    app = FastAPI(title="Mundo — Operação Marciana", lifespan=ciclo_de_vida)
    app.state.com_loop_real_time = com_loop_real_time
    app.include_router(missao.router)
    app.include_router(extracao.router)
    app.include_router(armazenagem.router)
    app.include_router(transporte.router)
    app.include_router(pesquisa.router)
    return app


app = criar_app()
