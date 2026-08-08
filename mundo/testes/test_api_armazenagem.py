from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo


def test_consultar_armazens_retorna_dois_armazens():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.get("/armazenagem/armazens")
        assert len(resposta.json()) == 2


def test_receber_carga_ocupa_espaco_no_armazem():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1", "identificador_da_carga": "carga-1",
            "mineral": "hematita", "quantidade": 20.0, "qualidade": 90.0,
        })
        motor = instancia_do_mundo.obter_motor()
        motor.avancar_ciclo(1)
        assert motor.armazens["armazem-1"].ocupacao == 20.0
        assert "carga-1" in motor.cargas


def test_solicitar_transporte_exige_autorizacao_valida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.post("/missao/autorizar-missao", json={
            "operacao": "solicitar_transporte", "central_solicitante": "armazenagem",
        })
        id_autorizacao = resposta.json()["id_autorizacao"]

        cliente.post("/armazenagem/solicitar-transporte", json={
            "identificador_da_carga": "carga-1", "id_autorizacao": id_autorizacao,
        })
        motor = instancia_do_mundo.obter_motor()
        motor.avancar_ciclo(1)
        assert any(e.tipo == "carga_disponivel" for e in motor.eventos.consultar_eventos())
