"""A missão é a única armadilha irrecuperável do mundo — e é barata de evitar.

Estes testes provam três coisas: que ignorar a missão mata a execução no meio,
que alocar um pouco para ela evita isso por completo, e que só ela é fatal —
as outras quatro centrais são ressuscitáveis.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.operacao import CatalogoDeOperacao

CAMINHO_OPERACAO = Path(__file__).parent.parent / "config" / "operacao.json"
CUSTOS = CatalogoDeOperacao.carregar_de_arquivo(CAMINHO_OPERACAO)
CICLOS_ATE_SECAR = int(10.0 / CUSTOS.consumo_por_ciclo_da_central)


def test_quem_ignora_a_missao_perde_a_cauda_da_execucao():
    """A armadilha existe, e dispara no meio.

    Sem nenhuma alocação a missão seca, a reserva congela, e a execução morre
    com quase toda a energia do mundo por gastar. É o piso do desafio.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()

        motor.avancar_ciclo(10_000)

        assert motor.encerrada
        assert motor.ciclo_atual < CICLOS_ATE_SECAR * 2, (
            f"a execução durou {motor.ciclo_atual} ciclos: a armadilha não disparou"
        )
        assert motor.energia.consultar_energia(motor.energia.RESERVA) > 900.0, (
            "a reserva deveria ficar encalhada"
        )


def test_alocar_para_a_missao_evita_a_armadilha_por_completo():
    """E é barata de evitar: uma alocação modesta, cedo, basta."""
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()

        cliente.post("/missao/alocar-energia", json={"destino": "missao", "quantidade": 40})
        motor.avancar_ciclo(1)
        motor.avancar_ciclo(CICLOS_ATE_SECAR * 2)

        assert motor.energia.esta_operante("missao"), (
            "quarenta de energia deveria sustentar a missão bem além do ponto da armadilha"
        )


def test_so_a_missao_e_fatal():
    """Uma armadilha, não cinco.

    Extração seca é erro recuperável: a missão a traz de volta. Missão seca
    não volta de jeito nenhum, porque não existe quem a ressuscite.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()

        motor.energia.debitar("extracao", motor.energia.consultar_energia("extracao"))
        cliente.post("/missao/alocar-energia", json={"destino": "extracao", "quantidade": 30})
        motor.avancar_ciclo(1)
        assert motor.energia.esta_operante("extracao"), "extração deveria ser ressuscitável"

        motor.energia.debitar("missao", motor.energia.consultar_energia("missao"))
        cliente.post("/missao/alocar-energia", json={"destino": "missao", "quantidade": 30})
        motor.avancar_ciclo(1)
        assert not motor.energia.esta_operante("missao"), (
            "a missão não pode ressuscitar a si mesma"
        )


def test_alocar_tudo_no_ciclo_um_continua_viavel():
    """Alocar bem não pode ser obrigatório para produzir qualquer coisa.

    Uma estratégia ingênua — distribuir tudo no início e nunca mais mexer —
    precisa continuar operando. Se ela morrer, o mecanismo virou pedágio e a
    calibração é que está errada, não o teste.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        for central in ("extracao", "armazenagem", "transporte", "pesquisa", "missao"):
            cliente.post("/missao/alocar-energia", json={"destino": central, "quantidade": 150})
        motor.avancar_ciclo(1)

        motor.avancar_ciclo(CICLOS_ATE_SECAR * 2)

        assert not motor.encerrada, (
            "distribuir tudo no início deveria continuar sendo uma estratégia viável"
        )
