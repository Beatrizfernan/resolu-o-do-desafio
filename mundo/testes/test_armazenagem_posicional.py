from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.armazenagem import CatalogoDeArmazenagem

CAMINHO_ARMAZENAGEM = Path(__file__).parent.parent / "config" / "armazenagem.json"
CUSTOS = CatalogoDeArmazenagem.carregar_de_arquivo(CAMINHO_ARMAZENAGEM)


def test_manutencao_cobra_por_unidade_armazenada_a_cada_ciclo():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "armazenagem", 100)
        motor.armazens["armazem-1"].empilhar("c1", 25.0)
        antes = motor.energia.consultar_energia("armazenagem")

        motor.avancar_ciclo(1)

        esperado = 25.0 * CUSTOS.custo_de_manutencao_por_unidade
        assert antes - motor.energia.consultar_energia("armazenagem") == pytest.approx(esperado)


def test_armazem_vazio_nao_custa_manutencao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "armazenagem", 100)
        antes = motor.energia.consultar_energia("armazenagem")

        motor.avancar_ciclo(3)

        assert motor.energia.consultar_energia("armazenagem") == antes


def test_manutencao_sem_saldo_nao_derruba_o_ciclo():
    """Um mundo que trava por dívida de manutenção é pior que um endividado."""
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        motor.armazens["armazem-1"].empilhar("c1", 500.0)
        ciclo_antes = motor.ciclo_atual

        motor.avancar_ciclo(1)

        assert motor.ciclo_atual == ciclo_antes + 1
