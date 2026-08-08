from pathlib import Path

from mundo.dominio.cargas import CargaMineral, LocalDaCarga, clamp_qualidade
from mundo.dominio.minerais import CatalogoDeMinerais

CAMINHO_CATALOGO = Path(__file__).parent.parent / "config" / "minerais.json"


def _mineral(nome: str):
    return CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO).obter(nome)


def test_qualidade_e_clamped_ao_criar_acima_de_100():
    carga = CargaMineral(identificador="c1", mineral="hematita", quantidade=10.0, qualidade=150.0)
    assert carga.qualidade == 100.0


def test_qualidade_e_clamped_ao_criar_abaixo_de_0():
    carga = CargaMineral(identificador="c1", mineral="hematita", quantidade=10.0, qualidade=-5.0)
    assert carga.qualidade == 0.0


def test_degradar_reduz_qualidade():
    carga = CargaMineral(identificador="c1", mineral="hematita", quantidade=10.0, qualidade=50.0)
    carga.degradar(taxa_degradacao=10.0)
    assert carga.qualidade == 40.0


def test_degradar_nunca_abaixo_de_zero():
    carga = CargaMineral(identificador="c1", mineral="hematita", quantidade=10.0, qualidade=5.0)
    carga.degradar(taxa_degradacao=50.0)
    assert carga.qualidade == 0.0


def test_valor_efetivo_considera_qualidade():
    carga = CargaMineral(identificador="c1", mineral="hematita", quantidade=10.0, qualidade=50.0)
    assert carga.valor_efetivo(valor_por_unidade=5.0) == 25.0


def test_clamp_qualidade_funcao_isolada():
    assert clamp_qualidade(200) == 100
    assert clamp_qualidade(-10) == 0
    assert clamp_qualidade(42) == 42


def test_carga_nasce_em_jazida_com_multiplicador_neutro():
    carga = CargaMineral(identificador="c1", mineral="hematita", quantidade=10.0)
    assert carga.local == LocalDaCarga.EM_JAZIDA
    assert carga.mult_degradacao_local == 1.0


def test_sensibilidade_aplicavel_em_armazem():
    carga = CargaMineral("c1", "gelo_de_agua", 10.0, local=LocalDaCarga.EM_ARMAZEM)
    mineral = _mineral("gelo_de_agua")
    assert carga.sensibilidade_aplicavel(mineral) == mineral.sensibilidade_armazenagem


def test_sensibilidade_aplicavel_em_transito():
    carga = CargaMineral("c1", "gelo_de_agua", 10.0, local=LocalDaCarga.EM_TRANSITO)
    mineral = _mineral("gelo_de_agua")
    assert carga.sensibilidade_aplicavel(mineral) == mineral.sensibilidade_transporte


def test_sensibilidade_aplicavel_exposta_na_jazida_e_total():
    carga = CargaMineral("c1", "gelo_de_agua", 10.0, local=LocalDaCarga.EM_JAZIDA)
    assert carga.sensibilidade_aplicavel(_mineral("gelo_de_agua")) == 1.0
