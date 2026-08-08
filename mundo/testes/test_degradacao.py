from pathlib import Path

from mundo.dominio.cargas import CargaMineral, LocalDaCarga
from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.motor.motor_de_simulacao import ConfiguracaoDaSimulacao, MotorDeSimulacao

CAMINHO_CATALOGO = Path(__file__).parent.parent / "config" / "minerais.json"


def _criar_motor(semente: int = 1) -> MotorDeSimulacao:
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    return MotorDeSimulacao(ConfiguracaoDaSimulacao(semente=semente, duracao_maxima=50), catalogo)


def test_carga_em_armazem_degrada_conforme_sensibilidade_de_armazenagem():
    motor = _criar_motor()
    motor.cargas["c1"] = CargaMineral(
        "c1", "gelo_de_agua", 10.0, 100.0, local=LocalDaCarga.EM_ARMAZEM,
    )
    mineral = motor.catalogo_de_minerais.obter("gelo_de_agua")
    esperado = 100.0 - mineral.taxa_degradacao * mineral.sensibilidade_armazenagem * 1.0

    motor.avancar_ciclo(1)

    assert motor.cargas["c1"].qualidade == esperado


def test_carga_em_jazida_degrada_com_o_multiplicador_configurado_do_local():
    motor = _criar_motor()
    motor.cargas["c1"] = CargaMineral(
        "c1", "gelo_de_agua", 10.0, 100.0, local=LocalDaCarga.EM_JAZIDA,
    )
    mineral = motor.catalogo_de_minerais.obter("gelo_de_agua")
    # 2.0 é o multiplicador de "em_jazida" em config/modos.json, fixado aqui de propósito:
    # mudar aquele valor deve quebrar este teste em vez de passar despercebido.
    esperado = 100.0 - mineral.taxa_degradacao * 1.0 * 2.0

    motor.avancar_ciclo(1)

    assert motor.cargas["c1"].qualidade == esperado


def test_carga_exposta_na_jazida_degrada_mais_que_em_armazem():
    motor = _criar_motor()
    motor.cargas["exposta"] = CargaMineral(
        "exposta", "gelo_de_agua", 10.0, 100.0, local=LocalDaCarga.EM_JAZIDA,
    )
    motor.cargas["guardada"] = CargaMineral(
        "guardada", "gelo_de_agua", 10.0, 100.0, local=LocalDaCarga.EM_ARMAZEM,
    )

    motor.avancar_ciclo(1)

    assert motor.cargas["exposta"].qualidade < motor.cargas["guardada"].qualidade


def test_mineral_estavel_degrada_muito_menos_que_mineral_sensivel():
    motor = _criar_motor()
    motor.cargas["estavel"] = CargaMineral(
        "estavel", "hematita", 10.0, 100.0, local=LocalDaCarga.EM_ARMAZEM,
    )
    motor.cargas["sensivel"] = CargaMineral(
        "sensivel", "gelo_de_agua", 10.0, 100.0, local=LocalDaCarga.EM_ARMAZEM,
    )

    motor.avancar_ciclo(10)

    assert motor.cargas["estavel"].qualidade > 99.0
    assert motor.cargas["sensivel"].qualidade < 95.0


def test_multiplicador_de_contexto_amplifica_a_perda():
    motor = _criar_motor()
    motor.cargas["neutra"] = CargaMineral(
        "neutra", "jarosita", 10.0, 100.0, local=LocalDaCarga.EM_TRANSITO,
    )
    motor.cargas["penalizada"] = CargaMineral(
        "penalizada", "jarosita", 10.0, 100.0,
        local=LocalDaCarga.EM_TRANSITO, mult_degradacao_local=2.0,
    )

    motor.avancar_ciclo(1)

    perda_neutra = 100.0 - motor.cargas["neutra"].qualidade
    perda_penalizada = 100.0 - motor.cargas["penalizada"].qualidade
    assert perda_penalizada == perda_neutra * 2.0


def test_carga_entregue_nao_degrada():
    motor = _criar_motor()
    motor.cargas["c1"] = CargaMineral(
        "c1", "gelo_de_agua", 10.0, 100.0, local=LocalDaCarga.ENTREGUE,
    )

    motor.avancar_ciclo(20)

    assert motor.cargas["c1"].qualidade == 100.0


def test_qualidade_nunca_fica_negativa():
    motor = _criar_motor()
    motor.cargas["c1"] = CargaMineral(
        "c1", "gelo_de_agua", 10.0, 1.0, local=LocalDaCarga.EM_JAZIDA,
    )

    motor.avancar_ciclo(50)

    assert motor.cargas["c1"].qualidade == 0.0
