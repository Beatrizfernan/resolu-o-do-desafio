from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.cargas import CargaMineral
from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.dominio.modos import ModoDeExtracao, ModoDeTransporte
from mundo.dominio.robos import EstadoDoRobo
from mundo.motor.motor_de_simulacao import ConfiguracaoDaSimulacao, MotorDeSimulacao

CAMINHO_CATALOGO = Path(__file__).parent.parent / "config" / "minerais.json"


def _criar_motor(semente: int = 1) -> MotorDeSimulacao:
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    return MotorDeSimulacao(ConfiguracaoDaSimulacao(semente=semente, duracao_maxima=50), catalogo)


def test_robo_disponivel_recupera_desgaste_a_cada_ciclo():
    motor = _criar_motor()
    unidade = motor.robos["mineradora-1"]
    unidade.estado = EstadoDoRobo.DISPONIVEL
    unidade.desgaste = 2.0
    recuperacao = motor.catalogo_de_modos.recuperacao_de_desgaste_por_ciclo

    motor.avancar_ciclo(1)

    assert unidade.desgaste == 2.0 - recuperacao


def test_robo_executando_nao_recupera_desgaste():
    motor = _criar_motor()
    unidade = motor.robos["mineradora-1"]
    unidade.estado = EstadoDoRobo.EXECUTANDO
    unidade.desgaste = 2.0

    motor.avancar_ciclo(3)

    assert unidade.desgaste == 2.0


def test_desgaste_nunca_fica_negativo():
    motor = _criar_motor()
    unidade = motor.robos["mineradora-1"]
    unidade.estado = EstadoDoRobo.DISPONIVEL
    unidade.desgaste = 0.1

    motor.avancar_ciclo(20)

    assert unidade.desgaste == 0.0


def test_recuperacao_alcanca_todos_os_robos_disponiveis():
    motor = _criar_motor()
    for robo in motor.robos.values():
        robo.estado = EstadoDoRobo.DISPONIVEL
        robo.desgaste = 1.0

    motor.avancar_ciclo(1)

    recuperacao = motor.catalogo_de_modos.recuperacao_de_desgaste_por_ciclo
    assert all(robo.desgaste == 1.0 - recuperacao for robo in motor.robos.values())


def _extrair(cliente, **campos):
    corpo = {
        "identificador_da_unidade": "mineradora-1",
        "identificador_da_jazida": "jazida-1",
        "quantidade": 10.0,
    }
    corpo.update(campos)
    return cliente.post("/extracao/iniciar-extracao", json=corpo)


