from __future__ import annotations

from statistics import median

from mundo.api.dependencias import obter_motor

from avaliador.dominio.relatorio_de_avaliacao import RelatorioDeAvaliacao
from avaliador.dominio.resultado_da_seed import ResultadoDaSeed
from avaliador.dominio.status_de_avaliacao import StatusDeAvaliacao


def coletar_resultado_da_seed(
    seed: int,
    cliente,
    status: StatusDeAvaliacao,
    erro_operacional: str | None = None,
) -> ResultadoDaSeed:
    del cliente
    motor = obter_motor()
    eventos = motor.eventos.consultar_eventos(0)
    energia_encalhada = sum(motor.energia._saldos.values())
    return ResultadoDaSeed(
        seed=seed,
        status=status,
        ciclo_final=motor.ciclo_atual,
        faturamento_total=motor.faturamento_total,
        energia_encalhada=energia_encalhada,
        operacoes_invalidas=sum(1 for evento in eventos if evento.tipo == "operacao_invalida"),
        autorizacoes_emitidas=len(motor.autorizacoes._autorizacoes),
        cargas_entregues=sum(1 for evento in eventos if evento.tipo == "distribuicao_preparada"),
        cargas_analisadas=sum(1 for evento in eventos if evento.tipo == "analise_concluida"),
        jazidas_esgotadas=sum(1 for jazida in motor.jazidas.values() if jazida.estado.value == "esgotada"),
        erro_operacional=erro_operacional,
    )


def agregar_resultados(
    resultados: list[ResultadoDaSeed],
    integridade_aprovada: bool,
    divergencias: list[str],
    configuracao: dict,
) -> RelatorioDeAvaliacao:
    faturamentos = [resultado.faturamento_total for resultado in resultados] or [0.0]
    ciclos = [resultado.ciclo_final for resultado in resultados] or [0.0]
    energias = [resultado.energia_encalhada for resultado in resultados] or [0.0]
    falhas_operacionais = [
        resultado for resultado in resultados if resultado.status == StatusDeAvaliacao.FALHA_OPERACIONAL
    ]
    return RelatorioDeAvaliacao(
        integridade_aprovada=integridade_aprovada,
        divergencias_de_integridade=divergencias,
        configuracao=configuracao,
        resultados=sorted(resultados, key=lambda resultado: resultado.seed),
        faturamento_medio=sum(faturamentos) / len(faturamentos),
        faturamento_mediano=median(faturamentos),
        ciclo_medio_de_encerramento=sum(ciclos) / len(ciclos),
        energia_encalhada_media=sum(energias) / len(energias),
        taxa_de_falha_operacional=(len(falhas_operacionais) / len(resultados)) if resultados else 0.0,
    )
