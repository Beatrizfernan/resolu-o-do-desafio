import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.cargas import CargaMineral
from mundo.dominio.rotas import CondicaoDaRota


def _tipos_de_eventos(motor) -> list[str]:
    return [evento.tipo for evento in motor.eventos.consultar_eventos()]


def _autorizar(cliente, operacao: str = "iniciar_viagem") -> str:
    resposta = cliente.post("/missao/autorizar-missao", json={
        "operacao": operacao, "central_solicitante": "transporte",
    })
    return resposta.json()["id_autorizacao"]


def _iniciar_viagem(cliente, id_autorizacao: str, **campos) -> None:
    corpo = {
        "identificador_da_unidade": "transportadora-1",
        "identificador_da_rota": "rota-1",
        "identificador_da_carga": "carga-1",
        "id_autorizacao": id_autorizacao,
    }
    corpo.update(campos)
    cliente.post("/transporte/iniciar-viagem", json=corpo)


def test_consultar_rotas_retorna_duas_rotas():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.get("/transporte/rotas")
        assert len(resposta.json()) == 2
        assert {r["identificador"] for r in resposta.json()} == {"rota-1", "rota-2"}
        assert all(r["condicao"] == "livre" for r in resposta.json())


def test_consultar_transportadores_ignora_unidades_mineradoras():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        identificadores = {t["identificador"] for t in cliente.get("/transporte/transportadores").json()}
        assert identificadores == {"transportadora-1", "transportadora-2"}


def test_consultar_cargas_disponiveis_lista_as_cargas_do_motor():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)

        resposta = cliente.get("/transporte/cargas-disponiveis")
        assert resposta.json() == [
            {"identificador": "carga-1", "mineral": "hematita", "quantidade": 10.0, "qualidade": 90.0},
        ]


def test_planejar_transporte_lista_apenas_rotas_livres():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)
        motor.rotas["rota-2"].condicao = CondicaoDaRota.INTERDITADA

        resposta = cliente.get("/transporte/planejar-transporte", params={"identificador_da_carga": "carga-1"})
        assert resposta.json() == {"carga": "carga-1", "rotas_disponiveis": ["rota-1"]}


def test_planejar_transporte_com_carga_inexistente_retorna_404():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.get("/transporte/planejar-transporte", params={"identificador_da_carga": "carga-x"})
        assert resposta.status_code == 404


def test_carregar_coloca_a_unidade_em_aguardando():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)

        cliente.post("/transporte/carregar", json={
            "identificador_da_unidade": "transportadora-1", "identificador_da_carga": "carga-1",
        })
        motor.avancar_ciclo(1)

        assert motor.robos["transportadora-1"].estado.value == "aguardando"


def test_carregar_acima_da_capacidade_gera_operacao_invalida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-pesada"] = CargaMineral("carga-pesada", "hematita", 150.0, 90.0)

        cliente.post("/transporte/carregar", json={
            "identificador_da_unidade": "transportadora-1", "identificador_da_carga": "carga-pesada",
        })
        motor.avancar_ciclo(1)

        assert "operacao_invalida" in _tipos_de_eventos(motor)
        assert motor.robos["transportadora-1"].estado.value == "disponivel"


def test_carregar_unidade_ocupada_gera_operacao_invalida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)
        motor.robos["transportadora-1"].estado = motor.robos["transportadora-1"].estado.EXECUTANDO

        cliente.post("/transporte/carregar", json={
            "identificador_da_unidade": "transportadora-1", "identificador_da_carga": "carga-1",
        })
        motor.avancar_ciclo(1)

        assert "operacao_invalida" in _tipos_de_eventos(motor)
        assert motor.robos["transportadora-1"].estado.value == "executando"


def test_carregar_unidade_inexistente_retorna_404():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.post("/transporte/carregar", json={
            "identificador_da_unidade": "transportadora-x", "identificador_da_carga": "carga-1",
        })
        assert resposta.status_code == 404


def test_iniciar_viagem_exige_autorizacao_e_debita_viagem_disponivel():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)
        energia_antes = motor.energia.consultar_energia("transporte")

        _iniciar_viagem(cliente, _autorizar(cliente))
        motor.avancar_ciclo(1)

        assert motor.robos["transportadora-1"].viagens_disponiveis == 9
        assert motor.robos["transportadora-1"].estado.value == "executando"
        assert motor.energia.consultar_energia("transporte") == energia_antes - 3


def test_iniciar_viagem_sem_autorizacao_valida_gera_operacao_invalida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)

        _iniciar_viagem(cliente, "aut-inexistente")
        motor.avancar_ciclo(1)

        assert "operacao_invalida" in _tipos_de_eventos(motor)
        assert motor.robos["transportadora-1"].viagens_disponiveis == 10
        assert motor.robos["transportadora-1"].estado.value == "disponivel"


