from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mundo.dominio.cargas import LocalDaCarga
from mundo.motor.comandos import Comando

from .dependencias import obter_motor

router = APIRouter(prefix="/pesquisa", tags=["pesquisa"])
CENTRAL = "pesquisa"


@router.get("/em-andamento")
async def consultar_em_andamento() -> list[str]:
    motor = obter_motor()
    return list(motor.analises_em_andamento)


# Mantemos o endpoint /fila por retrocompatibilidade caso alguém o chame
@router.get("/fila")
async def consultar_fila() -> list[str]:
    motor = obter_motor()
    return list(motor.analises_em_andamento)


class RequisicaoDeAnalise(BaseModel):
    identificador_da_carga: str


class RequisicaoDeSondagem(BaseModel):
    identificador_da_jazida: str


@router.post("/iniciar-analise")
async def iniciar_analise(requisicao: RequisicaoDeAnalise) -> dict:
    motor = obter_motor()
    carga = motor.cargas.get(requisicao.identificador_da_carga)
    if carga is None:
        raise HTTPException(status_code=404, detail="Carga não encontrada")

    def executar() -> None:
        if not motor.energia.esta_operante(CENTRAL):
            raise ValueError(f"Central {CENTRAL} dormente")
            
        catalogo = motor.catalogo_de_pesquisa
        if len(motor.analises_em_andamento) >= catalogo.capacidade_paralela:
            raise ValueError("Centro de pesquisa ocupado")
            
        mineral = motor.catalogo_de_minerais.obter(carga.mineral)
        
        custo = catalogo.custo_base_de_analise * mineral.custo_extracao
        motor.energia.debitar(CENTRAL, custo)
        
        motor.analises_em_andamento.append(requisicao.identificador_da_carga)
        
        duracao = mineral.ciclos_de_analise
        ciclo_conclusao = motor.ciclo_atual + duracao

        def concluir() -> None:
            carga_em_analise = motor.cargas.get(requisicao.identificador_da_carga)
            if carga_em_analise is not None:
                carga_em_analise.analisada = True
            if requisicao.identificador_da_carga in motor.analises_em_andamento:
                motor.analises_em_andamento.remove(requisicao.identificador_da_carga)
                
            motor.eventos.publicar("analise_concluida", motor.ciclo_atual, {
                "carga": requisicao.identificador_da_carga,
            })

        motor.agendar_efeito(ciclo_conclusao, concluir)

    motor.enfileirar_comando(Comando("iniciar_analise", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


@router.post("/sondar-jazida")
async def sondar_jazida(requisicao: RequisicaoDeSondagem) -> dict:
    motor = obter_motor()
    jazida = motor.jazidas.get(requisicao.identificador_da_jazida)
    if jazida is None:
        raise HTTPException(status_code=404, detail="Jazida não encontrada")

    def executar() -> None:
        if not motor.energia.esta_operante(CENTRAL):
            raise ValueError(f"Central {CENTRAL} dormente")

        catalogo = motor.catalogo_de_pesquisa
        if len(motor.analises_em_andamento) >= catalogo.capacidade_paralela:
            raise ValueError("Centro de pesquisa ocupado")
        if jazida.composicao_estimada is not None:
            raise ValueError("Jazida já sondada")

        motor.energia.debitar(CENTRAL, catalogo.custo_base_de_analise)

        identificador_da_sondagem = f"jazida:{jazida.identificador}"
        motor.analises_em_andamento.append(identificador_da_sondagem)
        ciclo_conclusao = motor.ciclo_atual + 2

        def concluir() -> None:
            jazida.composicao_estimada = jazida.estimar_composicao()
            if identificador_da_sondagem in motor.analises_em_andamento:
                motor.analises_em_andamento.remove(identificador_da_sondagem)

            motor.eventos.publicar("sondagem_de_jazida_concluida", motor.ciclo_atual, {
                "jazida": jazida.identificador,
                "estimativa_de_composicao": jazida.composicao_estimada,
            })

        motor.agendar_efeito(ciclo_conclusao, concluir)

    motor.enfileirar_comando(Comando("sondar_jazida", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


@router.get("/jazidas/{identificador}/estimativa")
async def consultar_estimativa_da_jazida(identificador: str) -> dict:
    motor = obter_motor()
    jazida = motor.jazidas.get(identificador)
    if jazida is None:
        raise HTTPException(status_code=404, detail="Jazida não encontrada")
    if jazida.composicao_estimada is None:
        raise HTTPException(status_code=404, detail="Jazida ainda não sondada")

    return {
        "jazida": jazida.identificador,
        "mineral_predominante": jazida.mineral,
        "estimativa_de_composicao": jazida.composicao_estimada,
    }


@router.post("/classificar-carga")
async def classificar_carga(requisicao: RequisicaoDeAnalise) -> dict:
    motor = obter_motor()
    carga = motor.cargas.get(requisicao.identificador_da_carga)
    if carga is None:
        raise HTTPException(status_code=404, detail="Carga não encontrada")
        
    qualidade = carga.qualidade if carga.analisada else None
    return {"carga": carga.identificador, "mineral": carga.mineral, "qualidade": qualidade}


@router.post("/aprovar-carga")
async def aprovar_carga(requisicao: RequisicaoDeAnalise) -> dict:
    motor = obter_motor()

    def executar() -> None:
        carga = motor.cargas.get(requisicao.identificador_da_carga)
        if carga is None:
            raise ValueError("Carga não encontrada")
        if not carga.analisada:
            raise ValueError("Carga não analisada")
            
        limiar = motor.catalogo_de_pesquisa.limiar_qualidade_aprovacao
        if carga.qualidade < limiar:
            raise ValueError("Qualidade insuficiente para aprovação")
            
        motor.eventos.publicar("carga_aprovada", motor.ciclo_atual, {"carga": carga.identificador})

    motor.enfileirar_comando(Comando("aprovar_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


@router.post("/rejeitar-carga")
async def rejeitar_carga(requisicao: RequisicaoDeAnalise) -> dict:
    motor = obter_motor()

    def executar() -> None:
        carga = motor.cargas.get(requisicao.identificador_da_carga)
        if carga is None:
            raise ValueError("Carga não encontrada")
        if not carga.analisada:
            raise ValueError("Carga não analisada")
            
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
        carga = motor.cargas.get(requisicao.identificador_da_carga)
        if carga is None:
            raise ValueError("Carga não encontrada")
        if not carga.analisada:
            raise ValueError("Carga não analisada")
            
        if carga.local in (LocalDaCarga.EM_ARMAZEM, LocalDaCarga.EM_TRANSITO):
            raise ValueError("Só se distribui carga que não está guardada nem viajando")
            
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
