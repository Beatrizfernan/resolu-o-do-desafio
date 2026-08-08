from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.energia import GerenciadorDeEnergia


def test_resetar_mundo_reinicia_ciclo_para_zero():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        instancia_do_mundo.obter_motor().avancar_ciclo(5)
        assert cliente.get("/missao/estado").json()["ciclo_atual"] == 5

        resposta = cliente.post("/missao/resetar-mundo", json={"semente": 7, "duracao_maxima": 100})

        assert resposta.status_code == 200
        assert cliente.get("/missao/estado").json()["ciclo_atual"] == 0


def test_alocar_energia_da_reserva_para_extracao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        reserva_inicial = cliente.get("/missao/estado").json()["energia"][GerenciadorDeEnergia.RESERVA]
        assert reserva_inicial == 950

        resposta = cliente.post("/missao/alocar-energia", json={"destino": "extracao", "quantidade": 20})

        assert resposta.status_code == 200
        assert resposta.json()["saldo"] == 30
        energia = cliente.get("/missao/estado").json()["energia"]
        assert energia["extracao"] == 30
        assert energia[GerenciadorDeEnergia.RESERVA] == reserva_inicial - 20


def test_autorizar_missao_emite_id_autorizacao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.post(
            "/missao/autorizar-missao",
            json={"operacao": "iniciar_viagem", "central_solicitante": "transporte"},
        )
        assert resposta.status_code == 200
        assert resposta.json()["id_autorizacao"].startswith("aut-")


def test_registrar_webhook_e_idempotente_para_a_mesma_url():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        url = "http://exemplo.invalido/eventos"

        primeira = cliente.post("/missao/registrar-webhook", json={"url": url})
        assert primeira.status_code == 200
        assert primeira.json() == {"registrado": True}
        dispatcher = instancia_do_mundo.obter_motor()._dispatcher_de_webhooks

        segunda = cliente.post("/missao/registrar-webhook", json={"url": url})
        assert segunda.status_code == 200
        assert segunda.json() == {"registrado": True}
        assert instancia_do_mundo.obter_motor()._dispatcher_de_webhooks is dispatcher
        assert dispatcher.urls_registradas() == {url}


def test_consultar_eventos_retorna_lista_vazia_inicialmente():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.get("/missao/eventos")
        assert resposta.json() == []
