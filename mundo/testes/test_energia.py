import pytest

from mundo.dominio.energia import CentralDesconhecidaError, EnergiaInsuficienteError, GerenciadorDeEnergia

CENTRAIS = ["extracao", "armazenagem", "transporte", "pesquisa", "missao"]


def _criar_gerenciador() -> GerenciadorDeEnergia:
    return GerenciadorDeEnergia(CENTRAIS, energia_inicial_por_central=10, energia_total=1000)


def test_saldo_inicial_por_central_e_reserva():
    gerenciador = _criar_gerenciador()
    for central in CENTRAIS:
        assert gerenciador.consultar_energia(central) == 10
    assert gerenciador.consultar_energia(GerenciadorDeEnergia.RESERVA) == 950


def test_debitar_reduz_saldo():
    gerenciador = _criar_gerenciador()
    gerenciador.debitar("extracao", 4)
    assert gerenciador.consultar_energia("extracao") == 6


def test_debitar_alem_do_saldo_lanca_erro():
    gerenciador = _criar_gerenciador()
    with pytest.raises(EnergiaInsuficienteError):
        gerenciador.debitar("extracao", 999)


def test_alocar_energia_so_a_partir_da_reserva():
    gerenciador = _criar_gerenciador()
    with pytest.raises(PermissionError):
        gerenciador.alocar_energia("extracao", "transporte", 5)


def test_alocar_energia_da_reserva_transfere_saldo():
    gerenciador = _criar_gerenciador()
    gerenciador.alocar_energia(GerenciadorDeEnergia.RESERVA, "extracao", 50)
    assert gerenciador.consultar_energia("extracao") == 60
    assert gerenciador.consultar_energia(GerenciadorDeEnergia.RESERVA) == 900


def test_revogar_energia_devolve_para_reserva():
    gerenciador = _criar_gerenciador()
    gerenciador.revogar_energia("extracao", 5)
    assert gerenciador.consultar_energia("extracao") == 5
    assert gerenciador.consultar_energia(GerenciadorDeEnergia.RESERVA) == 955


def test_central_desconhecida_lanca_erro():
    gerenciador = _criar_gerenciador()
    with pytest.raises(CentralDesconhecidaError):
        gerenciador.consultar_energia("inexistente")


def test_debitar_com_quantidade_negativa_lanca_erro():
    gerenciador = _criar_gerenciador()
    with pytest.raises(ValueError):
        gerenciador.debitar("extracao", -10)


def test_revogar_com_quantidade_negativa_lanca_erro():
    gerenciador = _criar_gerenciador()
    with pytest.raises(ValueError):
        gerenciador.revogar_energia("extracao", -5)


def test_alocar_com_quantidade_negativa_lanca_erro():
    gerenciador = _criar_gerenciador()
    with pytest.raises(ValueError):
        gerenciador.alocar_energia(GerenciadorDeEnergia.RESERVA, "extracao", -10)


def test_redistribuir_com_quantidade_negativa_lanca_erro():
    gerenciador = _criar_gerenciador()
    with pytest.raises(ValueError):
        gerenciador.redistribuir_energia("extracao", "transporte", -5)


def test_debitar_com_quantidade_zero_lanca_erro():
    gerenciador = _criar_gerenciador()
    with pytest.raises(ValueError):
        gerenciador.debitar("extracao", 0)
