from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.operacao import CatalogoDeOperacao

CAMINHO_OPERACAO = Path(__file__).parent.parent / "config" / "operacao.json"
CUSTOS = CatalogoDeOperacao.carregar_de_arquivo(CAMINHO_OPERACAO)
CENTRAIS = ("extracao", "armazenagem", "transporte", "pesquisa", "missao")


def test_cada_central_paga_o_proprio_consumo_a_cada_ciclo():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        antes = {c: motor.energia.consultar_energia(c) for c in CENTRAIS}

        motor.avancar_ciclo(1)

        for central in CENTRAIS:
            gasto = antes[central] - motor.energia.consultar_energia(central)
            assert gasto == pytest.approx(CUSTOS.consumo_por_ciclo_da_central), central


def test_a_reserva_nao_paga_consumo():
    """A reserva só guarda.

    É isso que garante o encerramento: as cinco centrais drenam e a execução
    acaba mesmo com a reserva cheia, que é exatamente o desfecho do deadlock.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        reserva = motor.energia.RESERVA
        antes = motor.energia.consultar_energia(reserva)

        motor.avancar_ciclo(5)

        assert motor.energia.consultar_energia(reserva) == pytest.approx(antes)


def test_central_dormente_nao_acumula_divida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        motor.energia.debitar("extracao", motor.energia.consultar_energia("extracao"))

        motor.avancar_ciclo(10)

        assert motor.energia.consultar_energia("extracao") == pytest.approx(0.0)


def test_central_seca_no_ciclo_esperado_sem_nenhuma_alocacao():
    """Duzentos ciclos é onde a armadilha foi calibrada para disparar."""
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        ciclos_ate_secar = int(10.0 / CUSTOS.consumo_por_ciclo_da_central)

        motor.avancar_ciclo(ciclos_ate_secar - 1)
        assert motor.energia.esta_operante("missao")

        motor.avancar_ciclo(1)
        assert not motor.energia.esta_operante("missao")


def test_central_dormente_nao_executa_operacao():
    """Sem saldo não se opera, e a recusa vem antes de qualquer mutação."""
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.debitar("extracao", motor.energia.consultar_energia("extracao"))
        jazida = next(iter(motor.jazidas.values()))
        antes = jazida.quantidade_disponivel
        invalidas = []
        motor.eventos.assinar(
            lambda e: invalidas.append(e) if e.tipo == "operacao_invalida" else None
        )

        cliente.post("/extracao/iniciar-extracao", json={
            "identificador_da_unidade": "mineradora-1",
            "identificador_da_jazida": jazida.identificador,
            "quantidade": 2.0,
        })
        motor.avancar_ciclo(8)

        assert invalidas, "central dormente deveria recusar"
        motivos = [e.dados["motivo"] for e in invalidas]
        assert any("dormente" in m for m in motivos), motivos
        assert jazida.quantidade_disponivel == pytest.approx(antes)


def test_alocar_ressuscita_e_a_central_volta_a_operar():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.debitar("extracao", motor.energia.consultar_energia("extracao"))
        assert not motor.energia.esta_operante("extracao")

        cliente.post("/missao/alocar-energia", json={"destino": "extracao", "quantidade": 50})
        motor.avancar_ciclo(1)

        assert motor.energia.esta_operante("extracao")


def _autorizar(cliente, operacao: str, central: str) -> str:
    return cliente.post("/missao/autorizar-missao", json={
        "operacao": operacao, "central_solicitante": central,
    }).json()["id_autorizacao"]


def test_toda_central_dormente_recusa_a_propria_operacao():
    """As quatro guardas, não só a da extração.

    Escrever a guarda em quatro arquivos e testar uma delas deixa três livres
    para sumir sem nada acusar — foi o que a mutação mostrou. Cada central
    dormente precisa recusar a operação que ela mesma cobra.
    """
    from mundo.dominio.cargas import CargaMineral, LocalDaCarga

    pedidos = {
        "extracao": ("/extracao/iniciar-extracao", lambda motor, cliente: {
            "identificador_da_unidade": "mineradora-1",
            "identificador_da_jazida": next(iter(motor.jazidas)),
            "quantidade": 2.0,
        }),
        "armazenagem": ("/armazenagem/receber-carga", lambda motor, cliente: {
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1"],
            "id_autorizacao": _autorizar(cliente, "receber_carga", "armazenagem"),
        }),
        "transporte": ("/transporte/iniciar-viagem", lambda motor, cliente: {
            "identificador_da_unidade": "transportadora-1",
            "identificador_da_rota": "rota-1",
            "identificador_da_carga": "c1",
            "id_autorizacao": _autorizar(cliente, "iniciar_viagem", "transporte"),
        }),
        "pesquisa": ("/pesquisa/iniciar-analise", lambda motor, cliente: {
            "identificador_da_carga": "c1",
        }),
    }

    for central, (rota, corpo) in pedidos.items():
        app = criar_app(com_loop_real_time=False)
        with TestClient(app) as cliente:
            motor = instancia_do_mundo.obter_motor()
            motor.cargas["c1"] = CargaMineral(
                "c1", "hematita", 5.0, 100.0, local=LocalDaCarga.NA_MAO,
            )
            invalidas = []
            motor.eventos.assinar(
                lambda e: invalidas.append(e) if e.tipo == "operacao_invalida" else None
            )
            dados = corpo(motor, cliente)
            motor.energia.debitar(central, motor.energia.consultar_energia(central))

            cliente.post(rota, json=dados)
            motor.avancar_ciclo(1)

            motivos = [e.dados["motivo"] for e in invalidas]
            assert any(f"Central {central} dormente" in m for m in motivos), (
                f"{central} dormente aceitou a operação: {motivos}"
            )
