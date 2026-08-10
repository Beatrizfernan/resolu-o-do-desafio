from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.operacao import CatalogoDeOperacao

CAMINHO_OPERACAO = Path(__file__).parent.parent / "config" / "operacao.json"
CUSTOS = CatalogoDeOperacao.carregar_de_arquivo(CAMINHO_OPERACAO)
CENTRAIS = ("extracao", "armazenagem", "transporte", "pesquisa", "missao")


def test_cada_central_paga_o_proprio_consumo_a_cada_ciclo():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        antes = {c: motor.energia.consultar_energia(c) for c in CENTRAIS}

        motor.avancar_ciclo(1)

        for central in CENTRAIS:
            gasto = antes[central] - motor.energia.consultar_energia(central)
            assert gasto == pytest.approx(CUSTOS.consumo_por_ciclo_da_central), central


def test_a_reserva_nao_paga_consumo():
    """A reserva só guarda.

    É isso que garante o encerramento: as cinco centrais drenam e a execução
    acaba mesmo com a reserva cheia, que é exatamente o desfecho do deadlock.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        reserva = motor.energia.RESERVA
        antes = motor.energia.consultar_energia(reserva)

        motor.avancar_ciclo(5)

        assert motor.energia.consultar_energia(reserva) == pytest.approx(antes)


def test_central_dormente_nao_acumula_divida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        motor.energia.debitar("extracao", motor.energia.consultar_energia("extracao"))

        motor.avancar_ciclo(10)

        assert motor.energia.consultar_energia("extracao") == pytest.approx(0.0)


def test_central_seca_no_ciclo_esperado_sem_nenhuma_alocacao():
    """Duzentos ciclos é onde a armadilha foi calibrada para disparar."""
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        ciclos_ate_secar = int(10.0 / CUSTOS.consumo_por_ciclo_da_central)

        motor.avancar_ciclo(ciclos_ate_secar - 1)
        assert motor.energia.esta_operante("missao")

        motor.avancar_ciclo(1)
        assert not motor.energia.esta_operante("missao")
