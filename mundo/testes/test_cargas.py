from mundo.dominio.cargas import CargaMineral, clamp_qualidade


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
