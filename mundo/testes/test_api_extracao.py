import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.cargas import LocalDaCarga
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
        # A carga nasce com a qualidade inicial do modo (NORMAL por omissão: 92.0)
        # e sofre a degradação do ciclo em que foi criada.
        # Hematita em jazida: taxa 0.2 × sensibilidade 1.0 × mult. do local 2.0 = 0.4 por ciclo.
        assert carga.local == LocalDaCarga.EM_JAZIDA
        assert carga.qualidade == 91.6


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


def _extrair(cliente, **campos):
    corpo = {
        "identificador_da_unidade": "mineradora-1",
        "identificador_da_jazida": "jazida-1",
        "quantidade": 10.0,
    }
    corpo.update(campos)
    return cliente.post("/extracao/iniciar-extracao", json=corpo)


def test_modo_agressivo_desperdica_mais_da_jazida_que_o_cuidadoso():
    from mundo.api.dependencias import instancia_do_mundo

    for modo, esperado_consumido in (("cuidadoso", 10.0), ("agressivo", 14.0)):
        app = criar_app(com_loop_real_time=False)
        with TestClient(app) as cliente:
            motor = instancia_do_mundo.obter_motor()
            motor.energia.alocar_energia("reserva_estrategica", "extracao", 100)
            restante_antes = motor.jazidas["jazida-1"].quantidade_disponivel

            _extrair(cliente, modo=modo)
            motor.avancar_ciclo(10)

            consumido = restante_antes - motor.jazidas["jazida-1"].quantidade_disponivel
            assert consumido == esperado_consumido


def test_modo_define_a_qualidade_inicial_da_carga():
    from mundo.api.dependencias import instancia_do_mundo

    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 100)

        _extrair(cliente, modo="agressivo")
        # Agressivo dura round(5 × 0.6) = 3 ciclos, contados a partir do ciclo 1
        # em que o comando é executado.
        motor.avancar_ciclo(4)
        carga = next(iter(motor.cargas.values()))

        # Qualidade inicial do modo agressivo (78.0) menos a degradação de 0.4
        # do ciclo em que a carga foi criada.
        assert carga.qualidade == 77.6
        assert carga.local.value == "em_jazida"


def test_modo_agressivo_conclui_antes_do_cuidadoso():
    from mundo.api.dependencias import instancia_do_mundo

    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 100)

        _extrair(cliente, identificador_da_unidade="mineradora-1", modo="agressivo")
        _extrair(cliente, identificador_da_unidade="mineradora-2", modo="cuidadoso")
        motor.avancar_ciclo(4)

        assert motor.robos["mineradora-1"].estado.value == "aguardando"
        assert motor.robos["mineradora-2"].estado.value == "executando"


def _custo_de_uma_extracao(modo):
    from mundo.api.dependencias import instancia_do_mundo

    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 100)
        mineral = motor.catalogo_de_minerais.obter(motor.jazidas["jazida-1"].mineral)
        antes = motor.energia.consultar_energia("extracao")

        _extrair(cliente, modo=modo)
        motor.avancar_ciclo(1)

        return mineral.custo_extracao, antes - motor.energia.consultar_energia("extracao")


def test_custo_energetico_deriva_do_mineral_e_do_modo():
    custo_extracao, cobrado = _custo_de_uma_extracao("normal")

    esperado = custo_extracao * 10.0 * 0.2 * 1.0
    assert cobrado == pytest.approx(esperado)


def test_custo_energetico_escala_com_o_mult_energia_do_modo():
    # Agressivo gasta menos energia por unidade (mult_energia 0.7) que o normal (1.0):
    # é essa diferença que ancora o termo `perfil.mult_energia` na fórmula do custo.
    custo_extracao, cobrado_agressivo = _custo_de_uma_extracao("agressivo")
    _, cobrado_normal = _custo_de_uma_extracao("normal")

    assert cobrado_agressivo == pytest.approx(custo_extracao * 10.0 * 0.2 * 0.7)
    assert cobrado_agressivo == pytest.approx(cobrado_normal * 0.7)


def test_custo_energetico_do_modo_cuidadoso_e_o_mais_caro():
    custo_extracao, cobrado = _custo_de_uma_extracao("cuidadoso")

    assert cobrado == pytest.approx(custo_extracao * 10.0 * 0.2 * 1.6)


def test_modo_invalido_retorna_422():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        assert _extrair(cliente, modo="turbo").status_code == 422
