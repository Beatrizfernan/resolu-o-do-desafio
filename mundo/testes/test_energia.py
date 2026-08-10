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


def test_central_com_saldo_esta_operante():
    energia = GerenciadorDeEnergia(["extracao"], energia_inicial_por_central=10)

    assert energia.esta_operante("extracao")


def test_central_sem_saldo_nao_esta_operante():
    energia = GerenciadorDeEnergia(["extracao"], energia_inicial_por_central=10)
    energia.debitar("extracao", 10.0)

    assert not energia.esta_operante("extracao")


def test_debitar_ate_o_saldo_devolve_o_que_conseguiu_debitar():
    """O consumo por ciclo não pode levantar.

    Uma operação que não cabe no saldo é rejeitada, e isso é certo. Mas o
    consumo é involuntário: a central não escolheu existir naquele ciclo.
    Ela entrega o que resta e fica dormente.
    """
    energia = GerenciadorDeEnergia(["extracao"], energia_inicial_por_central=10)
    energia.debitar("extracao", 9.97)

    debitado = energia.debitar_ate_o_saldo("extracao", 0.05)

    assert debitado == pytest.approx(0.03)
    assert energia.consultar_energia("extracao") == pytest.approx(0.0)
    assert not energia.esta_operante("extracao")


def test_debitar_ate_o_saldo_de_central_seca_nao_debita_nada():
    """Central dormente não acumula dívida."""
    energia = GerenciadorDeEnergia(["extracao"], energia_inicial_por_central=10)
    energia.debitar("extracao", 10.0)

    assert energia.debitar_ate_o_saldo("extracao", 0.05) == 0.0
    assert energia.consultar_energia("extracao") == pytest.approx(0.0)


def test_alocar_ressuscita_central_dormente():
    energia = GerenciadorDeEnergia(["extracao"], energia_inicial_por_central=10)
    energia.debitar("extracao", 10.0)

    energia.alocar_energia(GerenciadorDeEnergia.RESERVA, "extracao", 5.0)

    assert energia.esta_operante("extracao")


def test_debitar_ate_o_saldo_recusa_quantidade_negativa():
    """Silenciar um valor negativo creditaria energia.

    O clamp que existia aqui tratava negativo como zero, o que esconde uma
    configuração errada em vez de acusá-la: um consumo negativo passaria a
    financiar a central. É a mesma máscara que `liberar_espaco` tinha e que
    já foi trocada por uma exceção, pelo mesmo motivo.
    """
    energia = GerenciadorDeEnergia(["extracao"], energia_inicial_por_central=10)

    with pytest.raises(ValueError):
        energia.debitar_ate_o_saldo("extracao", -5.0)

    assert energia.consultar_energia("extracao") == pytest.approx(10.0)
