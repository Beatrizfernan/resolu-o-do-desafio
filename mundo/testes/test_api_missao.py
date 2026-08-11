import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.autorizacao import RegistroDeAutorizacoes
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
        # A alocação passou a ser comando enfileirado, então a resposta só
        # confirma o aceite: o saldo muda no tick, como toda outra mutação.
        assert resposta.json() == {"aceito": True}
        instancia_do_mundo.obter_motor().avancar_ciclo(1)

        consumo = instancia_do_mundo.obter_motor().catalogo_de_operacao.consumo_por_ciclo_da_central
        energia = cliente.get("/missao/estado").json()["energia"]
        assert energia["extracao"] == pytest.approx(30 - consumo)
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


def test_autorizar_debita_o_custo_da_missao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        antes = motor.energia.consultar_energia("missao")

        cliente.post("/missao/autorizar-missao", json={
            "operacao": "receber_carga", "central_solicitante": "armazenagem",
        })

        gasto = antes - motor.energia.consultar_energia("missao")
        assert gasto == pytest.approx(motor.catalogo_de_operacao.custo_de_autorizacao)


def test_autorizacao_segura_custa_mais_que_rapida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        antes = motor.energia.consultar_energia("missao")

        cliente.post("/missao/autorizar-missao", json={
            "operacao": "iniciar_viagem",
            "central_solicitante": "transporte",
            "classe": "segura",
        })

        gasto_segura = antes - motor.energia.consultar_energia("missao")
        assert gasto_segura > motor.catalogo_de_operacao.custo_de_autorizacao


def test_autorizacao_em_lote_registra_classe_no_registro():
    registro = RegistroDeAutorizacoes()

    autorizacao = registro.emitir("receber_carga", "armazenagem", classe="lote")

    assert autorizacao.classe == "lote"


def test_missao_dormente_nao_emite_autorizacao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.debitar("missao", motor.energia.consultar_energia("missao"))

        resposta = cliente.post("/missao/autorizar-missao", json={
            "operacao": "receber_carga", "central_solicitante": "armazenagem",
        })

        assert resposta.status_code == 400


def test_alocar_energia_so_muta_no_ciclo():
    """Nenhuma rota muta estado de forma síncrona — nem esta.

    Era a única exceção no projeto inteiro. Enfileirada como comando, a
    alocação passa a valer no tick, como todo o resto.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        antes = motor.energia.consultar_energia("extracao")

        cliente.post("/missao/alocar-energia", json={"destino": "extracao", "quantidade": 50})
        assert motor.energia.consultar_energia("extracao") == pytest.approx(antes)

        motor.avancar_ciclo(1)
        consumo = motor.catalogo_de_operacao.consumo_por_ciclo_da_central
        assert motor.energia.consultar_energia("extracao") == pytest.approx(antes + 50 - consumo)


def test_missao_dormente_nao_aloca():
    """Esta linha é o mecanismo inteiro do deadlock."""
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.debitar("missao", motor.energia.consultar_energia("missao"))
        antes = motor.energia.consultar_energia("extracao")

        cliente.post("/missao/alocar-energia", json={"destino": "extracao", "quantidade": 50})
        motor.avancar_ciclo(1)

        # Só o consumo do ciclo pode ter mexido no saldo. Afirmar apenas
        # "menos que antes + 50" deixaria o teste passar com a alocação
        # acontecendo, porque o consumo já derruba o total abaixo disso.
        consumo = motor.catalogo_de_operacao.consumo_por_ciclo_da_central
        assert motor.energia.consultar_energia("extracao") == pytest.approx(antes - consumo)
