from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.armazenagem import CatalogoDeArmazenagem
from mundo.dominio.cargas import CargaMineral, LocalDaCarga

CAMINHO_ARMAZENAGEM = Path(__file__).parent.parent / "config" / "armazenagem.json"
CUSTOS = CatalogoDeArmazenagem.carregar_de_arquivo(CAMINHO_ARMAZENAGEM)


def test_manutencao_cobra_por_unidade_armazenada_a_cada_ciclo():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "armazenagem", 100)
        motor.armazens["armazem-1"].empilhar("c1", 25.0)
        antes = motor.energia.consultar_energia("armazenagem")

        motor.avancar_ciclo(1)

        esperado = 25.0 * CUSTOS.custo_de_manutencao_por_unidade
        assert antes - motor.energia.consultar_energia("armazenagem") == pytest.approx(esperado)


def test_armazem_vazio_nao_custa_manutencao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "armazenagem", 100)
        antes = motor.energia.consultar_energia("armazenagem")

        motor.avancar_ciclo(3)

        assert motor.energia.consultar_energia("armazenagem") == antes


def test_manutencao_sem_saldo_nao_derruba_o_ciclo():
    """Um mundo que trava por dívida de manutenção é pior que um endividado."""
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        motor.armazens["armazem-1"].empilhar("c1", 500.0)
        ciclo_antes = motor.ciclo_atual

        motor.avancar_ciclo(1)

        assert motor.ciclo_atual == ciclo_antes + 1


def _autorizar(cliente, operacao: str = "receber_carga") -> str:
    resposta = cliente.post(
        "/missao/autorizar-missao",
        json={"operacao": operacao, "central_solicitante": "armazenagem"},
    )
    return resposta.json()["id_autorizacao"]


def _preparar(cliente, quantidades: dict[str, float]):
    from mundo.dominio.cargas import CargaMineral, LocalDaCarga

    motor = instancia_do_mundo.obter_motor()
    motor.energia.alocar_energia("reserva_estrategica", "armazenagem", 300)
    for nome, quantidade in quantidades.items():
        motor.cargas[nome] = CargaMineral(
            nome, "hematita", quantidade, 100.0, local=LocalDaCarga.NA_MAO,
        )
    return motor


def test_receber_empilha_na_ordem_dada_e_cobra_por_unidade():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 10.0, "c2": 20.0})
        antes = motor.energia.consultar_energia("armazenagem")

        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1", "c2"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        armazem = motor.armazens["armazem-1"]
        assert armazem.pilha == ["c1", "c2"]
        gasto = antes - motor.energia.consultar_energia("armazenagem")
        manutencao = armazem.ocupacao * CUSTOS.custo_de_manutencao_por_unidade
        esperado = 30.0 * CUSTOS.custo_de_armazenagem_por_unidade + manutencao
        assert gasto == pytest.approx(esperado)


def test_nova_ordem_reordena_a_pilha_e_cobra_por_movimento():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 1.0, "c2": 1.0, "c3": 1.0})
        armazem = motor.armazens["armazem-1"]
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1", "c2"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)
        antes = motor.energia.consultar_energia("armazenagem")

        # Insere c3 e declara a ordem final invertida: [c1,c2,c3] -> [c3,c2,c1].
        # Deslocamentos: c3 2->0 (2), c2 1->1 (0), c1 0->2 (2) = 4.
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c3"],
            "nova_ordem": ["c3", "c2", "c1"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        assert armazem.pilha == ["c3", "c2", "c1"]
        gasto = antes - motor.energia.consultar_energia("armazenagem")
        manutencao = armazem.ocupacao * CUSTOS.custo_de_manutencao_por_unidade
        esperado = (
            1.0 * CUSTOS.custo_de_armazenagem_por_unidade
            + 4 * CUSTOS.custo_por_movimento
            + manutencao
        )
        assert gasto == pytest.approx(esperado)


def test_sem_nova_ordem_nada_se_move_e_nao_ha_custo_de_movimento():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 1.0, "c2": 1.0})
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)
        antes = motor.energia.consultar_energia("armazenagem")

        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c2"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        armazem = motor.armazens["armazem-1"]
        manutencao = armazem.ocupacao * CUSTOS.custo_de_manutencao_por_unidade
        gasto = antes - motor.energia.consultar_energia("armazenagem")
        esperado = 1.0 * CUSTOS.custo_de_armazenagem_por_unidade + manutencao
        assert gasto == pytest.approx(esperado)


