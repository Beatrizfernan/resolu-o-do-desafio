from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.robos import EstadoDoRobo


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


def test_extracao_concluida_cria_carga_que_ja_degrada_no_ciclo_de_criacao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        jazidas = cliente.get("/extracao/jazidas").json()
        jazida = jazidas[0]

        cliente.post(
            "/extracao/iniciar-extracao",
            json={
                "identificador_da_unidade": "mineradora-1",
                "identificador_da_jazida": jazida["identificador"],
                "quantidade": 10.0,
            },
        )

        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 20)
        motor.avancar_ciclo(6)

        assert len(motor.cargas) == 1
        carga = next(iter(motor.cargas.values()))
        assert carga.mineral == jazida["mineral"]
        assert carga.quantidade == 10.0
        # A carga nasce com qualidade máxima e sofre a degradação do ciclo em que foi criada.
        mineral = motor.catalogo_de_minerais.obter(carga.mineral)
        perda = (
            mineral.taxa_degradacao
            * carga.sensibilidade_aplicavel(mineral)
            * motor.catalogo_de_modos.mult_do_local(carga.local.value)
        )
        assert carga.qualidade == 100.0 - perda


def test_interromper_extracao_muda_estado_para_retornando():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        jazidas = cliente.get("/extracao/jazidas").json()
        cliente.post(
            "/extracao/iniciar-extracao",
            json={
                "identificador_da_unidade": "mineradora-1",
                "identificador_da_jazida": jazidas[0]["identificador"],
                "quantidade": 10.0,
            },
        )
        motor = instancia_do_mundo.obter_motor()
        motor.avancar_ciclo(1)
        assert motor.robos["mineradora-1"].estado.value == "executando"

        resposta = cliente.post(
            "/extracao/interromper-extracao",
            json={"identificador_da_unidade": "mineradora-1"},
        )
        assert resposta.status_code == 200
        assert resposta.json()["aceito"] is True

        motor.avancar_ciclo(1)
        assert motor.robos["mineradora-1"].estado.value == "retornando"


def test_retornar_unidade_muda_estado_para_disponivel():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.robos["mineradora-1"].estado = EstadoDoRobo.RETORNANDO

        resposta = cliente.post(
            "/extracao/retornar-unidade",
            json={"identificador_da_unidade": "mineradora-1"},
        )
        assert resposta.status_code == 200
        assert resposta.json()["aceito"] is True

        motor.avancar_ciclo(1)
        assert motor.robos["mineradora-1"].estado.value == "disponivel"


def test_inspecionar_jazida_inexistente_retorna_404():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.get("/extracao/jazidas/inexistente")
        assert resposta.status_code == 404
