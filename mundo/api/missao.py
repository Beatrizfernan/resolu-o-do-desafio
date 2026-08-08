from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mundo.dominio.energia import GerenciadorDeEnergia
from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.eventos.webhooks import DispatcherDeWebhooks
from mundo.motor.motor_de_simulacao import ConfiguracaoDaSimulacao

from .dependencias import instancia_do_mundo, obter_motor

router = APIRouter(prefix="/missao", tags=["missao"])
CAMINHO_CATALOGO = Path(__file__).parent.parent / "config" / "minerais.json"


class RequisicaoDeResetarMundo(BaseModel):
    semente: int
    duracao_maxima: int


@router.post("/resetar-mundo")
def resetar_mundo(requisicao: RequisicaoDeResetarMundo) -> dict:
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    instancia_do_mundo.inicializar(
        ConfiguracaoDaSimulacao(semente=requisicao.semente, duracao_maxima=requisicao.duracao_maxima),
        catalogo,
    )
    return {"ciclo_atual": 0}


@router.get("/estado")
def consultar_estado_global() -> dict:
    motor = obter_motor()
    centrais = ["extracao", "armazenagem", "transporte", "pesquisa", "missao", GerenciadorDeEnergia.RESERVA]
    return {
        "ciclo_atual": motor.ciclo_atual,
        "energia": {central: motor.energia.consultar_energia(central) for central in centrais},
        "faturamento_total": motor.faturamento_total,
    }


@router.get("/eventos")
def consultar_eventos(desde_ciclo: int = 0) -> list[dict]:
    motor = obter_motor()
    return [
        {"identificador": e.identificador, "tipo": e.tipo, "ciclo": e.ciclo, "dados": e.dados}
        for e in motor.eventos.consultar_eventos(desde_ciclo)
    ]


class RequisicaoDeAlocacao(BaseModel):
    destino: str
    quantidade: int


@router.post("/alocar-energia")
def alocar_energia(requisicao: RequisicaoDeAlocacao) -> dict:
    motor = obter_motor()
    try:
        motor.energia.alocar_energia(GerenciadorDeEnergia.RESERVA, requisicao.destino, requisicao.quantidade)
    except Exception as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    return {"saldo": motor.energia.consultar_energia(requisicao.destino)}


class RequisicaoDeAutorizacao(BaseModel):
    operacao: str
    central_solicitante: str


@router.post("/autorizar-missao")
def autorizar_missao(requisicao: RequisicaoDeAutorizacao) -> dict:
    motor = obter_motor()
    autorizacao = motor.autorizacoes.emitir(requisicao.operacao, requisicao.central_solicitante)
    return {"id_autorizacao": autorizacao.identificador}


class RequisicaoDeWebhook(BaseModel):
    url: str


@router.post("/registrar-webhook")
def registrar_webhook(requisicao: RequisicaoDeWebhook) -> dict:
    motor = obter_motor()
    if not hasattr(motor, "_dispatcher_de_webhooks"):
        motor._dispatcher_de_webhooks = DispatcherDeWebhooks()
        motor.eventos.assinar(motor._dispatcher_de_webhooks.notificar)
    motor._dispatcher_de_webhooks.registrar(requisicao.url)
    return {"registrado": True}
