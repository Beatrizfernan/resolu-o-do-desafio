from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mundo.dominio.cargas import LocalDaCarga
from mundo.dominio.modos import ModoDeTransporte
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
            "tempo_base": rota.tempo_base,
            "perfil": rota.perfil,
            "tipo": "fixa" if rota.fixa else "variante",
            "vantagem": rota.vantagem,
            "desvantagem": rota.desvantagem,
            "custo_energia_base": rota.custo_energia_base,
            "multiplicador_degradacao": rota.multiplicador_degradacao,
            "multiplicador_desgaste": rota.multiplicador_desgaste,
            "capacidade_maxima": rota.capacidade_maxima,
            "risco": rota.risco,
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
            "qualidade": carga.qualidade if carga.analisada else None,
        }
        for carga in motor.cargas.values()
    ]


@router.get("/planejar-transporte")
async def planejar_transporte(identificador_da_carga: str) -> dict:
    motor = obter_motor()
    carga = motor.cargas.get(identificador_da_carga)
    if carga is None:
        raise HTTPException(status_code=404, detail="Carga não encontrada")
    origem_compativel = None
    if carga.local == LocalDaCarga.EM_JAZIDA and carga.origem_jazida is not None:
        jazida = motor.jazidas.get(carga.origem_jazida)
        if jazida is not None:
            origem_compativel = jazida.localizacao
    rotas_livres = [
        rota.identificador
        for rota in motor.rotas.values()
        if rota.condicao == CondicaoDaRota.LIVRE
        and rota.capacidade_maxima >= carga.quantidade
        and (origem_compativel is None or rota.origem == origem_compativel)
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
    modo: ModoDeTransporte = ModoDeTransporte.NORMAL


@router.post("/iniciar-viagem")
async def iniciar_viagem(requisicao: RequisicaoDeViagem) -> dict:
    motor = obter_motor()
    unidade = motor.robos.get(requisicao.identificador_da_unidade)
    rota = motor.rotas.get(requisicao.identificador_da_rota)
    if unidade is None or rota is None:
        raise HTTPException(status_code=404, detail="Unidade ou rota não encontrada")
    if motor.cargas.get(requisicao.identificador_da_carga) is None:
        raise HTTPException(status_code=404, detail="Carga não encontrada")

    def executar() -> None:
        # Central dormente não opera. A verificação vem antes de tudo, como
        # todas as outras: o que pode falhar tem que falhar antes de mutar.
        if not motor.energia.esta_operante(CENTRAL):
            raise ValueError(f"Central {CENTRAL} dormente")
        motor.autorizacoes.consumir(requisicao.id_autorizacao, "iniciar_viagem")
        if rota.condicao != CondicaoDaRota.LIVRE:
            raise ValueError("Rota interditada")
        if unidade.viagens_disponiveis <= 0:
            raise ValueError("Sem viagens disponíveis")
        carga = motor.cargas[requisicao.identificador_da_carga]
        # O que bloqueia é estar **guardado**, não estar fora da mão. Exigir
        # NA_MAO tornaria o armazém etapa obrigatória: minério recém-extraído
        # nasce EM_JAZIDA, e nenhum caminho leva de lá à mão sem passar por
        # guardar e desenterrar. O armazém tem que ser escolha contra a
        # alternativa de despachar direto — se toda produção fosse obrigada a
        # passar por ele, o custo incidiria igual sobre qualquer estratégia e
        # deixaria de distinguir uma da outra.
        if carga.local in (LocalDaCarga.EM_ARMAZEM, LocalDaCarga.EM_TRANSITO):
            raise ValueError("Só se transporta carga que não está guardada nem viajando")
        if carga.local == LocalDaCarga.EM_JAZIDA and carga.origem_jazida is not None:
            jazida_de_origem = motor.jazidas.get(carga.origem_jazida)
            if jazida_de_origem is None:
                raise ValueError("Jazida de origem da carga não encontrada")
            if rota.origem != jazida_de_origem.localizacao:
                raise ValueError("Rota incompatível com a origem da carga")
        if carga.quantidade > unidade.capacidade:
            raise ValueError("Capacidade da unidade excedida")
        if carga.quantidade > rota.capacidade_maxima:
            raise ValueError("Carga excede a capacidade da rota")
        perfil = motor.catalogo_de_modos.obter_transporte(requisicao.modo)
        custo = (
            rota.custo_energia_base
            * perfil.mult_energia
            * motor.catalogo_de_modos.fator_de_desgaste(unidade.desgaste)
        )
        motor.energia.debitar(CENTRAL, custo)
        # O desgaste segue o ritmo de operação, não a energia gasta: quem opera
        # em ciclos mais curtos castiga mais a máquina por unidade de tempo.
        unidade.desgaste += (
            motor.catalogo_de_modos.taxa_de_desgaste
            / perfil.mult_duracao
            * rota.multiplicador_desgaste
        )
        unidade.viagens_disponiveis -= 1
        unidade.estado = EstadoDoRobo.EXECUTANDO
        local_de_origem = carga.local
        carga.mover_para(
            LocalDaCarga.EM_TRANSITO,
            perfil.mult_degradacao * rota.multiplicador_degradacao,
        )
        duracao = max(1, round(rota.tempo_base * perfil.mult_duracao))
        ciclo_chegada = motor.ciclo_atual + duracao

        def concluir() -> None:
            if unidade.estado != EstadoDoRobo.EXECUTANDO:
                # A viagem não aconteceu: a carga volta para onde saiu, sem o
                # multiplicador do modo. Deixá-la em trânsito a condenaria a
                # degradar até zero sem nenhum caminho de recuperação.
                carga_abortada = motor.cargas.get(requisicao.identificador_da_carga)
                if carga_abortada is not None:
                    carga_abortada.mover_para(local_de_origem)
                motor.eventos.publicar(
                    "viagem_abortada",
                    motor.ciclo_atual,
                    {
                        "unidade": unidade.identificador,
                        "carga": requisicao.identificador_da_carga,
                    },
                )
                return
            carga_em_transito = motor.cargas[requisicao.identificador_da_carga]
            carga_em_transito.mover_para(LocalDaCarga.NA_MAO)
            unidade.estado = EstadoDoRobo.RETORNANDO
            motor.eventos.publicar(
                "transporte_concluido",
                motor.ciclo_atual,
                {
                    "unidade": unidade.identificador,
                    "carga": carga_em_transito.identificador,
                    "modo": requisicao.modo.value,
                    "desgaste_da_unidade": unidade.desgaste,
                },
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
