from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo


def _receber_carga(cliente, **campos) -> None:
    corpo = {
        "identificador_do_armazem": "armazem-1",
        "identificador_da_carga": "carga-1",
        "mineral": "hematita",
        "quantidade": 20.0,
        "qualidade": 90.0,
    }
    corpo.update(campos)
    cliente.post("/armazenagem/receber-carga", json=corpo)


def _tipos_de_eventos(motor) -> list[str]:
    return [evento.tipo for evento in motor.eventos.consultar_eventos()]


def test_consultar_armazens_retorna_dois_armazens():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.get("/armazenagem/armazens")
        assert len(resposta.json()) == 2


def test_receber_carga_ocupa_espaco_no_armazem():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        _receber_carga(cliente)
        motor = instancia_do_mundo.obter_motor()
        motor.avancar_ciclo(1)
        assert motor.armazens["armazem-1"].ocupacao == 20.0
        assert "carga-1" in motor.cargas


def test_receber_carga_com_mineral_incompativel_publica_carga_contaminada():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.armazens["armazem-1"].compatibilidades = {"hematita"}

        _receber_carga(cliente, mineral="jarosita", identificador_da_carga="carga-suja")
        motor.avancar_ciclo(1)

        assert "carga_contaminada" in _tipos_de_eventos(motor)
        assert motor.armazens["armazem-1"].ocupacao == 0.0
        assert "carga-suja" not in motor.cargas


def test_receber_carga_publica_armazem_proximo_da_capacidade():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        _receber_carga(cliente, quantidade=460.0)
        motor = instancia_do_mundo.obter_motor()
        motor.avancar_ciclo(1)
        assert "armazem_proximo_da_capacidade" in _tipos_de_eventos(motor)


def test_receber_carga_publica_armazem_lotado():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        _receber_carga(cliente, quantidade=500.0)
        motor = instancia_do_mundo.obter_motor()
        motor.avancar_ciclo(1)
        assert "armazem_lotado" in _tipos_de_eventos(motor)


def test_reservar_espaco_aumenta_a_ocupacao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        cliente.post("/armazenagem/reservar-espaco", json={
            "identificador_do_armazem": "armazem-1", "quantidade": 30.0,
        })
        motor = instancia_do_mundo.obter_motor()
        motor.avancar_ciclo(1)
        assert motor.armazens["armazem-1"].ocupacao == 30.0


def test_realocar_carga_transfere_ocupacao_entre_armazens():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        _receber_carga(cliente, quantidade=25.0)
        cliente.post("/armazenagem/realocar-carga", json={
            "identificador_da_carga": "carga-1",
            "identificador_do_armazem_origem": "armazem-1",
            "identificador_do_armazem_destino": "armazem-2",
        })
        motor = instancia_do_mundo.obter_motor()
        motor.avancar_ciclo(1)
        assert motor.armazens["armazem-1"].ocupacao == 0.0
        assert motor.armazens["armazem-2"].ocupacao == 25.0


def test_liberar_carga_reduz_a_ocupacao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        cliente.post("/armazenagem/reservar-espaco", json={
            "identificador_do_armazem": "armazem-1", "quantidade": 30.0,
        })
        cliente.post("/armazenagem/liberar-carga", json={
            "identificador_do_armazem": "armazem-1", "quantidade": 10.0,
        })
        motor = instancia_do_mundo.obter_motor()
        motor.avancar_ciclo(1)
        assert motor.armazens["armazem-1"].ocupacao == 20.0


def test_descartar_carga_remove_a_carga_e_libera_espaco():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        _receber_carga(cliente, quantidade=40.0)
        cliente.post("/armazenagem/descartar-carga", json={
            "identificador_da_carga": "carga-1", "identificador_do_armazem": "armazem-1",
        })
        motor = instancia_do_mundo.obter_motor()
        motor.avancar_ciclo(1)
        assert "carga-1" not in motor.cargas
        assert motor.armazens["armazem-1"].ocupacao == 0.0
        assert "carga_descartada" in _tipos_de_eventos(motor)


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


def test_solicitar_transporte_rejeita_reuso_da_mesma_autorizacao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.post("/missao/autorizar-missao", json={
            "operacao": "solicitar_transporte", "central_solicitante": "armazenagem",
        })
        id_autorizacao = resposta.json()["id_autorizacao"]
        motor = instancia_do_mundo.obter_motor()

        cliente.post("/armazenagem/solicitar-transporte", json={
            "identificador_da_carga": "carga-1", "id_autorizacao": id_autorizacao,
        })
        motor.avancar_ciclo(1)

        cliente.post("/armazenagem/solicitar-transporte", json={
            "identificador_da_carga": "carga-2", "id_autorizacao": id_autorizacao,
        })
        motor.avancar_ciclo(1)

        tipos = _tipos_de_eventos(motor)
        assert tipos.count("carga_disponivel") == 1
        assert "operacao_invalida" in tipos


def test_solicitar_transporte_rejeita_autorizacao_inexistente():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        cliente.post("/armazenagem/solicitar-transporte", json={
            "identificador_da_carga": "carga-1", "id_autorizacao": "aut-inexistente",
        })
        motor = instancia_do_mundo.obter_motor()
        motor.avancar_ciclo(1)

        tipos = _tipos_de_eventos(motor)
        assert "carga_disponivel" not in tipos
        assert "operacao_invalida" in tipos
