from __future__ import annotations

from dataclasses import replace

from .catalogo import DEGRADACAO_PREFERENCIAL, MINERAIS, MODOS, PERFIS_PROIBIDOS_CRISTAL, RISCO_PREFERENCIAL
from .modelos import CandidatoDeTransporte, CargaDisponivel, UnidadeProjetada


def valor_bruto(carga: CargaDisponivel) -> float:
    return carga.quantidade * MINERAIS[carga.mineral].valor


def perda_por_espera(carga: CargaDisponivel) -> float:
    perfil = MINERAIS[carga.mineral]
    return valor_bruto(carga) * perfil.taxa_degradacao * 2.0 / 100


def chave_da_fila(carga: CargaDisponivel, ciclo_atual: int) -> tuple:
    return (
        MINERAIS[carga.mineral].prioridade,
        -perda_por_espera(carga),
        -(ciclo_atual - carga.ciclo_de_entrada),
        -valor_bruto(carga),
        carga.identificador,
    )


def ordenar_fila(cargas: list[CargaDisponivel], ciclo_atual: int) -> list[CargaDisponivel]:
    return sorted(cargas, key=lambda carga: chave_da_fila(carga, ciclo_atual))


def escolher_carga(
    cargas: list[CargaDisponivel],
    ciclo_atual: int,
    despachos_raros_consecutivos: int,
    viagens_restantes: int,
) -> CargaDisponivel | None:
    fila = ordenar_fila(cargas, ciclo_atual)
    if not fila:
        return None
    if fila[0].mineral == "cristal_marciano_raro":
        return fila[0]
    raras = [c for c in fila if MINERAIS[c.mineral].prioridade <= 2]
    comuns = [c for c in fila if MINERAIS[c.mineral].prioridade >= 3]
    if raras and comuns and despachos_raros_consecutivos >= 3 and viagens_restantes > len(raras) + 1:
        return max(comuns, key=lambda carga: ciclo_atual - carga.ciclo_de_entrada)
    if raras:
        return raras[0]
    return fila[0]


def destino_para(carga: CargaDisponivel, armazem_de_cristais: str, ciclo_atual: int) -> dict:
    prioridade = f"P{MINERAIS[carga.mineral].prioridade}"
    if carga.mineral == "cristal_marciano_raro":
        return {
            "prioridade": prioridade,
            "destino_primario": "pesquisa",
            "destino_fallback": "armazenagem",
            "armazem_recomendado": armazem_de_cristais,
            "motivo": "CRISTAL_PESQUISA_DIRETA",
            "ciclo_limite_recomendado": ciclo_atual,
        }
    if carga.mineral in {"jarosita", "gelo_de_agua"}:
        return {
            "prioridade": prioridade,
            "destino_primario": "pesquisa",
            "destino_fallback": "armazenagem",
            "armazem_recomendado": "armazem-1",
            "motivo": "RARO_PRIORIZADO",
            "ciclo_limite_recomendado": ciclo_atual + 1,
        }
    return {
        "prioridade": prioridade,
        "destino_primario": "pesquisa",
        "destino_fallback": "armazenagem",
        "armazem_recomendado": "armazem-1",
        "motivo": "COMUM_FLUXO_CONSTANTE",
        "ciclo_limite_recomendado": ciclo_atual + 4,
    }


def montar_candidatos(
    carga: CargaDisponivel,
    unidades: list[UnidadeProjetada],
    rotas: list[dict],
) -> list[CandidatoDeTransporte]:
    perfil = MINERAIS[carga.mineral]
    candidatos: list[CandidatoDeTransporte] = []
    for unidade in unidades:
        if unidade.estado != "disponivel" or unidade.viagens_restantes <= 0:
            continue
        for rota in rotas:
            if rota["condicao"] != "livre":
                continue
            if rota["capacidade_maxima"] < carga.quantidade:
                continue
            if carga.mineral == "cristal_marciano_raro" and rota["perfil"] in PERFIS_PROIBIDOS_CRISTAL:
                continue
            for nome_do_modo in perfil.modos:
                modo = MODOS[nome_do_modo]
                duracao = max(1, round(rota["tempo_base"] * modo.mult_duracao))
                fator_raridade = 1 + perfil.raridade * 30
                perda_qualidade = (
                    perfil.taxa_degradacao
                    * perfil.sensibilidade_transporte
                    * modo.mult_degradacao
                    * rota["multiplicador_degradacao"]
                    * fator_raridade
                    * duracao
                )
                perda_qualidade = min(100.0, perda_qualidade)
                energia = rota["custo_energia_base"] * modo.mult_energia * (1 + unidade.desgaste * 0.65)
                desgaste = (1 / modo.mult_duracao) * rota["multiplicador_desgaste"]
                candidatos.append(
                    CandidatoDeTransporte(
                        carga=carga,
                        unidade=unidade,
                        rota=rota,
                        modo=nome_do_modo,
                        duracao=duracao,
                        energia=energia,
                        perda_de_valor=valor_bruto(carga) * perda_qualidade / 100,
                        risco=rota["risco"],
                        desgaste=desgaste,
                    )
                )
    return candidatos


def escolher_candidato(
    carga: CargaDisponivel,
    unidades: list[UnidadeProjetada],
    rotas: list[dict],
    exigir_preferencial: bool = True,
) -> CandidatoDeTransporte | None:
    candidatos = montar_candidatos(carga, unidades, rotas)
    if not candidatos:
        return None
    prioridade = MINERAIS[carga.mineral].prioridade
    preferenciais = [
        c for c in candidatos
        if c.risco <= RISCO_PREFERENCIAL[prioridade]
        and c.rota["multiplicador_degradacao"] <= DEGRADACAO_PREFERENCIAL[prioridade]
    ]
    if preferenciais:
        candidatos = preferenciais
    elif exigir_preferencial and carga.mineral != "cristal_marciano_raro":
        candidatos = candidatos
    return _pontuar(candidatos)[0]


def _pontuar(candidatos: list[CandidatoDeTransporte]) -> list[CandidatoDeTransporte]:
    def normalizar(nome: str) -> list[float]:
        valores = [getattr(c, nome) for c in candidatos]
        menor, maior = min(valores), max(valores)
        if menor == maior:
            return [0.0 for _ in candidatos]
        return [(getattr(c, nome) - menor) / (maior - menor) for c in candidatos]

    energia = normalizar("energia")
    perda = normalizar("perda_de_valor")
    risco = normalizar("risco")
    desgaste = normalizar("desgaste")
    duracao = normalizar("duracao")
    pontuados = []
    for indice, candidato in enumerate(candidatos):
        pesos = MINERAIS[candidato.carga.mineral].pesos
        score = (
            pesos[0] * energia[indice]
            + pesos[1] * perda[indice]
            + pesos[2] * risco[indice]
            + pesos[3] * desgaste[indice]
            + pesos[4] * duracao[indice]
        )
        pontuados.append(replace(candidato, score=score))
    return sorted(
        pontuados,
        key=lambda c: (
            c.score,
            c.risco,
            c.perda_de_valor,
            c.energia,
            c.desgaste,
            c.rota["identificador"],
            c.unidade.identificador,
        ),
    )
