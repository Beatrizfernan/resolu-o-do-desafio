from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mundo.dominio.cargas import CargaMineral
from mundo.dominio.jazidas import EstadoDaJazida
from mundo.dominio.robos import EstadoDoRobo
from mundo.motor.comandos import Comando

from .dependencias import obter_motor

router = APIRouter(prefix="/extracao", tags=["extracao"])
CENTRAL = "extracao"
DURACAO_EXTRACAO_EM_CICLOS = 5
CUSTO_ENERGETICO_EXTRACAO = 2
QUALIDADE_INICIAL_DA_CARGA = 100.0


@router.get("/jazidas")
def consultar_jazidas() -> list[dict]:
    motor = obter_motor()
    return [
        {
            "identificador": jazida.identificador,
            "mineral": jazida.mineral,
            "estado": jazida.estado.value,
            "quantidade_disponivel": jazida.quantidade_disponivel,
        }
        for jazida in motor.jazidas.values()
    ]


@router.get("/jazidas/{identificador}")
def inspecionar_jazida(identificador: str) -> dict:
    motor = obter_motor()
    jazida = motor.jazidas.get(identificador)
    if jazida is None:
        raise HTTPException(status_code=404, detail="Jazida não encontrada")
    return {
        "identificador": jazida.identificador,
        "localizacao": jazida.localizacao,
        "mineral": jazida.mineral,
        "quantidade_disponivel": jazida.quantidade_disponivel,
        "dificuldade_extracao": jazida.dificuldade_extracao,
        "risco": jazida.risco,
        "estado": jazida.estado.value,
    }


class RequisicaoDeExtracao(BaseModel):
    identificador_da_unidade: str
    identificador_da_jazida: str
    quantidade: float


@router.post("/iniciar-extracao")
def iniciar_extracao(requisicao: RequisicaoDeExtracao) -> dict:
    motor = obter_motor()
    unidade = motor.robos.get(requisicao.identificador_da_unidade)
    jazida = motor.jazidas.get(requisicao.identificador_da_jazida)
    if unidade is None or jazida is None:
        raise HTTPException(status_code=404, detail="Unidade ou jazida não encontrada")

    def executar() -> None:
        if unidade.estado != EstadoDoRobo.DISPONIVEL:
            raise ValueError("Unidade indisponível")
        if jazida.estado != EstadoDaJazida.DISPONIVEL:
            raise ValueError("Jazida não disponível")
        motor.energia.debitar(CENTRAL, CUSTO_ENERGETICO_EXTRACAO)
        unidade.estado = EstadoDoRobo.EXECUTANDO
        ciclo_conclusao = motor.ciclo_atual + DURACAO_EXTRACAO_EM_CICLOS

        def concluir() -> None:
            jazida.extrair(requisicao.quantidade)
            unidade.estado = EstadoDoRobo.AGUARDANDO
            carga = CargaMineral(
                f"carga-{jazida.identificador}-{unidade.identificador}-{motor.ciclo_atual}",
                jazida.mineral,
                requisicao.quantidade,
                QUALIDADE_INICIAL_DA_CARGA,
            )
            motor.cargas[carga.identificador] = carga
            motor.eventos.publicar(
                "extracao_concluida",
                motor.ciclo_atual,
                {
                    "unidade": unidade.identificador,
                    "jazida": jazida.identificador,
                    "quantidade": requisicao.quantidade,
                    "carga": carga.identificador,
                },
            )

        motor.agendar_efeito(ciclo_conclusao, concluir)

    motor.enfileirar_comando(Comando("iniciar_extracao", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeUnidade(BaseModel):
    identificador_da_unidade: str


@router.post("/interromper-extracao")
def interromper_extracao(requisicao: RequisicaoDeUnidade) -> dict:
    motor = obter_motor()
    unidade = motor.robos.get(requisicao.identificador_da_unidade)
    if unidade is None:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")

    def executar() -> None:
        unidade.estado = EstadoDoRobo.RETORNANDO

    motor.enfileirar_comando(Comando("interromper_extracao", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


@router.post("/retornar-unidade")
def retornar_unidade(requisicao: RequisicaoDeUnidade) -> dict:
    motor = obter_motor()
    unidade = motor.robos.get(requisicao.identificador_da_unidade)
    if unidade is None:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")

    def executar() -> None:
        unidade.estado = EstadoDoRobo.DISPONIVEL

    motor.enfileirar_comando(Comando("retornar_unidade", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}
