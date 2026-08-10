from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.armazenagem import CatalogoDeArmazenagem

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


def _autorizar(cliente) -> str:
    resposta = cliente.post(
        "/missao/autorizar-missao",
        json={"operacao": "receber_carga", "central_solicitante": "armazenagem"},
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
    """Cobre o guard de duplicidade de `Armazem.empilhar` pela via da API.

    Task 1 identificou que esse guard não tem teste dedicado e é
    load-bearing: sem ele, a mesma carga entraria duas vezes na pilha e o
    caminho de liberação decrementaria a ocupação duas vezes para uma única
    carga física. `identificadores_das_cargas` com o mesmo id repetido é o
    jeito de um participante disparar isso a partir do endpoint.
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
        assert armazem.pilha == ["c1"]
        assert armazem.ocupacao == 10.0
