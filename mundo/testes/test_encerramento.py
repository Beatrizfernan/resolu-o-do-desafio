import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo


def test_simulacao_encerra_quando_nenhuma_central_paga_o_consumo():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        encerramentos = []
        motor.eventos.assinar(
            lambda e: encerramentos.append(e) if e.tipo == "simulacao_encerrada" else None
        )

        motor.avancar_ciclo(500)

        assert motor.encerrada
        assert encerramentos, "encerrar precisa publicar simulacao_encerrada"


def test_avancar_ciclo_e_no_op_depois_de_encerrada():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        motor.avancar_ciclo(500)
        ciclo_no_fim = motor.ciclo_atual

        motor.avancar_ciclo(50)

        assert motor.ciclo_atual == ciclo_no_fim


def test_toda_execucao_termina():
    """O Avaliador depende disto para rodar cem simulações.

    Sem alocação nenhuma, as cinco centrais drenam os 10 iniciais e a
    execução morre. Com alocação, morre depois. Em nenhum caso roda para
    sempre — a energia total só diminui.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()

        motor.avancar_ciclo(10_000)

        assert motor.encerrada


def test_o_evento_de_encerramento_relata_o_que_sobrou():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        capturados = []
        motor.eventos.assinar(
            lambda e: capturados.append(e) if e.tipo == "simulacao_encerrada" else None
        )

        motor.avancar_ciclo(500)

        dados = capturados[0].dados
        assert dados["ciclo"] == motor.ciclo_atual
        assert dados["faturamento_total"] == pytest.approx(motor.faturamento_total)
        # Ninguém alocou nada, então a reserva inteira ficou encalhada.
        assert dados["energia_encalhada"] > 900.0


def test_resetar_mundo_aceita_pedido_sem_duracao_maxima():
    """O campo sai do contrato sem quebrar quem já o enviava.

    `duracao_maxima` esteve no corpo desde o início e nunca fez nada.
    Removê-lo não pode derrubar cliente de participante, então o pedido é
    aceito com ou sem ele.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        assert cliente.post("/missao/resetar-mundo", json={"semente": 7}).status_code == 200
        resposta = cliente.post(
            "/missao/resetar-mundo", json={"semente": 7, "duracao_maxima": 100},
        )
        assert resposta.status_code == 200
