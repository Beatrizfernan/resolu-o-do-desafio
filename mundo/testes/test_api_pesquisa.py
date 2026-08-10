import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.cargas import CargaMineral, LocalDaCarga


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


def test_consultar_em_andamento_comeca_vazia():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        assert cliente.get("/pesquisa/em-andamento").json() == []


def test_iniciar_analise_com_slot_disponivel():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0, local=LocalDaCarga.NA_MAO)
        
        motor.energia.alocar_energia("reserva_estrategica", "pesquisa", 20)

        resposta = cliente.post("/pesquisa/iniciar-analise", json={"identificador_da_carga": "carga-1"})
        assert resposta.status_code == 200
        motor.avancar_ciclo(1)

        assert "carga-1" in motor.analises_em_andamento


def test_iniciar_analise_com_slot_ocupado_gera_operacao_invalida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0, local=LocalDaCarga.NA_MAO)
        motor.cargas["carga-2"] = CargaMineral("carga-2", "hematita", 10.0, 90.0, local=LocalDaCarga.NA_MAO)
        motor.energia.alocar_energia("reserva_estrategica", "pesquisa", 20)

        # Preenche o slot (capacidade paralela = 1)
        cliente.post("/pesquisa/iniciar-analise", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1)
        
        # Tenta colocar mais um
        cliente.post("/pesquisa/iniciar-analise", json={"identificador_da_carga": "carga-2"})
        motor.avancar_ciclo(1)

        assert motor.analises_em_andamento == ["carga-1"]
        eventos = motor.eventos.consultar_eventos()
        assert any(e.tipo == "operacao_invalida" and "ocupado" in e.dados["motivo"] for e in eventos)


def test_analise_conclui_no_tempo_do_mineral():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0, local=LocalDaCarga.NA_MAO)
        motor.energia.alocar_energia("reserva_estrategica", "pesquisa", 20)

        cliente.post("/pesquisa/iniciar-analise", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1) # Entrou em andamento

        # Hematita demora 2 ciclos
        motor.avancar_ciclo(1)
        assert "analise_concluida" not in _tipos_de_eventos(motor)
        
        motor.avancar_ciclo(1) # Concluiu
        assert "analise_concluida" in _tipos_de_eventos(motor)
        assert motor.cargas["carga-1"].analisada is True
        assert motor.analises_em_andamento == []


def test_classificar_carga_oculta_qualidade_se_nao_analisada():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0, local=LocalDaCarga.NA_MAO, analisada=False)
        
        resposta = cliente.post("/pesquisa/classificar-carga", json={"identificador_da_carga": "carga-1"})
        assert resposta.json()["qualidade"] is None


def test_classificar_carga_mostra_qualidade_se_analisada():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0, local=LocalDaCarga.NA_MAO, analisada=True)
        
        resposta = cliente.post("/pesquisa/classificar-carga", json={"identificador_da_carga": "carga-1"})
        assert resposta.json()["qualidade"] == 90.0


def test_sondar_jazida_conclui_e_persiste_estimativa():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "pesquisa", 20)

        resposta = cliente.post("/pesquisa/sondar-jazida", json={"identificador_da_jazida": "jazida-1"})
        assert resposta.status_code == 200

        motor.avancar_ciclo(1)
        motor.avancar_ciclo(2)

        consulta = cliente.get("/pesquisa/jazidas/jazida-1/estimativa")
        assert consulta.status_code == 200
        assert consulta.json()["jazida"] == "jazida-1"
        assert consulta.json()["estimativa_de_composicao"]
        assert any(e.tipo == "sondagem_de_jazida_concluida" for e in motor.eventos.consultar_eventos())


def test_sondar_jazida_compete_com_analise_de_carga():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0, local=LocalDaCarga.NA_MAO)
        motor.energia.alocar_energia("reserva_estrategica", "pesquisa", 20)

        cliente.post("/pesquisa/iniciar-analise", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1)

        cliente.post("/pesquisa/sondar-jazida", json={"identificador_da_jazida": "jazida-1"})
        motor.avancar_ciclo(1)

        eventos = motor.eventos.consultar_eventos()
        assert any(e.tipo == "operacao_invalida" and "ocupado" in e.dados["motivo"] for e in eventos)


def test_consultar_estimativa_de_jazida_nao_sondada_retorna_404():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        resposta = cliente.get("/pesquisa/jazidas/jazida-1/estimativa")

        assert resposta.status_code == 404


def test_sondar_jazida_ja_sondada_gera_operacao_invalida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "pesquisa", 30)

        cliente.post("/pesquisa/sondar-jazida", json={"identificador_da_jazida": "jazida-1"})
        motor.avancar_ciclo(3)

        cliente.post("/pesquisa/sondar-jazida", json={"identificador_da_jazida": "jazida-1"})
        motor.avancar_ciclo(1)

        eventos = motor.eventos.consultar_eventos()
        assert any(e.tipo == "operacao_invalida" and "sondada" in e.dados["motivo"] for e in eventos)


def test_aprovar_carga_nao_analisada_gera_erro():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0, local=LocalDaCarga.NA_MAO, analisada=False)

        cliente.post("/pesquisa/aprovar-carga", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1)

        eventos = motor.eventos.consultar_eventos()
        assert any(e.tipo == "operacao_invalida" and "não analisada" in e.dados["motivo"] for e in eventos)


def test_aprovar_carga_analisada():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0, local=LocalDaCarga.NA_MAO, analisada=True)

        cliente.post("/pesquisa/aprovar-carga", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1)

        assert "carga_aprovada" in _tipos_de_eventos(motor)


def test_rejeitar_carga_nao_analisada_gera_erro():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0, local=LocalDaCarga.NA_MAO, analisada=False)

        cliente.post("/pesquisa/rejeitar-carga", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1)

        eventos = motor.eventos.consultar_eventos()
        assert any(e.tipo == "operacao_invalida" and "não analisada" in e.dados["motivo"] for e in eventos)


def test_preparar_distribuicao_nao_analisada_gera_erro():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0, local=LocalDaCarga.NA_MAO, analisada=False)

        _preparar_distribuicao(cliente, _autorizar(cliente))
        motor.avancar_ciclo(1)

        eventos = motor.eventos.consultar_eventos()
        assert any(e.tipo == "operacao_invalida" and "não analisada" in e.dados["motivo"] for e in eventos)
        assert motor.faturamento_total == 0.0


def test_preparar_distribuicao_analisada_soma_faturamento():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 100.0, local=LocalDaCarga.NA_MAO, analisada=True)

        _preparar_distribuicao(cliente, _autorizar(cliente))
        motor.avancar_ciclo(1)

        assert motor.faturamento_total == 50.0