def test_extracao_acumula_desgaste_conforme_o_ritmo_do_modo():
    """O desgaste mede ritmo de operação, não energia consumida.

    Cada extração acumula `taxa_de_desgaste / mult_duracao`: ciclos mais curtos
    castigam mais a máquina, independentemente do que a operação custou.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 500)
        unidade = motor.robos["mineradora-1"]
        perfil = motor.catalogo_de_modos.obter_extracao(ModoDeExtracao.NORMAL)

        _extrair(cliente, modo="normal")
        motor.avancar_ciclo(1)

        esperado = motor.catalogo_de_modos.taxa_de_desgaste / perfil.mult_duracao
        assert unidade.desgaste == pytest.approx(esperado)


def test_unidade_desgastada_paga_mais_pela_mesma_extracao():
    custos = {}
    for desgaste_inicial in (0.0, 4.0):
        app = criar_app(com_loop_real_time=False)
        with TestClient(app) as cliente:
            motor = instancia_do_mundo.obter_motor()
            motor.energia.alocar_energia("reserva_estrategica", "extracao", 500)
            motor.robos["mineradora-1"].desgaste = desgaste_inicial
            antes = motor.energia.consultar_energia("extracao")

            _extrair(cliente)
            motor.avancar_ciclo(1)

            custos[desgaste_inicial] = antes - motor.energia.consultar_energia("extracao")

    assert custos[4.0] > custos[0.0]


def _autorizar(cliente) -> str:
    resposta = cliente.post(
        "/missao/autorizar-missao",
        json={"operacao": "iniciar_viagem", "central_solicitante": "transporte"},
    )
    return resposta.json()["id_autorizacao"]


def test_transportadora_desgastada_paga_mais_pela_mesma_viagem():
    custos = {}
    for desgaste_inicial in (0.0, 4.0):
        app = criar_app(com_loop_real_time=False)
        with TestClient(app) as cliente:
            motor = instancia_do_mundo.obter_motor()
            motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)
            motor.energia.alocar_energia("reserva_estrategica", "transporte", 500)
            motor.robos["transportadora-1"].desgaste = desgaste_inicial
            antes = motor.energia.consultar_energia("transporte")

            cliente.post(
                "/transporte/iniciar-viagem",
                json={
                    "identificador_da_unidade": "transportadora-1",
                    "identificador_da_rota": "rota-1",
                    "identificador_da_carga": "carga-1",
                    "id_autorizacao": _autorizar(cliente),
                },
            )
            motor.avancar_ciclo(1)

            custos[desgaste_inicial] = antes - motor.energia.consultar_energia("transporte")

    assert custos[4.0] > custos[0.0]


def test_viagem_acumula_desgaste_na_transportadora():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)
        motor.energia.alocar_energia("reserva_estrategica", "transporte", 500)
        unidade = motor.robos["transportadora-1"]
        perfil = motor.catalogo_de_modos.obter_transporte(ModoDeTransporte.NORMAL)

        cliente.post(
            "/transporte/iniciar-viagem",
            json={
                "identificador_da_unidade": "transportadora-1",
                "identificador_da_rota": "rota-1",
                "identificador_da_carga": "carga-1",
                "id_autorizacao": _autorizar(cliente),
            },
        )
        motor.avancar_ciclo(1)

        esperado = motor.catalogo_de_modos.taxa_de_desgaste / perfil.mult_duracao
        assert unidade.desgaste == pytest.approx(esperado)


CICLOS_DE_OPERACAO_CONTINUA = 60


def _operar_continuamente(modo: str) -> tuple[float, float]:
    """Extrai sem pausas por uma janela fixa de ciclos.

    Devolve (unidades entregues, energia gasta) para o modo dado, ponderando
    a entrega pela qualidade inicial do modo — o que interessa é valor útil,
    não massa bruta.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 900)
        unidade = motor.robos["mineradora-1"]
        perfil = motor.catalogo_de_modos.obter_extracao(ModoDeExtracao(modo))
        energia_antes = motor.energia.consultar_energia("extracao")
        entregue = 0.0

        for _ in range(CICLOS_DE_OPERACAO_CONTINUA):
            if unidade.estado.value == "disponivel":
                resposta = _extrair(cliente, modo=modo, quantidade=2.0)
                if resposta.status_code == 200:
                    entregue += 2.0 * (perfil.qualidade_inicial / 100)
            elif unidade.estado.value == "aguardando":
                unidade.estado = EstadoDoRobo.DISPONIVEL
            motor.avancar_ciclo(1)

        return entregue, energia_antes - motor.energia.consultar_energia("extracao")


def test_agressivo_deixa_de_dominar_sob_operacao_continua():
    """O ponto do sub-projeto inteiro.

    Sem desgaste, agressivo vence por 1,88x em qualquer cenário estático.
    Sob uso contínuo ele executa mais operações por ciclo, acumula desgaste
    mais rápido e o custo por unidade entregue passa a subir.
    """
    entregue_agressivo, energia_agressivo = _operar_continuamente("agressivo")
    entregue_cuidadoso, energia_cuidadoso = _operar_continuamente("cuidadoso")

    custo_agressivo = energia_agressivo / entregue_agressivo
    custo_cuidadoso = energia_cuidadoso / entregue_cuidadoso

    assert custo_agressivo > custo_cuidadoso, (
        f"agressivo ainda domina sob uso contínuo: "
        f"{custo_agressivo:.2f} vs {custo_cuidadoso:.2f} de energia por unidade entregue"
    )


def test_normal_tambem_acumula_desgaste_e_nao_tem_refugio():
    """Impede a dominância invertida.

    Se o desgaste punisse só os extremos, `normal` viraria a escolha
    universal — o mesmo defeito com outro nome.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 500)
        unidade = motor.robos["mineradora-1"]

        _extrair(cliente, modo="normal")
        motor.avancar_ciclo(1)

        assert unidade.desgaste > 0.0
