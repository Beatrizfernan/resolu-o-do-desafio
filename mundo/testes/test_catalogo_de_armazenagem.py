from pathlib import Path

import pytest

from mundo.dominio.armazenagem import CatalogoDeArmazenagem

CAMINHO = Path(__file__).parent.parent / "config" / "armazenagem.json"


def test_carrega_os_quatro_custos_do_arquivo():
    catalogo = CatalogoDeArmazenagem.carregar_de_arquivo(CAMINHO)

    assert catalogo.custo_de_armazenagem_por_unidade == 0.05
    assert catalogo.custo_de_manutencao_por_unidade == 0.004
    assert catalogo.custo_por_movimento == 0.3
    assert catalogo.custo_por_desempilhamento == 0.8


def test_guardar_vinte_unidades_custa_o_mesmo_que_a_taxa_fixa_antiga():
    """A mudança não pode encarecer o caso simples.

    Antes, receber uma carga custava 1 de energia fixo. Vinte unidades a
    0.05 dão exatamente 1.0, então quem não usa a pilha não paga a mais.
    """
    catalogo = CatalogoDeArmazenagem.carregar_de_arquivo(CAMINHO)

    assert catalogo.custo_de_armazenagem_por_unidade * 20.0 == pytest.approx(1.0)
