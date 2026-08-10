from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mundo.dominio.cargas import LocalDaCarga
from mundo.motor.comandos import Comando

from .dependencias import obter_motor

router = APIRouter(prefix="/pesquisa", tags=["pesquisa"])
CENTRAL = "pesquisa"
DURACAO_ANALISE_EM_CICLOS = 3
CUSTO_ENERGETICO_ANALISE = 2
LIMIAR_QUALIDADE_APROVACAO = 40.0


@router.get("/fila")
async def consultar_fila() -> list[str]:
    motor = obter_motor()
    return list(motor.fila_de_pesquisa)


class RequisicaoDeAnalise(BaseModel):
    identificador_da_carga: str


@router.post("/iniciar-analise")
async def iniciar_analise(requisicao: RequisicaoDeAnalise) -> dict:
    motor = obter_motor()
    if requisicao.identificador_da_carga not in motor.cargas:
        raise HTTPException(status_code=404, detail="Carga não encontrada")

    def executar() -> None:
        motor.energia.debitar(CENTRAL, CUSTO_ENERGETICO_ANALISE)
        motor.fila_de_pesquisa.append(requisicao.identificador_da_carga)
        ciclo_conclusao = motor.ciclo_atual + DURACAO_ANALISE_EM_CICLOS

        def concluir() -> None:
            motor.eventos.publicar("analise_concluida", motor.ciclo_atual, {
                "carga": requisicao.identificador_da_carga,
            })

        motor.agendar_efeito(ciclo_conclusao, concluir)

    motor.enfileirar_comando(Comando("iniciar_analise", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


@router.post("/classificar-carga")
async def classificar_carga(requisicao: RequisicaoDeAnalise) -> dict:
    motor = obter_motor()
    carga = motor.cargas.get(requisicao.identificador_da_carga)
    if carga is None:
        raise HTTPException(status_code=404, detail="Carga não encontrada")
    return {"carga": carga.identificador, "mineral": carga.mineral, "qualidade": carga.qualidade}


@router.post("/aprovar-carga")
async def aprovar_carga(requisicao: RequisicaoDeAnalise) -> dict:
    motor = obter_motor()

    def executar() -> None:
        carga = motor.cargas[requisicao.identificador_da_carga]
        if carga.qualidade < LIMIAR_QUALIDADE_APROVACAO:
            raise ValueError("Qualidade insuficiente para aprovação")
        if requisicao.identificador_da_carga in motor.fila_de_pesquisa:
            motor.fila_de_pesquisa.remove(requisicao.identificador_da_carga)
        motor.eventos.publicar("carga_aprovada", motor.ciclo_atual, {"carga": carga.identificador})

    motor.enfileirar_comando(Comando("aprovar_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


@router.post("/rejeitar-carga")
async def rejeitar_carga(requisicao: RequisicaoDeAnalise) -> dict:
    motor = obter_motor()

    def executar() -> None:
        if requisicao.identificador_da_carga in motor.fila_de_pesquisa:
            motor.fila_de_pesquisa.remove(requisicao.identificador_da_carga)
        motor.eventos.publicar(
            "carga_rejeitada", motor.ciclo_atual, {"carga": requisicao.identificador_da_carga},
        )

    motor.enfileirar_comando(Comando("rejeitar_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeDistribuicao(BaseModel):
    identificador_da_carga: str
    id_autorizacao: str


@router.post("/preparar-distribuicao")
async def preparar_distribuicao(requisicao: RequisicaoDeDistribuicao) -> dict:
    motor = obter_motor()

    def executar() -> None:
        motor.autorizacoes.consumir(requisicao.id_autorizacao, "preparar_distribuicao")
        carga = motor.cargas[requisicao.identificador_da_carga]
        if carga.local != LocalDaCarga.NA_MAO:
            raise ValueError("Só se distribui carga que está na mão")
        mineral = motor.catalogo_de_minerais.obter(carga.mineral)
        valor_entregue = carga.valor_efetivo(mineral.valor_por_unidade)
        motor.faturamento_total += valor_entregue
        motor.eventos.publicar("carga_entregue", motor.ciclo_atual, {
            "carga": carga.identificador, "valor_entregue": valor_entregue,
        })
        del motor.cargas[requisicao.identificador_da_carga]

    motor.enfileirar_comando(
        Comando("preparar_distribuicao", CENTRAL, requisicao.model_dump(), executar),
    )
    return {"aceito": True}
