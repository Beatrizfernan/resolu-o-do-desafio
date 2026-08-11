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


def test_consultar_mineradoras_lista_apenas_unidades_mineradoras():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        mineradoras = cliente.get("/extracao/mineradoras")

        assert mineradoras.status_code == 200
        corpos = mineradoras.json()
        assert {item["identificador"] for item in corpos} == {"mineradora-1", "mineradora-2"}
        assert all("desgaste" in item for item in corpos)
        assert all("localizacao" in item for item in corpos)


def test_consultar_mineradoras_expoe_tipos_distintos():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        tipos = {item["tipo"] for item in cliente.get("/extracao/mineradoras").json()}
        assert tipos == {"leve", "precisa"}


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

    # 10 unidades pedidas × fator_desperdicio do modo: cuidadoso 1.0, agressivo 1.4.
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


def _custo_de_uma_extracao(modo, **campos):
    from mundo.api.dependencias import instancia_do_mundo

    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 100)
        mineral = motor.catalogo_de_minerais.obter(motor.jazidas["jazida-1"].mineral)
        antes = motor.energia.consultar_energia("extracao")

        _extrair(cliente, modo=modo, **campos)
        motor.avancar_ciclo(1)

        # Descontado o consumo do ciclo: o que interessa aqui é o preço da
        # extração, não o aluguel que a central paga só por existir.
        gasto = antes - motor.energia.consultar_energia("extracao")
        return mineral.custo_extracao, gasto - motor.catalogo_de_operacao.consumo_por_ciclo_da_central


def test_custo_energetico_deriva_do_mineral_e_do_modo():
    custo_extracao, cobrado = _custo_de_uma_extracao("normal")

    esperado = custo_extracao * 10.0 * 0.2 * 1.0 * 0.9
    assert cobrado == pytest.approx(esperado)


def test_custo_energetico_escala_com_o_mult_energia_do_modo():
    # Agressivo gasta menos energia por unidade (mult_energia 0.45) que o normal (1.0):
    # é essa diferença que ancora o termo `perfil.mult_energia` na fórmula do custo.
    # O perfil superficial é o padrão e aplica multiplicador adicional de 0.9.
    custo_extracao, cobrado_agressivo = _custo_de_uma_extracao("agressivo")
    _, cobrado_normal = _custo_de_uma_extracao("normal")

    assert cobrado_agressivo == pytest.approx(custo_extracao * 10.0 * 0.2 * 0.45 * 0.9)
    assert cobrado_agressivo == pytest.approx(cobrado_normal * 0.45)


def test_custo_energetico_do_modo_cuidadoso_e_o_mais_caro():
    custo_extracao, cobrado = _custo_de_uma_extracao("cuidadoso")

    # custo = custo_extracao × quantidade(10) × fator_base_de_energia(0.2) × mult_energia(1.8) × superficial(0.9).
    assert cobrado == pytest.approx(custo_extracao * 10.0 * 0.2 * 1.8 * 0.9)


def test_perfil_profundo_custa_mais_energia_que_superficial():
    _, cobrado_superficial = _custo_de_uma_extracao(
        "normal", perfil_de_escavacao="superficial"
    )
    _, cobrado_profundo = _custo_de_uma_extracao(
        "normal", perfil_de_escavacao="profunda"
    )

    assert cobrado_profundo == pytest.approx(cobrado_superficial * 1.25 / 0.9)
    assert cobrado_profundo > cobrado_superficial


def test_perfil_mapeadora_melhora_qualidade_inicial_da_carga():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 100)

        _extrair(cliente, perfil_de_escavacao="mapeadora")
        motor.avancar_ciclo(6)
        carga = next(iter(motor.cargas.values()))

        assert carga.qualidade == pytest.approx(93.6)


def _custo_com_jazida_em(fracao_restante):
    from mundo.api.dependencias import instancia_do_mundo

    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 300)
        jazida = motor.jazidas["jazida-1"]
        jazida.quantidade_disponivel = jazida.quantidade_inicial * fracao_restante
        antes = motor.energia.consultar_energia("extracao")

        _extrair(cliente, modo="normal")
        motor.avancar_ciclo(1)

        # Descontado o consumo do ciclo, pelo mesmo motivo do helper acima: a
        # razão de 16x é entre custos de extração, e o aluguel é aditivo.
        gasto = antes - motor.energia.consultar_energia("extracao")
        return gasto - motor.catalogo_de_operacao.consumo_por_ciclo_da_central


