from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo


def test_consultar_jazidas_retorna_dez_jazidas():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.get("/extracao/jazidas")
        assert resposta.status_code == 200
        assert len(resposta.json()) == 10


def test_iniciar_extracao_e_aceita_e_processada_no_proximo_ciclo():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        jazidas = cliente.get("/extracao/jazidas").json()
        jazida_id = jazidas[0]["identificador"]

        resposta = cliente.post(
            "/extracao/iniciar-extracao",
            json={
                "identificador_da_unidade": "mineradora-1",
                "identificador_da_jazida": jazida_id,
                "quantidade": 10.0,
            },
        )
        assert resposta.status_code == 200
        assert resposta.json()["aceito"] is True

        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 20)
        motor.avancar_ciclo(1)
        assert motor.robos["mineradora-1"].estado.value == "executando"
        motor.avancar_ciclo(5)
        assert motor.robos["mineradora-1"].estado.value == "aguardando"


def test_inspecionar_jazida_inexistente_retorna_404():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.get("/extracao/jazidas/inexistente")
        assert resposta.status_code == 404
