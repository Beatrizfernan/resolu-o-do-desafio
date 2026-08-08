import pytest

from mundo.dominio.jazidas import EstadoDaJazida, Jazida, TransicaoDeEstadoInvalidaError


def _criar_jazida(estado=EstadoDaJazida.DISPONIVEL, quantidade=100.0) -> Jazida:
    return Jazida(
        identificador="j1", localizacao="setor-1", mineral="hematita",
        quantidade_disponivel=quantidade, dificuldade_extracao=1.0, risco=0.1, estado=estado,
    )


def test_extrair_reduz_quantidade_disponivel():
    jazida = _criar_jazida(quantidade=100.0)
    jazida.extrair(30.0)
    assert jazida.quantidade_disponivel == 70.0


def test_extrair_ate_esgotar_transiciona_estado():
    jazida = _criar_jazida(quantidade=10.0)
    jazida.extrair(10.0)
    assert jazida.estado == EstadoDaJazida.ESGOTADA


def test_extrair_alem_do_disponivel_lanca_erro():
    jazida = _criar_jazida(quantidade=10.0)
    with pytest.raises(ValueError):
        jazida.extrair(20.0)


def test_extrair_de_jazida_nao_disponivel_lanca_erro():
    jazida = _criar_jazida(estado=EstadoDaJazida.INTERDITADA)
    with pytest.raises(ValueError):
        jazida.extrair(1.0)


def test_fracao_restante_parte_de_um_e_cai_com_a_extracao():
    jazida = _criar_jazida(quantidade=100.0)
    assert jazida.quantidade_inicial == 100.0
    assert jazida.fracao_restante == 1.0
    jazida.extrair(75.0)
    assert jazida.fracao_restante == 0.25


def test_jazida_nunca_regenera():
    jazida = _criar_jazida(quantidade=100.0)
    jazida.extrair(40.0)
    jazida.extrair(40.0)
    assert jazida.quantidade_disponivel == 20.0
    assert jazida.quantidade_inicial == 100.0


def test_transicao_invalida_lanca_erro():
    jazida = _criar_jazida(estado=EstadoDaJazida.ESGOTADA)
    with pytest.raises(TransicaoDeEstadoInvalidaError):
        jazida.transicionar(EstadoDaJazida.DISPONIVEL)