def test_nova_ordem_que_nao_e_permutacao_e_operacao_invalida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 1.0})
        invalidas = []
        motor.eventos.assinar(
            lambda e: invalidas.append(e) if e.tipo == "operacao_invalida" else None
        )

        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1"],
            "nova_ordem": ["c1", "fantasma"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        assert invalidas, "ordem inválida deveria publicar operacao_invalida"
        assert motor.armazens["armazem-1"].pilha == []


def test_receber_carga_move_para_em_armazem():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 5.0})

        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        from mundo.dominio.cargas import LocalDaCarga
        assert motor.cargas["c1"].local == LocalDaCarga.EM_ARMAZEM


def test_receber_carga_com_identificador_repetido_nao_deixa_pilha_inconsistente():
    """Um pedido com id repetido não pode deixar rastro nenhum.

    Sem checagem prévia, `empilhar` só descobre a repetição ao chegar na
    segunda ocorrência — e a primeira já entrou, deixando a carga empilhada e
    ocupando espaço enquanto o mundo registra a operação como inválida. Pior:
    o custo já teria sido cobrado pelas duas.

    Esta é a mesma classe de falha do débito depois de empilhar, por outra
    porta: o que pode falhar tem que falhar antes de qualquer mutação.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 10.0})
        invalidas = []
        motor.eventos.assinar(
            lambda e: invalidas.append(e) if e.tipo == "operacao_invalida" else None
        )

        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1", "c1"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        assert invalidas, "id repetido deveria publicar operacao_invalida"
        armazem = motor.armazens["armazem-1"]
        assert armazem.pilha == [], "nada pode ter sido empilhado"
        assert armazem.ocupacao == 0.0, "a ocupação não pode contar o que não entrou"
        assert motor.cargas["c1"].local == LocalDaCarga.NA_MAO


def test_retirar_devolve_o_alvo_e_tudo_acima_para_a_mao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 1.0, "c2": 1.0, "c3": 1.0})
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1", "c2", "c3"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        cliente.post("/armazenagem/retirar-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificador_da_carga": "c1",
            "id_autorizacao": _autorizar(cliente, "retirar_carga"),
        })
        motor.avancar_ciclo(1)

        from mundo.dominio.cargas import LocalDaCarga
        assert motor.armazens["armazem-1"].pilha == []
        for nome in ("c1", "c2", "c3"):
            assert motor.cargas[nome].local == LocalDaCarga.NA_MAO


def test_retirar_cobra_por_profundidade():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 1.0, "c2": 1.0, "c3": 1.0})
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1", "c2", "c3"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)
        antes = motor.energia.consultar_energia("armazenagem")

        # c1 está no fundo de uma pilha de três: profundidade 2.
        cliente.post("/armazenagem/retirar-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificador_da_carga": "c1",
            "id_autorizacao": _autorizar(cliente, "retirar_carga"),
        })
        motor.avancar_ciclo(1)

        gasto = antes - motor.energia.consultar_energia("armazenagem")
        assert gasto == pytest.approx(2 * CUSTOS.custo_por_desempilhamento)


def test_retirar_do_topo_nao_custa_desempilhamento():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 1.0, "c2": 1.0})
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1", "c2"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)
        antes = motor.energia.consultar_energia("armazenagem")

        cliente.post("/armazenagem/retirar-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificador_da_carga": "c2",
            "id_autorizacao": _autorizar(cliente, "retirar_carga"),
        })
        motor.avancar_ciclo(1)

        gasto_sem_manutencao = (
            antes
            - motor.energia.consultar_energia("armazenagem")
            - motor.armazens["armazem-1"].ocupacao * CUSTOS.custo_de_manutencao_por_unidade
        )
        assert gasto_sem_manutencao == pytest.approx(0.0)


def test_ocupacao_volta_a_zero_depois_de_retirar_tudo():
    """Regressão do vazamento que travava o mundo.

    Antes, entregar uma carga removia-a do mundo sem liberar espaço: a
    ocupação só subia. Com 1000 de capacidade contra 1484 de minério, quem
    processasse minério demais entupia os dois armazéns sem volta.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {f"c{i}": 20.0 for i in range(5)})
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": [f"c{i}" for i in range(5)],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)
        assert motor.armazens["armazem-1"].ocupacao == 100.0

        cliente.post("/armazenagem/retirar-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificador_da_carga": "c0",
            "id_autorizacao": _autorizar(cliente, "retirar_carga"),
        })
        motor.avancar_ciclo(1)

        assert motor.armazens["armazem-1"].ocupacao == 0.0
        assert motor.armazens["armazem-1"].pilha == []


