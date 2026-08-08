from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mundo.motor.comandos import Comando

from .dependencias import obter_motor

router = APIRouter(prefix="/armazenagem", tags=["armazenagem"])
CENTRAL = "armazenagem"
CUSTO_ENERGETICO_OPERACAO = 1
LIMIAR_PROXIMO_DA_CAPACIDADE = 0.9


@router.get("/armazens")
async def consultar_armazens() -> list[dict]:
    motor = obter_motor()
    return [
        {
            "identificador": armazem.identificador,
            "capacidade": armazem.capacidade,
            "ocupacao": armazem.ocupacao,
            "localizacao": armazem.localizacao,
            "condicoes": armazem.condicoes,
        }
        for armazem in motor.armazens.values()
    ]


class RequisicaoDeReserva(BaseModel):
    identificador_do_armazem: str
    quantidade: float


@router.post("/reservar-espaco")
async def reservar_espaco(requisicao: RequisicaoDeReserva) -> dict:
    motor = obter_motor()
    armazem = motor.armazens.get(requisicao.identificador_do_armazem)
    if armazem is None:
        raise HTTPException(status_code=404, detail="Armazém não encontrado")

    def executar() -> None:
        motor.energia.debitar(CENTRAL, CUSTO_ENERGETICO_OPERACAO)
        armazem.reservar_espaco(requisicao.quantidade)

    motor.enfileirar_comando(Comando("reservar_espaco", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeRecebimento(BaseModel):
    identificador_do_armazem: str
    identificador_da_carga: str


@router.post("/receber-carga")
async def receber_carga(requisicao: RequisicaoDeRecebimento) -> dict:
    motor = obter_motor()
    armazem = motor.armazens.get(requisicao.identificador_do_armazem)
    if armazem is None:
        raise HTTPException(status_code=404, detail="Armazém não encontrado")
    carga = motor.cargas.get(requisicao.identificador_da_carga)
    if carga is None:
        raise HTTPException(status_code=404, detail="Carga não encontrada")

    def executar() -> None:
        if not armazem.compativel_com(carga.mineral):
            motor.eventos.publicar(
                "carga_contaminada",
                motor.ciclo_atual,
                {"carga": carga.identificador, "armazem": armazem.identificador},
            )
            raise ValueError("Mineral incompatível com o armazém")
        motor.energia.debitar(CENTRAL, CUSTO_ENERGETICO_OPERACAO)
        armazem.reservar_espaco(carga.quantidade)
        if armazem.ocupacao >= armazem.capacidade:
            motor.eventos.publicar(
                "armazem_lotado", motor.ciclo_atual, {"armazem": armazem.identificador},
            )
        elif armazem.ocupacao >= armazem.capacidade * LIMIAR_PROXIMO_DA_CAPACIDADE:
            motor.eventos.publicar(
                "armazem_proximo_da_capacidade", motor.ciclo_atual, {"armazem": armazem.identificador},
            )

    motor.enfileirar_comando(Comando("receber_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeRealocacao(BaseModel):
    identificador_da_carga: str
    identificador_do_armazem_origem: str
    identificador_do_armazem_destino: str


@router.post("/realocar-carga")
async def realocar_carga(requisicao: RequisicaoDeRealocacao) -> dict:
    motor = obter_motor()

    def executar() -> None:
        origem = motor.armazens[requisicao.identificador_do_armazem_origem]
        destino = motor.armazens[requisicao.identificador_do_armazem_destino]
        carga = motor.cargas[requisicao.identificador_da_carga]
        destino.reservar_espaco(carga.quantidade)
        origem.liberar_espaco(carga.quantidade)

    motor.enfileirar_comando(Comando("realocar_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeLiberacao(BaseModel):
    identificador_do_armazem: str
    quantidade: float


@router.post("/liberar-carga")
async def liberar_carga(requisicao: RequisicaoDeLiberacao) -> dict:
    motor = obter_motor()

    def executar() -> None:
        motor.armazens[requisicao.identificador_do_armazem].liberar_espaco(requisicao.quantidade)

    motor.enfileirar_comando(Comando("liberar_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeDescarte(BaseModel):
    identificador_da_carga: str
    identificador_do_armazem: str


@router.post("/descartar-carga")
async def descartar_carga(requisicao: RequisicaoDeDescarte) -> dict:
    motor = obter_motor()

    def executar() -> None:
        carga = motor.cargas.pop(requisicao.identificador_da_carga)
        motor.armazens[requisicao.identificador_do_armazem].liberar_espaco(carga.quantidade)
        motor.eventos.publicar("carga_descartada", motor.ciclo_atual, {"carga": carga.identificador})

    motor.enfileirar_comando(Comando("descartar_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeSolicitacaoDeTransporte(BaseModel):
    identificador_da_carga: str
    id_autorizacao: str


@router.post("/solicitar-transporte")
async def solicitar_transporte(requisicao: RequisicaoDeSolicitacaoDeTransporte) -> dict:
    motor = obter_motor()

    def executar() -> None:
        motor.autorizacoes.consumir(requisicao.id_autorizacao, "solicitar_transporte")
        motor.eventos.publicar(
            "carga_disponivel", motor.ciclo_atual, {"carga": requisicao.identificador_da_carga},
        )

    motor.enfileirar_comando(Comando("solicitar_transporte", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}
