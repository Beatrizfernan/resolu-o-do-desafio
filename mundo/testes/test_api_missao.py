from fastapi.testclient import TestClient

from mundo.api.app import criar_app


def test_resetar_mundo_reinicia_ciclo_para_zero():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        cliente.post("/missao/resetar-mundo", json={"semente": 7, "duracao_maxima": 100})
        resposta = cliente.get("/missao/estado")
        assert resposta.json()["ciclo_atual"] == 0


def test_alocar_energia_da_reserva_para_extracao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.post("/missao/alocar-energia", json={"destino": "extracao", "quantidade": 20})
        assert resposta.status_code == 200
        assert resposta.json()["saldo"] == 30


def test_autorizar_missao_emite_id_autorizacao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.post(
            "/missao/autorizar-missao",
            json={"operacao": "iniciar_viagem", "central_solicitante": "transporte"},
        )
        assert resposta.status_code == 200
        assert resposta.json()["id_autorizacao"].startswith("aut-")


def test_consultar_eventos_retorna_lista_vazia_inicialmente():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.get("/missao/eventos")
        assert resposta.json() == []
