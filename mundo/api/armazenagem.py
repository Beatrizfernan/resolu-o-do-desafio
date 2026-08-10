from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mundo.dominio.armazens import CapacidadeExcedidaError, deslocamento_entre
from mundo.dominio.cargas import LocalDaCarga
from mundo.motor.comandos import Comando

from .dependencias import obter_motor

router = APIRouter(prefix="/armazenagem", tags=["armazenagem"])
CENTRAL = "armazenagem"
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
            # A pilha é a variável de decisão do sub-projeto inteiro, então
            # precisa ser legível. Sem isto o participante só a reconstruiria
            # acumulando eventos e refazendo a aritmética da reordenação por
            # conta própria — o que transformaria a decisão num exercício de
            # bookkeeping em vez de estratégia. Do fundo para o topo.
            "pilha": list(armazem.pilha),
        }
        for armazem in motor.armazens.values()
    ]


class RequisicaoDeRecebimento(BaseModel):
    identificador_do_armazem: str
    identificadores_das_cargas: list[str]
    nova_ordem: list[str] | None = None
    id_autorizacao: str


@router.post("/receber-carga")
async def receber_carga(requisicao: RequisicaoDeRecebimento) -> dict:
    motor = obter_motor()
    armazem = motor.armazens.get(requisicao.identificador_do_armazem)
    if armazem is None:
        raise HTTPException(status_code=404, detail="Armazém não encontrado")
    for identificador in requisicao.identificadores_das_cargas:
        if identificador not in motor.cargas:
            raise HTTPException(status_code=404, detail="Carga não encontrada")

    def executar() -> None:
        # Central dormente não opera. A verificação vem antes de tudo, como
        # todas as outras: o que pode falhar tem que falhar antes de mutar.
        if not motor.energia.esta_operante(CENTRAL):
            raise ValueError(f"Central {CENTRAL} dormente")
        motor.autorizacoes.consumir(requisicao.id_autorizacao, "receber_carga")
        custos = motor.catalogo_de_armazenagem

        # O pedido é checado contra si mesmo antes de qualquer outra coisa. Sem
        # isto, `empilhar` só descobre a repetição ao chegar na segunda
        # ocorrência — e a primeira já entrou. Uma carga repetida também seria
        # cobrada duas vezes antes de a operação ser rejeitada.
        vistos = set()
        for identificador in requisicao.identificadores_das_cargas:
            if identificador in vistos:
                raise ValueError(f"Carga repetida no pedido: {identificador}")
            if identificador in armazem.pilha:
                raise ValueError(f"Carga já está no armazém: {identificador}")
            vistos.add(identificador)

        # A capacidade é checada pelo volume do pedido inteiro, não carga a
        # carga. `empilhar` levantaria na primeira que não coubesse, deixando as
        # anteriores dentro da pilha — e o estrago aí não é só um rastro
        # parcial: a carga fica empilhada e marcada `na_mao`, então pode ser
        # entregue e sumir do mundo com o identificador ainda na pilha. A
        # ocupação nunca mais é liberada e toda retirada seguinte morre
        # procurando uma carga que não existe. O armazém fica inutilizável.
        volume = sum(
            motor.cargas[identificador].quantidade
            for identificador in requisicao.identificadores_das_cargas
        )
        if armazem.ocupacao + volume > armazem.capacidade:
            raise CapacidadeExcedidaError(armazem.identificador)

        total = 0.0
        for identificador in requisicao.identificadores_das_cargas:
            carga = motor.cargas[identificador]
            if not armazem.compativel_com(carga.mineral):
                motor.eventos.publicar(
                    "carga_contaminada",
                    motor.ciclo_atual,
                    {"carga": carga.identificador, "armazem": armazem.identificador},
                )
                raise ValueError("Mineral incompatível com o armazém")
            total += carga.quantidade * custos.custo_de_armazenagem_por_unidade

        # Tudo que pode falhar acontece antes de qualquer mutação: validar a
        # ordem, somar o custo inteiro e debitar. `executar()` roda dentro do
        # try do motor, então levantar aqui vira `operacao_invalida` e o tick
        # sobrevive — mas o que já tiver sido mutado **continua mutado**. Uma
        # falha depois de empilhar deixaria a carga na pilha, ocupando espaço,
        # e ainda marcada como estando na mão: dentro e fora do armazém ao
        # mesmo tempo, por uma operação que o mundo registrou como inválida.
        pilha_resultante = armazem.pilha + list(requisicao.identificadores_das_cargas)
        movimentos = 0
        if requisicao.nova_ordem is not None:
            # O deslocamento é aritmética pura sobre a pilha que ainda não
            # existe, justamente para o preço ser conhecido antes de mexer nela.
            movimentos = deslocamento_entre(pilha_resultante, requisicao.nova_ordem)
            total += movimentos * custos.custo_por_movimento

        motor.energia.debitar(CENTRAL, total)

        for identificador in requisicao.identificadores_das_cargas:
            armazem.empilhar(identificador, motor.cargas[identificador].quantidade)
        if requisicao.nova_ordem is not None:
            armazem.reordenar(requisicao.nova_ordem)
        for identificador in requisicao.identificadores_das_cargas:
            motor.cargas[identificador].mover_para(LocalDaCarga.EM_ARMAZEM)

        motor.eventos.publicar(
            "cargas_armazenadas",
            motor.ciclo_atual,
            {
                "armazem": armazem.identificador,
                "cargas": list(requisicao.identificadores_das_cargas),
                "movimentos": movimentos,
                "custo": total,
            },
        )
        if armazem.ocupacao >= armazem.capacidade:
            motor.eventos.publicar(
                "armazem_lotado", motor.ciclo_atual, {"armazem": armazem.identificador},
            )
        elif armazem.ocupacao >= armazem.capacidade * LIMIAR_PROXIMO_DA_CAPACIDADE:
            motor.eventos.publicar(
                "armazem_proximo_da_capacidade",
                motor.ciclo_atual,
                {"armazem": armazem.identificador},
            )

    motor.enfileirar_comando(Comando("receber_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeRetirada(BaseModel):
    identificador_do_armazem: str
    identificador_da_carga: str
    id_autorizacao: str


@router.post("/retirar-carga")
async def retirar_carga(requisicao: RequisicaoDeRetirada) -> dict:
    motor = obter_motor()
    armazem = motor.armazens.get(requisicao.identificador_do_armazem)
    if armazem is None:
        raise HTTPException(status_code=404, detail="Armazém não encontrado")
    if requisicao.identificador_da_carga not in motor.cargas:
        raise HTTPException(status_code=404, detail="Carga não encontrada")

    def executar() -> None:
        # Central dormente não opera. A verificação vem antes de tudo, como
        # todas as outras: o que pode falhar tem que falhar antes de mutar.
        if not motor.energia.esta_operante(CENTRAL):
            raise ValueError(f"Central {CENTRAL} dormente")
        motor.autorizacoes.consumir(requisicao.id_autorizacao, "retirar_carga")
        # A profundidade é medida antes de mexer na pilha: é ela que define o
        # preço, e depois de desempilhar não há mais o que medir.
        profundidade = armazem.profundidade(requisicao.identificador_da_carga)
        custo = profundidade * motor.catalogo_de_armazenagem.custo_por_desempilhamento
        # Retirar do topo é de graça, e `debitar` rejeita valor não-positivo:
        # cobrar zero derrubaria a operação inteira. É o caso comum de quem
        # guardou na ordem certa, e ele precisa ser o mais barato, não o único
        # que falha.
        if custo > 0.0:
            motor.energia.debitar(CENTRAL, custo)

        quantidades = {nome: motor.cargas[nome].quantidade for nome in armazem.pilha}
        removidos = armazem.desempilhar_ate(requisicao.identificador_da_carga, quantidades)
        for nome in removidos:
            motor.cargas[nome].mover_para(LocalDaCarga.NA_MAO)

        motor.eventos.publicar(
            "cargas_desempilhadas",
            motor.ciclo_atual,
            {
                "armazem": armazem.identificador,
                "alvo": requisicao.identificador_da_carga,
                "cargas": removidos,
                "profundidade": profundidade,
                "custo": custo,
            },
        )

    motor.enfileirar_comando(Comando("retirar_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeDescarte(BaseModel):
    identificador_da_carga: str


@router.post("/descartar-carga")
async def descartar_carga(requisicao: RequisicaoDeDescarte) -> dict:
    motor = obter_motor()
    if requisicao.identificador_da_carga not in motor.cargas:
        raise HTTPException(status_code=404, detail="Carga não encontrada")

    def executar() -> None:
        carga = motor.cargas[requisicao.identificador_da_carga]
        if carga.local != LocalDaCarga.NA_MAO:
            raise ValueError("Só se descarta carga que está na mão")
        del motor.cargas[requisicao.identificador_da_carga]
        motor.eventos.publicar("carga_descartada", motor.ciclo_atual, {"carga": carga.identificador})

    motor.enfileirar_comando(Comando("descartar_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeSolicitacaoDeTransporte(BaseModel):
    identificador_da_carga: str
    id_autorizacao: str


@router.post("/solicitar-transporte")
async def solicitar_transporte(requisicao: RequisicaoDeSolicitacaoDeTransporte) -> dict:
    motor = obter_motor()
    if requisicao.identificador_da_carga not in motor.cargas:
        raise HTTPException(status_code=404, detail="Carga não encontrada")

    def executar() -> None:
        motor.autorizacoes.consumir(requisicao.id_autorizacao, "solicitar_transporte")
        motor.eventos.publicar(
            "carga_disponivel", motor.ciclo_atual, {"carga": requisicao.identificador_da_carga},
        )

    motor.enfileirar_comando(Comando("solicitar_transporte", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}
