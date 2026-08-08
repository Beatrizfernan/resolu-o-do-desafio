from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.cargas import CargaMineral


def _tipos_de_eventos(motor) -> list[str]:
    return [evento.tipo for evento in motor.eventos.consultar_eventos()]


def _autorizar(cliente, operacao: str = "preparar_distribuicao") -> str:
    resposta = cliente.post("/missao/autorizar-missao", json={
        "operacao": operacao, "central_solicitante": "pesquisa",
    })
    return resposta.json()["id_autorizacao"]


def _preparar_distribuicao(cliente, id_autorizacao: str, identificador_da_carga: str = "carga-1") -> None:
    cliente.post("/pesquisa/preparar-distribuicao", json={
        "identificador_da_carga": identificador_da_carga, "id_autorizacao": id_autorizacao,
    })


def test_consultar_fila_comeca_vazia():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        assert cliente.get("/pesquisa/fila").json() == []


def test_consultar_fila_reflete_analises_iniciadas():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)

        cliente.post("/pesquisa/iniciar-analise", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1)

        assert cliente.get("/pesquisa/fila").json() == ["carga-1"]


def test_iniciar_analise_adiciona_carga_na_fila_e_debita_energia():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)
        motor.energia.alocar_energia("reserva_estrategica", "pesquisa", 20)
        energia_antes = motor.energia.consultar_energia("pesquisa")

        cliente.post("/pesquisa/iniciar-analise", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1)

        assert "carga-1" in motor.fila_de_pesquisa
        assert motor.energia.consultar_energia("pesquisa") == energia_antes - 2


def test_iniciar_analise_sem_energia_gera_operacao_invalida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)
        motor.energia.revogar_energia("pesquisa", motor.energia.consultar_energia("pesquisa"))

        cliente.post("/pesquisa/iniciar-analise", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1)

        assert "operacao_invalida" in _tipos_de_eventos(motor)
        assert motor.fila_de_pesquisa == []


def test_iniciar_analise_com_carga_inexistente_retorna_404():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.post("/pesquisa/iniciar-analise", json={"identificador_da_carga": "carga-x"})
        assert resposta.status_code == 404


def test_analise_conclui_apenas_apos_a_duracao_prevista():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)

        cliente.post("/pesquisa/iniciar-analise", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(3)
        assert "analise_concluida" not in _tipos_de_eventos(motor)

        motor.avancar_ciclo(1)

        eventos = motor.eventos.consultar_eventos()
        assert any(e.tipo == "analise_concluida" and e.dados["carga"] == "carga-1" for e in eventos)


def test_classificar_carga_retorna_mineral_e_qualidade():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "jarosita", 10.0, 73.5)

        resposta = cliente.post("/pesquisa/classificar-carga", json={"identificador_da_carga": "carga-1"})

        assert resposta.json() == {"carga": "carga-1", "mineral": "jarosita", "qualidade": 73.5}


def test_classificar_carga_inexistente_retorna_404():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.post("/pesquisa/classificar-carga", json={"identificador_da_carga": "carga-x"})
        assert resposta.status_code == 404


def test_aprovar_carga_remove_da_fila_e_publica_carga_aprovada():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)
        motor.fila_de_pesquisa.append("carga-1")

        cliente.post("/pesquisa/aprovar-carga", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1)

        assert motor.fila_de_pesquisa == []
        assert "carga_aprovada" in _tipos_de_eventos(motor)


def test_aprovar_carga_fora_da_fila_publica_carga_aprovada_sem_erro():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)

        cliente.post("/pesquisa/aprovar-carga", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1)

        assert "carga_aprovada" in _tipos_de_eventos(motor)
        assert "operacao_invalida" not in _tipos_de_eventos(motor)


def test_aprovar_carga_no_limiar_de_qualidade_e_aprovada():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 40.0)
        motor.fila_de_pesquisa.append("carga-1")

        cliente.post("/pesquisa/aprovar-carga", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1)

        assert "carga_aprovada" in _tipos_de_eventos(motor)
        assert motor.fila_de_pesquisa == []


