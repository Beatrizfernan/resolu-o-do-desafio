from pathlib import Path

from mundo.dominio.minerais import CatalogoDeMinerais

CAMINHO_CATALOGO = Path(__file__).parent.parent / "config" / "minerais.json"


def test_carrega_catalogo_com_cinco_minerais():
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    assert len(catalogo.todos()) == 5


def test_obter_mineral_por_nome():
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    hematita = catalogo.obter("hematita")
    assert hematita.valor_por_unidade == 5.0


def test_obter_mineral_desconhecido_lanca_erro():
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    try:
        catalogo.obter("inexistente")
        assert False, "deveria ter lançado ValueError"
    except ValueError:
        pass
