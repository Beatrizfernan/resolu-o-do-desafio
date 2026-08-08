from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mundo.dominio.robos import EstadoDoRobo
from mundo.dominio.rotas import CondicaoDaRota
from mundo.motor.comandos import Comando

from .dependencias import obter_motor

router = APIRouter(prefix="/transporte", tags=["transporte"])
CENTRAL = "transporte"
CUSTO_ENERGETICO_VIAGEM = 3


@router.get("/rotas")
async def consultar_rotas() -> list[dict]:
    motor = obter_motor()
    return [
        {
            "identificador": rota.identificador,
            "origem": rota.origem,
            "destino": rota.destino,
            "distancia": rota.distancia,
            "condicao": rota.condicao.value,
        }
        for rota in motor.rotas.values()
    ]


@router.get("/transportadores")
async def consultar_transportadores() -> list[dict]:
    motor = obter_motor()
    return [
        {
            "identificador": robo.identificador,
            "estado": robo.estado.value,
            "localizacao": robo.localizacao,
        }
        for robo in motor.robos.values()
        if hasattr(robo, "viagens_disponiveis")
    ]


@router.get("/cargas-disponiveis")
async def consultar_cargas_disponiveis() -> list[dict]:
    motor = obter_motor()
    return [
        {
            "identificador": carga.identificador,
            "mineral": carga.mineral,
            "quantidade": carga.quantidade,
            "qualidade": carga.qualidade,
        }
        for carga in motor.cargas.values()
    ]


@router.get("/planejar-transporte")
async def planejar_transporte(identificador_da_carga: str) -> dict:
    motor = obter_motor()
    carga = motor.cargas.get(identificador_da_carga)
    if carga is None:
        raise HTTPException(status_code=404, detail="Carga não encontrada")
    rotas_livres = [
        rota.identificador for rota in motor.rotas.values() if rota.condicao == CondicaoDaRota.LIVRE
    ]
    return {"carga": carga.identificador, "rotas_disponiveis": rotas_livres}


class RequisicaoDeCarregamento(BaseModel):
    identificador_da_unidade: str
    identificador_da_carga: str


@router.post("/carregar")
async def carregar(requisicao: RequisicaoDeCarregamento) -> dict:
    motor = obter_motor()
    unidade = motor.robos.get(requisicao.identificador_da_unidade)
    if unidade is None:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")

    def executar() -> None:
        if unidade.estado != EstadoDoRobo.DISPONIVEL:
            raise ValueError("Unidade indisponível")
        carga = motor.cargas[requisicao.identificador_da_carga]
        if carga.quantidade > unidade.capacidade:
            raise ValueError("Capacidade da unidade excedida")
        unidade.estado = EstadoDoRobo.AGUARDANDO

    motor.enfileirar_comando(Comando("carregar", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeViagem(BaseModel):
    identificador_da_unidade: str
    identificador_da_rota: str
    identificador_da_carga: str
    id_autorizacao: str


@router.post("/iniciar-viagem")
async def iniciar_viagem(requisicao: RequisicaoDeViagem) -> dict:
    motor = obter_motor()
    unidade = motor.robos.get(requisicao.identificador_da_unidade)
    rota = motor.rotas.get(requisicao.identificador_da_rota)
    if unidade is None or rota is None:
        raise HTTPException(status_code=404, detail="Unidade ou rota não encontrada")

    def executar() -> None:
        motor.autorizacoes.consumir(requisicao.id_autorizacao, "iniciar_viagem")
        if rota.condicao != CondicaoDaRota.LIVRE:
            raise ValueError("Rota interditada")
        if unidade.viagens_disponiveis <= 0:
            raise ValueError("Sem viagens disponíveis")
        motor.energia.debitar(CENTRAL, CUSTO_ENERGETICO_VIAGEM)
        unidade.viagens_disponiveis -= 1
        unidade.estado = EstadoDoRobo.EXECUTANDO
        ciclo_chegada = motor.ciclo_atual + rota.tempo_base

        def concluir() -> None:
            carga = motor.cargas[requisicao.identificador_da_carga]
            carga.degradar(taxa_degradacao=rota.risco, fator_contexto=1.0)
            unidade.estado = EstadoDoRobo.RETORNANDO
            motor.eventos.publicar(
                "transporte_concluido",
                motor.ciclo_atual,
                {"unidade": unidade.identificador, "carga": carga.identificador},
            )

        motor.agendar_efeito(ciclo_chegada, concluir)

    motor.enfileirar_comando(Comando("iniciar_viagem", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeUnidade(BaseModel):
    identificador_da_unidade: str


@router.post("/abortar-viagem")
async def abortar_viagem(requisicao: RequisicaoDeUnidade) -> dict:
    motor = obter_motor()
    unidade = motor.robos.get(requisicao.identificador_da_unidade)
    if unidade is None:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")

    def executar() -> None:
        unidade.estado = EstadoDoRobo.RETORNANDO

    motor.enfileirar_comando(Comando("abortar_viagem", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


@router.post("/descarregar")
async def descarregar(requisicao: RequisicaoDeCarregamento) -> dict:
    motor = obter_motor()

    def executar() -> None:
        motor.eventos.publicar(
            "carga_disponivel", motor.ciclo_atual, {"carga": requisicao.identificador_da_carga},
        )

    motor.enfileirar_comando(Comando("descarregar", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


@router.post("/retornar-unidade")
async def retornar_unidade(requisicao: RequisicaoDeUnidade) -> dict:
    motor = obter_motor()
    unidade = motor.robos.get(requisicao.identificador_da_unidade)
    if unidade is None:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")

    def executar() -> None:
        unidade.estado = EstadoDoRobo.DISPONIVEL

    motor.enfileirar_comando(Comando("retornar_unidade", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}
