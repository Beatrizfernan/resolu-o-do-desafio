from pathlib import Path

import pytest

from mundo.dominio.operacao import CatalogoDeOperacao

CAMINHO = Path(__file__).parent.parent / "config" / "operacao.json"


def test_carrega_os_dois_custos_do_arquivo():
    catalogo = CatalogoDeOperacao.carregar_de_arquivo(CAMINHO)

    assert catalogo.consumo_por_ciclo_da_central == 0.05
    assert catalogo.custo_de_autorizacao == 0.2


def test_o_saldo_inicial_de_uma_central_dura_cerca_de_duzentos_ciclos():
    """É esta razão que decide quando a armadilha dispara.

    Uma central começa com 10. Se o consumo faz isso durar muito, a
    armadilha nunca dispara e o mecanismo é decorativo; se durar pouco, o
    mundo vira punitivo. Duzentos ciclos é cerca de metade de uma execução
    típica — tarde o bastante para o participante desatento já ter se
    comprometido, cedo o bastante para ainda restar execução a perder.
    """
    catalogo = CatalogoDeOperacao.carregar_de_arquivo(CAMINHO)

    assert 10.0 / catalogo.consumo_por_ciclo_da_central == pytest.approx(200.0)


def test_autorizacao_custa_alguns_ciclos_de_existencia():
    """A autorização precisa pesar mais que existir, e muito menos que operar.

    Se custasse menos que um ciclo de consumo, agrupar operações não valeria
    a pena. Se custasse como uma extração, autorizar viraria a despesa
    principal e o resto do mundo perderia relevância.
    """
    catalogo = CatalogoDeOperacao.carregar_de_arquivo(CAMINHO)
    ciclos_equivalentes = catalogo.custo_de_autorizacao / catalogo.consumo_por_ciclo_da_central

    assert 2.0 <= ciclos_equivalentes <= 10.0
