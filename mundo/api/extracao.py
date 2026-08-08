from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mundo.dominio.cargas import CargaMineral, LocalDaCarga
from mundo.dominio.jazidas import EstadoDaJazida
from mundo.dominio.modos import ModoDeExtracao
from mundo.dominio.robos import EstadoDoRobo
from mundo.motor.comandos import Comando

from .dependencias import obter_motor

router = APIRouter(prefix="/extracao", tags=["extracao"])
CENTRAL = "extracao"
DURACAO_EXTRACAO_EM_CICLOS = 5


@router.get("/jazidas")
async def consultar_jazidas() -> list[dict]:
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
async def inspecionar_jazida(identificador: str) -> dict:
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
    modo: ModoDeExtracao = ModoDeExtracao.NORMAL


@router.post("/iniciar-extracao")
async def iniciar_extracao(requisicao: RequisicaoDeExtracao) -> dict:
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
        perfil = motor.catalogo_de_modos.obter_extracao(requisicao.modo)
        mineral = motor.catalogo_de_minerais.obter(jazida.mineral)
        custo = (
            mineral.custo_extracao
            * requisicao.quantidade
            * motor.catalogo_de_modos.fator_base_de_energia
            * perfil.mult_energia
        )
        motor.energia.debitar(CENTRAL, custo)
        unidade.estado = EstadoDoRobo.EXECUTANDO
        duracao = max(1, round(DURACAO_EXTRACAO_EM_CICLOS * perfil.mult_duracao))
        ciclo_conclusao = motor.ciclo_atual + duracao

        def concluir() -> None:
            consumido = requisicao.quantidade * perfil.fator_desperdicio
            jazida.extrair(consumido)
            unidade.estado = EstadoDoRobo.AGUARDANDO
            carga = CargaMineral(
                f"carga-{jazida.identificador}-{unidade.identificador}-{motor.ciclo_atual}",
                jazida.mineral,
                requisicao.quantidade,
                perfil.qualidade_inicial,
                local=LocalDaCarga.EM_JAZIDA,
            )
            motor.cargas[carga.identificador] = carga
            motor.eventos.publicar(
                "extracao_concluida",
                motor.ciclo_atual,
                {
                    "unidade": unidade.identificador,
                    "jazida": jazida.identificador,
                    "quantidade": requisicao.quantidade,
                    "quantidade_consumida_da_jazida": consumido,
                    "modo": requisicao.modo.value,
                    "carga": carga.identificador,
                },
            )

        motor.agendar_efeito(ciclo_conclusao, concluir)

    motor.enfileirar_comando(Comando("iniciar_extracao", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeUnidade(BaseModel):
    identificador_da_unidade: str


@router.post("/interromper-extracao")
async def interromper_extracao(requisicao: RequisicaoDeUnidade) -> dict:
    motor = obter_motor()
    unidade = motor.robos.get(requisicao.identificador_da_unidade)
    if unidade is None:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")

    def executar() -> None:
        unidade.estado = EstadoDoRobo.RETORNANDO

    motor.enfileirar_comando(Comando("interromper_extracao", CENTRAL, requisicao.model_dump(), executar))
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
