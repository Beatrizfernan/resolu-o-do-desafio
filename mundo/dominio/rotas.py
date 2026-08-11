from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CondicaoDaRota(str, Enum):
    LIVRE = "livre"
    INTERDITADA = "interditada"


@dataclass(frozen=True)
class PerfilDeRota:
    nome: str
    vantagem: str
    desvantagem: str
    ajuste_de_distancia: float
    ajuste_de_tempo: int
    custo_energia_base: float
    multiplicador_degradacao: float
    multiplicador_desgaste: float
    capacidade_maxima: float
    risco: float


@dataclass
class Rota:
    identificador: str
    origem: str
    destino: str
    distancia: float
    tempo_base: int
    risco: float
    custo_energia_base: float = 3.0
    multiplicador_degradacao: float = 1.0
    multiplicador_desgaste: float = 1.0
    capacidade_maxima: float = 100.0
    fixa: bool = True
    perfil: str = "padrao"
    vantagem: str = "Equilibrada e previsível"
    desvantagem: str = "Não se destaca em custo, desgaste nem preservação"
    condicao: CondicaoDaRota = CondicaoDaRota.LIVRE


def catalogo_de_perfis_variantes() -> list[PerfilDeRota]:
    return [
        PerfilDeRota(
            nome="blindada",
            vantagem="Preserva melhor a qualidade do material",
            desvantagem="Consome mais energia e tem capacidade menor",
            ajuste_de_distancia=4.0,
            ajuste_de_tempo=2,
            custo_energia_base=4.8,
            multiplicador_degradacao=0.45,
            multiplicador_desgaste=1.1,
            capacidade_maxima=80.0,
            risco=0.04,
        ),
        PerfilDeRota(
            nome="economica",
            vantagem="Baixo custo energético por viagem",
            desvantagem="Degrada mais o material durante o trajeto",
            ajuste_de_distancia=-1.0,
            ajuste_de_tempo=1,
            custo_energia_base=2.0,
            multiplicador_degradacao=1.35,
            multiplicador_desgaste=0.9,
            capacidade_maxima=100.0,
            risco=0.05,
        ),
        PerfilDeRota(
            nome="turbo",
            vantagem="Chega mais rápido ao destino",
            desvantagem="Gera desgaste alto na transportadora",
            ajuste_de_distancia=1.0,
            ajuste_de_tempo=-2,
            custo_energia_base=4.2,
            multiplicador_degradacao=0.75,
            multiplicador_desgaste=1.8,
            capacidade_maxima=90.0,
            risco=0.09,
        ),
        PerfilDeRota(
            nome="pesada",
            vantagem="Aceita cargas maiores sem penalidade de rota",
            desvantagem="Exige mais energia e degrada um pouco mais",
            ajuste_de_distancia=3.0,
            ajuste_de_tempo=1,
            custo_energia_base=4.0,
            multiplicador_degradacao=1.1,
            multiplicador_desgaste=1.2,
            capacidade_maxima=140.0,
            risco=0.07,
        ),
        PerfilDeRota(
            nome="tecnica",
            vantagem="Minimiza degradação em materiais delicados",
            desvantagem="Castiga fortemente a transportadora",
            ajuste_de_distancia=2.0,
            ajuste_de_tempo=0,
            custo_energia_base=4.5,
            multiplicador_degradacao=0.55,
            multiplicador_desgaste=2.2,
            capacidade_maxima=70.0,
            risco=0.06,
        ),
        PerfilDeRota(
            nome="abrasiva",
            vantagem="É curta e relativamente barata",
            desvantagem="Aumenta bastante a degradação da carga",
            ajuste_de_distancia=-2.0,
            ajuste_de_tempo=-1,
            custo_energia_base=2.6,
            multiplicador_degradacao=1.7,
            multiplicador_desgaste=1.0,
            capacidade_maxima=110.0,
            risco=0.07,
        ),
        PerfilDeRota(
            nome="panoramica",
            vantagem="Poupa a transportadora e preserva razoavelmente a carga",
            desvantagem="Leva mais tempo para concluir a viagem",
            ajuste_de_distancia=5.0,
            ajuste_de_tempo=2,
            custo_energia_base=3.2,
            multiplicador_degradacao=0.85,
            multiplicador_desgaste=0.8,
            capacidade_maxima=100.0,
            risco=0.03,
        ),
        PerfilDeRota(
            nome="corredor_frio",
            vantagem="Boa preservação para materiais sensíveis",
            desvantagem="Custo energético acima da média",
            ajuste_de_distancia=2.0,
            ajuste_de_tempo=0,
            custo_energia_base=3.9,
            multiplicador_degradacao=0.65,
            multiplicador_desgaste=1.4,
            capacidade_maxima=85.0,
            risco=0.05,
        ),
        PerfilDeRota(
            nome="manutencao_leve",
            vantagem="Reduz desgaste acumulado da transportadora",
            desvantagem="Viagem mais lenta e com degradação um pouco maior",
            ajuste_de_distancia=1.0,
            ajuste_de_tempo=1,
            custo_energia_base=3.4,
            multiplicador_degradacao=1.1,
            multiplicador_desgaste=0.55,
            capacidade_maxima=95.0,
            risco=0.04,
        ),
        PerfilDeRota(
            nome="expressa_fragil",
            vantagem="Tempo base muito baixo",
            desvantagem="Capacidade baixa e degradação alta",
            ajuste_de_distancia=0.0,
            ajuste_de_tempo=-3,
            custo_energia_base=3.6,
            multiplicador_degradacao=1.45,
            multiplicador_desgaste=1.9,
            capacidade_maxima=75.0,
            risco=0.08,
        ),
    ]