def test_iniciar_viagem_rejeita_reuso_da_mesma_autorizacao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)
        id_autorizacao = _autorizar(cliente)

        _iniciar_viagem(cliente, id_autorizacao)
        motor.avancar_ciclo(1)
        assert motor.robos["transportadora-1"].viagens_disponiveis == 9

        _iniciar_viagem(cliente, id_autorizacao, identificador_da_unidade="transportadora-2")
        motor.avancar_ciclo(1)

        assert "operacao_invalida" in _tipos_de_eventos(motor)
        assert motor.robos["transportadora-2"].viagens_disponiveis == 10
        assert motor.robos["transportadora-2"].estado.value == "disponivel"


def test_iniciar_viagem_rejeita_autorizacao_de_outra_operacao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)

        _iniciar_viagem(cliente, _autorizar(cliente, operacao="solicitar_transporte"))
        motor.avancar_ciclo(1)

        assert "operacao_invalida" in _tipos_de_eventos(motor)
        assert motor.robos["transportadora-1"].viagens_disponiveis == 10


def test_iniciar_viagem_em_rota_interditada_gera_operacao_invalida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)
        motor.rotas["rota-1"].condicao = CondicaoDaRota.INTERDITADA

        _iniciar_viagem(cliente, _autorizar(cliente))
        motor.avancar_ciclo(1)

        assert "operacao_invalida" in _tipos_de_eventos(motor)
        assert motor.robos["transportadora-1"].viagens_disponiveis == 10
        assert motor.robos["transportadora-1"].estado.value == "disponivel"


def test_iniciar_viagem_sem_viagens_disponiveis_gera_operacao_invalida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)
        motor.robos["transportadora-1"].viagens_disponiveis = 0
        energia_antes = motor.energia.consultar_energia("transporte")

        _iniciar_viagem(cliente, _autorizar(cliente))
        motor.avancar_ciclo(1)

        assert "operacao_invalida" in _tipos_de_eventos(motor)
        assert motor.robos["transportadora-1"].viagens_disponiveis == 0
        assert motor.energia.consultar_energia("transporte") == energia_antes


def test_iniciar_viagem_com_rota_inexistente_retorna_404():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.post("/transporte/iniciar-viagem", json={
            "identificador_da_unidade": "transportadora-1", "identificador_da_rota": "rota-x",
            "identificador_da_carga": "carga-1", "id_autorizacao": "aut-1",
        })
        assert resposta.status_code == 404


def test_viagem_conclui_apos_o_tempo_base_degradando_a_carga():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)

        _iniciar_viagem(cliente, _autorizar(cliente))
        motor.avancar_ciclo(1)
        assert "transporte_concluido" not in _tipos_de_eventos(motor)

        motor.avancar_ciclo(motor.rotas["rota-1"].tempo_base)

        assert "transporte_concluido" in _tipos_de_eventos(motor)
        assert motor.robos["transportadora-1"].estado.value == "retornando"
        # Além do risco da rota, a carga sofre a degradação por ciclo em cada um dos
        # 1 + tempo_base ciclos avançados acima.
        carga = motor.cargas["carga-1"]
        mineral = motor.catalogo_de_minerais.obter(carga.mineral)
        perda_por_ciclo = (
            mineral.taxa_degradacao
            * carga.sensibilidade_aplicavel(mineral)
            * motor.catalogo_de_modos.mult_do_local(carga.local.value)
        )
        ciclos = 1 + motor.rotas["rota-1"].tempo_base
        esperado = 90.0 - motor.rotas["rota-1"].risco - perda_por_ciclo * ciclos
        assert carga.qualidade == pytest.approx(esperado)


def test_abortar_viagem_coloca_a_unidade_em_retornando():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()

        cliente.post("/transporte/abortar-viagem", json={"identificador_da_unidade": "transportadora-1"})
        motor.avancar_ciclo(1)

        assert motor.robos["transportadora-1"].estado.value == "retornando"


def test_abortar_viagem_de_unidade_inexistente_retorna_404():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.post("/transporte/abortar-viagem", json={
            "identificador_da_unidade": "transportadora-x",
        })
        assert resposta.status_code == 404


def test_descarregar_publica_carga_disponivel():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()

        cliente.post("/transporte/descarregar", json={
            "identificador_da_unidade": "transportadora-1", "identificador_da_carga": "carga-1",
        })
        motor.avancar_ciclo(1)

        eventos = motor.eventos.consultar_eventos()
        assert any(e.tipo == "carga_disponivel" and e.dados["carga"] == "carga-1" for e in eventos)


def test_retornar_unidade_torna_a_unidade_disponivel():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.robos["transportadora-1"].estado = motor.robos["transportadora-1"].estado.RETORNANDO

        cliente.post("/transporte/retornar-unidade", json={"identificador_da_unidade": "transportadora-1"})
        motor.avancar_ciclo(1)

        assert motor.robos["transportadora-1"].estado.value == "disponivel"


def test_retornar_unidade_inexistente_retorna_404():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.post("/transporte/retornar-unidade", json={
            "identificador_da_unidade": "transportadora-x",
        })
        assert resposta.status_code == 404