def test_aprovar_carga_com_qualidade_baixa_gera_operacao_invalida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 10.0)
        motor.fila_de_pesquisa.append("carga-1")

        cliente.post("/pesquisa/aprovar-carga", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1)

        assert "operacao_invalida" in _tipos_de_eventos(motor)
        assert "carga_aprovada" not in _tipos_de_eventos(motor)
        assert motor.fila_de_pesquisa == ["carga-1"]


def test_aprovar_carga_inexistente_gera_operacao_invalida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()

        cliente.post("/pesquisa/aprovar-carga", json={"identificador_da_carga": "carga-x"})
        motor.avancar_ciclo(1)

        assert "operacao_invalida" in _tipos_de_eventos(motor)
        assert "carga_aprovada" not in _tipos_de_eventos(motor)


def test_rejeitar_carga_remove_da_fila_e_publica_carga_rejeitada():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 10.0)
        motor.fila_de_pesquisa.append("carga-1")

        cliente.post("/pesquisa/rejeitar-carga", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1)

        assert motor.fila_de_pesquisa == []
        eventos = motor.eventos.consultar_eventos()
        assert any(e.tipo == "carga_rejeitada" and e.dados["carga"] == "carga-1" for e in eventos)


def test_rejeitar_carga_fora_da_fila_publica_carga_rejeitada_sem_erro():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()

        cliente.post("/pesquisa/rejeitar-carga", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1)

        assert "carga_rejeitada" in _tipos_de_eventos(motor)
        assert "operacao_invalida" not in _tipos_de_eventos(motor)


def test_preparar_distribuicao_soma_faturamento():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 100.0)

        _preparar_distribuicao(cliente, _autorizar(cliente))
        motor.avancar_ciclo(1)

        assert motor.faturamento_total == 50.0  # 10 * 5.0 (hematita) * (100/100)


def test_preparar_distribuicao_pondera_faturamento_pela_qualidade():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "cristal_marciano_raro", 2.0, 50.0)

        _preparar_distribuicao(cliente, _autorizar(cliente))
        motor.avancar_ciclo(1)

        assert motor.faturamento_total == 200.0  # 2 * 200.0 * (50/100)
        eventos = motor.eventos.consultar_eventos()
        assert any(
            e.tipo == "carga_entregue" and e.dados == {"carga": "carga-1", "valor_entregue": 200.0}
            for e in eventos
        )


def test_preparar_distribuicao_rejeita_reuso_da_mesma_autorizacao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 100.0)
        id_autorizacao = _autorizar(cliente)

        _preparar_distribuicao(cliente, id_autorizacao)
        motor.avancar_ciclo(1)
        assert motor.faturamento_total == 50.0

        _preparar_distribuicao(cliente, id_autorizacao)
        motor.avancar_ciclo(1)

        assert "operacao_invalida" in _tipos_de_eventos(motor)
        assert motor.faturamento_total == 50.0


def test_preparar_distribuicao_sem_autorizacao_valida_gera_operacao_invalida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 100.0)

        _preparar_distribuicao(cliente, "aut-inexistente")
        motor.avancar_ciclo(1)

        assert "operacao_invalida" in _tipos_de_eventos(motor)
        assert motor.faturamento_total == 0.0


def test_preparar_distribuicao_rejeita_autorizacao_de_outra_operacao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 100.0)

        _preparar_distribuicao(cliente, _autorizar(cliente, operacao="iniciar_viagem"))
        motor.avancar_ciclo(1)

        assert "operacao_invalida" in _tipos_de_eventos(motor)
        assert motor.faturamento_total == 0.0


def test_preparar_distribuicao_de_carga_inexistente_nao_fatura():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()

        _preparar_distribuicao(cliente, _autorizar(cliente), identificador_da_carga="carga-x")
        motor.avancar_ciclo(1)

        assert "operacao_invalida" in _tipos_de_eventos(motor)
        assert motor.faturamento_total == 0.0
