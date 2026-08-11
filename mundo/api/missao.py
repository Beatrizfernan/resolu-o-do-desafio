from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mundo.dominio.energia import GerenciadorDeEnergia
from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.eventos.webhooks import DispatcherDeWebhooks
from mundo.motor.comandos import Comando
from mundo.motor.motor_de_simulacao import ConfiguracaoDaSimulacao

from .dependencias import instancia_do_mundo, obter_motor

router = APIRouter(prefix="/missao", tags=["missao"])
CAMINHO_CATALOGO = Path(__file__).parent.parent / "config" / "minerais.json"
CENTRAL = "missao"
CUSTOS_DE_AUTORIZACAO_POR_CLASSE = {"rapida": 0.2, "segura": 0.5, "lote": 0.8}


class RequisicaoDeResetarMundo(BaseModel):
    semente: int
    duracao_maxima: int | None = None


@router.post("/resetar-mundo")
async def resetar_mundo(requisicao: RequisicaoDeResetarMundo) -> dict:
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    instancia_do_mundo.inicializar(
        ConfiguracaoDaSimulacao(semente=requisicao.semente),
        catalogo,
    )
    return {"ciclo_atual": 0}


@router.get("/estado")
async def consultar_estado_global() -> dict:
    motor = obter_motor()
    centrais = ["extracao", "armazenagem", "transporte", "pesquisa", "missao", GerenciadorDeEnergia.RESERVA]
    return {
        "ciclo_atual": motor.ciclo_atual,
        "energia": {central: motor.energia.consultar_energia(central) for central in centrais},
        "faturamento_total": motor.faturamento_total,
    }


@router.get("/eventos")
async def consultar_eventos(desde_ciclo: int = 0) -> list[dict]:
    motor = obter_motor()
    return [
        {"identificador": e.identificador, "tipo": e.tipo, "ciclo": e.ciclo, "dados": e.dados}
        for e in motor.eventos.consultar_eventos(desde_ciclo)
    ]


class RequisicaoDeAlocacao(BaseModel):
    destino: str
    quantidade: int


@router.post("/alocar-energia")
async def alocar_energia(requisicao: RequisicaoDeAlocacao) -> dict:
    motor = obter_motor()

    def executar() -> None:
        if not motor.energia.esta_operante(CENTRAL):
            raise ValueError("Central de missão dormente: não há quem aloque")
        motor.energia.alocar_energia(
            GerenciadorDeEnergia.RESERVA, requisicao.destino, requisicao.quantidade,
        )

    motor.enfileirar_comando(Comando("alocar_energia", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeAutorizacao(BaseModel):
    operacao: str
    central_solicitante: str
    classe: Literal["rapida", "segura", "lote"] = "rapida"


@router.post("/autorizar-missao")
async def autorizar_missao(requisicao: RequisicaoDeAutorizacao) -> dict:
    motor = obter_motor()
    # Esta rota permanece síncrona de propósito: ela devolve o identificador
    # que o chamador usa na mesma requisição seguinte, então enfileirá-la
    # quebraria todo o resto do projeto. É exceção conhecida, e única.
    if not motor.energia.esta_operante(CENTRAL):
        raise HTTPException(status_code=400, detail="Central de missão dormente")
    try:
        motor.energia.debitar(CENTRAL, CUSTOS_DE_AUTORIZACAO_POR_CLASSE[requisicao.classe])
    except Exception as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    autorizacao = motor.autorizacoes.emitir(
        requisicao.operacao,
        requisicao.central_solicitante,
        classe=requisicao.classe,
    )
    return {"id_autorizacao": autorizacao.identificador}


class RequisicaoDeWebhook(BaseModel):
    url: str


@router.post("/registrar-webhook")
async def registrar_webhook(requisicao: RequisicaoDeWebhook) -> dict:
    motor = obter_motor()
    if not hasattr(motor, "_dispatcher_de_webhooks"):
        motor._dispatcher_de_webhooks = DispatcherDeWebhooks()
        motor.eventos.assinar(motor._dispatcher_de_webhooks.notificar)
    motor._dispatcher_de_webhooks.registrar(requisicao.url)
    return {"registrado": True}