def test_endpoints_incoerentes_com_a_pilha_sumiram():
    """Os três escreviam ocupação sem referência a carga alguma.

    Era o que permitia zerar um armazém cheio com um número inventado.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        for rota in ("liberar-carga", "realocar-carga", "reservar-espaco"):
            resposta = cliente.post(f"/armazenagem/{rota}", json={})
            assert resposta.status_code == 404, f"{rota} ainda existe"


def test_nao_se_descarta_carga_que_ainda_esta_empilhada():
    """Descartar só vale para o que está na mão.

    Descartar carga empilhada a removeria de `motor.cargas` deixando o
    identificador na pilha: o armazém passaria a apontar para uma carga que
    não existe mais, e a ocupação nunca seria liberada. É a mesma divergência
    entre conteúdo e contador que este sub-projeto existe para eliminar.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 10.0})
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)
        assert motor.armazens["armazem-1"].pilha == ["c1"]

        cliente.post("/armazenagem/descartar-carga", json={
            "identificador_da_carga": "c1",
        })
        motor.avancar_ciclo(1)

        assert "c1" in motor.cargas, "a carga não pode sumir enquanto está na pilha"
        assert motor.armazens["armazem-1"].pilha == ["c1"]


def test_nao_se_transporta_carga_que_esta_enterrada():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 1.0})
        motor.energia.alocar_energia("reserva_estrategica", "transporte", 100)
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)
        invalidas = []
        motor.eventos.assinar(
            lambda e: invalidas.append(e) if e.tipo == "operacao_invalida" else None
        )

        autorizacao = cliente.post("/missao/autorizar-missao", json={
            "operacao": "iniciar_viagem", "central_solicitante": "transporte",
        }).json()["id_autorizacao"]
        cliente.post("/transporte/iniciar-viagem", json={
            "identificador_da_unidade": "transportadora-1",
            "identificador_da_rota": "rota-1",
            "identificador_da_carga": "c1",
            "id_autorizacao": autorizacao,
        })
        motor.avancar_ciclo(1)

        assert invalidas, "transportar carga empilhada deveria ser inválido"


def test_viagem_termina_com_a_carga_na_mao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 1.0})
        motor.energia.alocar_energia("reserva_estrategica", "transporte", 100)

        autorizacao = cliente.post("/missao/autorizar-missao", json={
            "operacao": "iniciar_viagem", "central_solicitante": "transporte",
        }).json()["id_autorizacao"]
        cliente.post("/transporte/iniciar-viagem", json={
            "identificador_da_unidade": "transportadora-1",
            "identificador_da_rota": "rota-1",
            "identificador_da_carga": "c1",
            "id_autorizacao": autorizacao,
        })
        for _ in range(8):
            motor.avancar_ciclo(1)

        from mundo.dominio.cargas import LocalDaCarga
        assert motor.cargas["c1"].local == LocalDaCarga.NA_MAO


def test_falha_de_energia_ao_guardar_nao_deixa_a_carga_meio_dentro_do_armazem():
    """Operação inválida não pode deixar rastro na pilha.

    `executar()` roda dentro do try do motor, então uma falha vira
    `operacao_invalida` e o tick sobrevive — mas o que já foi mutado continua
    mutado. Se o débito de energia acontecesse depois de empilhar, uma central
    sem saldo deixaria a carga na pilha, ocupando espaço, e ainda marcada como
    estando na mão: dentro e fora do armazém ao mesmo tempo, com a ocupação
    apontando para algo que o mundo diz não ter guardado.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        # Saldo insuficiente para os 500 × 0.05 = 25.0 que guardar custaria.
        motor.energia.alocar_energia("reserva_estrategica", "armazenagem", 1)
        motor.cargas["c1"] = CargaMineral(
            "c1", "hematita", 500.0, 100.0, local=LocalDaCarga.NA_MAO,
        )
        invalidas = []
        motor.eventos.assinar(
            lambda e: invalidas.append(e) if e.tipo == "operacao_invalida" else None
        )

        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        armazem = motor.armazens["armazem-1"]
        assert invalidas, "faltar energia deveria publicar operacao_invalida"
        assert armazem.pilha == [], "a carga não pode ficar na pilha"
        assert armazem.ocupacao == 0.0, "a ocupação não pode contar o que não entrou"
        assert motor.cargas["c1"].local == LocalDaCarga.NA_MAO