def test_extrair_de_jazida_esvaziada_custa_mais_que_de_jazida_intacta():
    # A escassez entra como fracao_restante ** -expoente_escassez (expoente 2.0),
    # limitada por fator_escassez_maximo: jazida intacta paga ×1, jazida com 25%
    # restante paga ×(0.25 ** -2) = ×16.
    custo_intacta = _custo_com_jazida_em(1.0)
    custo_esvaziada = _custo_com_jazida_em(0.25)

    assert custo_esvaziada > custo_intacta
    assert custo_esvaziada == pytest.approx(custo_intacta * 16.0)


def test_modo_invalido_retorna_422():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        assert _extrair(cliente, modo="turbo").status_code == 422


def test_interromper_extracao_impede_criacao_de_carga_e_publica_evento():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 100)
        jazida_id = "jazida-1"
        jazida = motor.jazidas[jazida_id]
        quantidade_inicial = jazida.quantidade_disponivel

        # Iniciar extração
        _extrair(cliente, identificador_da_jazida=jazida_id, quantidade=10.0)
        motor.avancar_ciclo(1)

        # Verificar que a unidade está executando
        assert motor.robos["mineradora-1"].estado == EstadoDoRobo.EXECUTANDO
        assert len(motor.cargas) == 0

        # Interromper a extração
        cliente.post("/extracao/interromper-extracao", json={
            "identificador_da_unidade": "mineradora-1",
        })
        motor.avancar_ciclo(1)
        assert motor.robos["mineradora-1"].estado == EstadoDoRobo.RETORNANDO

        # Avançar até o ciclo original de conclusão (ciclo 1 + 5 = 6)
        motor.avancar_ciclo(4)

        # Nenhuma carga deve ter sido criada
        assert len(motor.cargas) == 0

        # A jazida não deve ter sido consumida
        assert motor.jazidas[jazida_id].quantidade_disponivel == quantidade_inicial

        # Verificar que o evento extracao_interrompida foi publicado
        eventos = motor.eventos.consultar_eventos()
        assert any(e.tipo == "extracao_interrompida" and e.dados["unidade"] == "mineradora-1" for e in eventos)


def test_extracao_que_excede_a_jazida_com_desperdicio_e_rejeitada_sem_gastar_nada():
    from mundo.api.dependencias import instancia_do_mundo

    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 300)
        jazida = motor.jazidas["jazida-1"]
        # 11.0 disponível cobre a quantidade pedida (10.0), mas não o consumo real
        # do modo agressivo: 10.0 × fator_desperdicio(1.4) = 14.0.
        jazida.quantidade_disponivel = 11.0
        energia_antes = motor.energia.consultar_energia("extracao")

        _extrair(cliente, modo="agressivo", quantidade=10.0)
        motor.avancar_ciclo(1)

        # A validação acontece antes do débito e da transição de estado: nada é
        # gasto e a unidade continua livre para receber outro comando.
        # "sem gastar nada" é sobre a operação: o consumo por ciclo da central
        # acontece de qualquer forma, porque existir não é opcional.
        consumo = motor.catalogo_de_operacao.consumo_por_ciclo_da_central
        assert motor.energia.consultar_energia("extracao") == pytest.approx(
            energia_antes - consumo
        )
        assert motor.robos["mineradora-1"].estado == EstadoDoRobo.DISPONIVEL
        assert motor.robos["mineradora-1"].desgaste == 0.0
        assert motor.jazidas["jazida-1"].quantidade_disponivel == 11.0
        eventos = motor.eventos.consultar_eventos()
        assert any(
            e.tipo == "operacao_invalida" and e.dados["comando"] == "iniciar_extracao"
            for e in eventos
        )


def test_extracao_rejeitada_por_desperdicio_nao_trava_a_unidade():
    from mundo.api.dependencias import instancia_do_mundo

    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 300)
        motor.jazidas["jazida-1"].quantidade_disponivel = 11.0

        _extrair(cliente, modo="agressivo", quantidade=10.0)
        motor.avancar_ciclo(30)

        # Sem efeito agendado pendurado, a unidade segue disponível e uma extração
        # dentro do que a jazida comporta ainda funciona.
        assert motor.robos["mineradora-1"].estado == EstadoDoRobo.DISPONIVEL
        _extrair(cliente, modo="agressivo", quantidade=7.0)
        motor.avancar_ciclo(4)
        assert motor.robos["mineradora-1"].estado == EstadoDoRobo.AGUARDANDO
        assert len(motor.cargas) == 1
        assert motor.jazidas["jazida-1"].quantidade_disponivel == pytest.approx(1.2)
