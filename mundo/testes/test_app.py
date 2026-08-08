from fastapi.testclient import TestClient

from mundo.api.app import criar_app


def test_app_inicializa_mundo_no_startup_e_expoe_estado():
    app = criar_app()
    with TestClient(app) as cliente:
        resposta = cliente.get("/missao/estado")
        assert resposta.status_code == 200
        assert resposta.json()["ciclo_atual"] == 0
