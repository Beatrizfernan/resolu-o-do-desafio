"""Cada modo precisa vencer em pelo menos um cenário.

Se um destes testes falhar após uma recalibração de `modos.json`, o modo
citado deixou de ter razão de existir: nenhuma estratégia o escolheria.
"""
from pathlib import Path

from mundo.dominio.cargas import CargaMineral, LocalDaCarga
from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.dominio.modos import CatalogoDeModos, ModoDeExtracao, ModoDeTransporte

CAMINHO_MINERAIS = Path(__file__).parent.parent / "config" / "minerais.json"
CAMINHO_MODOS = Path(__file__).parent.parent / "config" / "modos.json"

MINERAIS = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_MINERAIS)
MODOS = CatalogoDeModos.carregar_de_arquivo(CAMINHO_MODOS)

QUANTIDADE = 10.0


def _retorno_da_extracao(nome_do_mineral: str, modo: ModoDeExtracao) -> float:
    """Valor entregue por energia gasta, penalizado pelo minério destruído.

    O minério destruído é cobrado acima do preço de tabela, com peso
    `1 + raridade`: uma jazida é finita e irreponível, então queimar cristal
    marciano raro custa quase o dobro do seu valor de venda, enquanto
    desperdiçar hematita custa praticamente só o valor de face. É essa
    ponderação que faz a métrica depender do mineral — sem ela o
    `valor_por_unidade` se cancela na razão e um único modo venceria sempre.
    """
    mineral = MINERAIS.obter(nome_do_mineral)
    perfil = MODOS.obter_extracao(modo)
    energia = (
        mineral.custo_extracao * QUANTIDADE * MODOS.fator_base_de_energia * perfil.mult_energia
    )
    carga = CargaMineral("c", nome_do_mineral, QUANTIDADE, perfil.qualidade_inicial)
    valor = carga.valor_efetivo(mineral.valor_por_unidade)
    desperdicado = QUANTIDADE * (perfil.fator_desperdicio - 1.0)
    valor_perdido = desperdicado * mineral.valor_por_unidade * (1.0 + mineral.raridade)
    return (valor - valor_perdido) / energia


def _melhor_modo_de_extracao(nome_do_mineral: str) -> ModoDeExtracao:
    return max(ModoDeExtracao, key=lambda modo: _retorno_da_extracao(nome_do_mineral, modo))


def _qualidade_apos_viagem(
    nome_do_mineral: str, modo: ModoDeTransporte, tempo_base: int,
) -> float:
    mineral = MINERAIS.obter(nome_do_mineral)
    perfil = MODOS.obter_transporte(modo)
    carga = CargaMineral(
        "c", nome_do_mineral, QUANTIDADE, 100.0, local=LocalDaCarga.EM_TRANSITO,
    )
    ciclos = max(1, round(tempo_base * perfil.mult_duracao))
    perda_por_ciclo = (
        mineral.taxa_degradacao
        * carga.sensibilidade_aplicavel(mineral)
        * MODOS.mult_do_local("em_transito")
        * perfil.mult_degradacao
    )
    for _ in range(ciclos):
        carga.degradar(taxa_degradacao=perda_por_ciclo)
    return carga.qualidade


def _retorno_do_transporte(
    nome_do_mineral: str, modo: ModoDeTransporte, tempo_base: int, custo_base: float,
) -> float:
    mineral = MINERAIS.obter(nome_do_mineral)
    perfil = MODOS.obter_transporte(modo)
    qualidade = _qualidade_apos_viagem(nome_do_mineral, modo, tempo_base)
    valor = QUANTIDADE * mineral.valor_por_unidade * (qualidade / 100)
    return valor / (custo_base * perfil.mult_energia)


def _melhor_modo_de_transporte(
    nome_do_mineral: str, tempo_base: int, custo_base: float = 3.0,
) -> ModoDeTransporte:
    return max(
        ModoDeTransporte,
        key=lambda modo: _retorno_do_transporte(nome_do_mineral, modo, tempo_base, custo_base),
    )


def test_cuidadoso_vence_em_mineral_caro_e_escasso():
    assert _melhor_modo_de_extracao("cristal_marciano_raro") == ModoDeExtracao.CUIDADOSO


def test_agressivo_vence_em_mineral_barato():
    assert _melhor_modo_de_extracao("hematita") == ModoDeExtracao.AGRESSIVO


def test_todo_modo_de_extracao_vence_em_algum_mineral_do_catalogo():
    vencedores = {_melhor_modo_de_extracao(m.nome) for m in MINERAIS.todos()}
    ausentes = set(ModoDeExtracao) - vencedores
    assert not ausentes, f"modos de extração que nunca vencem: {ausentes}"


def test_rapido_vence_transportando_mineral_sensivel_em_rota_longa():
    assert _melhor_modo_de_transporte("gelo_de_agua", tempo_base=20) == ModoDeTransporte.RAPIDO


def test_economico_vence_transportando_mineral_estavel():
    assert _melhor_modo_de_transporte("hematita", tempo_base=5) == ModoDeTransporte.ECONOMICO


def test_todo_modo_de_transporte_vence_em_alguma_combinacao():
    vencedores = set()
    for mineral in MINERAIS.todos():
        for tempo_base in (3, 5, 8, 12, 20, 30):
            vencedores.add(_melhor_modo_de_transporte(mineral.nome, tempo_base))
    ausentes = set(ModoDeTransporte) - vencedores
    assert not ausentes, f"modos de transporte que nunca vencem: {ausentes}"
