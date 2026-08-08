from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.dominio.robos import EstadoDoRobo
from mundo.motor.motor_de_simulacao import ConfiguracaoDaSimulacao, MotorDeSimulacao

CAMINHO_CATALOGO = Path(__file__).parent.parent / "config" / "minerais.json"


def _criar_motor(semente: int = 1) -> MotorDeSimulacao:
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    return MotorDeSimulacao(ConfiguracaoDaSimulacao(semente=semente, duracao_maxima=50), catalogo)


def test_robo_disponivel_recupera_desgaste_a_cada_ciclo():
    motor = _criar_motor()
    unidade = motor.robos["mineradora-1"]
    unidade.estado = EstadoDoRobo.DISPONIVEL
    unidade.desgaste = 2.0
    recuperacao = motor.catalogo_de_modos.recuperacao_de_desgaste_por_ciclo

    motor.avancar_ciclo(1)

    assert unidade.desgaste == 2.0 - recuperacao


def test_robo_executando_nao_recupera_desgaste():
    motor = _criar_motor()
    unidade = motor.robos["mineradora-1"]
    unidade.estado = EstadoDoRobo.EXECUTANDO
    unidade.desgaste = 2.0

    motor.avancar_ciclo(3)

    assert unidade.desgaste == 2.0


def test_desgaste_nunca_fica_negativo():
    motor = _criar_motor()
    unidade = motor.robos["mineradora-1"]
    unidade.estado = EstadoDoRobo.DISPONIVEL
    unidade.desgaste = 0.1

    motor.avancar_ciclo(20)

    assert unidade.desgaste == 0.0


def test_recuperacao_alcanca_todos_os_robos_disponiveis():
    motor = _criar_motor()
    for robo in motor.robos.values():
        robo.estado = EstadoDoRobo.DISPONIVEL
        robo.desgaste = 1.0

    motor.avancar_ciclo(1)

    recuperacao = motor.catalogo_de_modos.recuperacao_de_desgaste_por_ciclo
    assert all(robo.desgaste == 1.0 - recuperacao for robo in motor.robos.values())


def _extrair(cliente, **campos):
    corpo = {
        "identificador_da_unidade": "mineradora-1",
        "identificador_da_jazida": "jazida-1",
        "quantidade": 10.0,
    }
    corpo.update(campos)
    return cliente.post("/extracao/iniciar-extracao", json=corpo)


def test_extracao_acumula_desgaste_proporcional_a_energia_gasta():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 500)
        unidade = motor.robos["mineradora-1"]
        energia_antes = motor.energia.consultar_energia("extracao")

        _extrair(cliente)
        motor.avancar_ciclo(1)

        energia_gasta = energia_antes - motor.energia.consultar_energia("extracao")
        esperado = energia_gasta * motor.catalogo_de_modos.taxa_de_desgaste
        assert unidade.desgaste == pytest.approx(esperado)


def test_unidade_desgastada_paga_mais_pela_mesma_extracao():
    custos = {}
    for desgaste_inicial in (0.0, 4.0):
        app = criar_app(com_loop_real_time=False)
        with TestClient(app) as cliente:
            motor = instancia_do_mundo.obter_motor()
            motor.energia.alocar_energia("reserva_estrategica", "extracao", 500)
            motor.robos["mineradora-1"].desgaste = desgaste_inicial
            antes = motor.energia.consultar_energia("extracao")

            _extrair(cliente)
            motor.avancar_ciclo(1)

            custos[desgaste_inicial] = antes - motor.energia.consultar_energia("extracao")

    assert custos[4.0] > custos[0.0]
