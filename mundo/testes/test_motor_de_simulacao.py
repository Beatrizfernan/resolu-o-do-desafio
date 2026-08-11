from pathlib import Path

from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.motor.comandos import Comando
from mundo.motor.motor_de_simulacao import ConfiguracaoDaSimulacao, MotorDeSimulacao

CAMINHO_CATALOGO = Path(__file__).parent.parent / "config" / "minerais.json"


def _criar_motor(semente: int = 1) -> MotorDeSimulacao:
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    return MotorDeSimulacao(ConfiguracaoDaSimulacao(semente=semente), catalogo)


def test_motor_gera_mundo_inicial_com_entidades():
    motor = _criar_motor()
    assert len(motor.jazidas) == 10  # 5 minerais x 2 jazidas
    assert "mineradora-1" in motor.robos
    assert "transportadora-1" in motor.robos
    assert len(motor.armazens) == 2
    assert len(motor.rotas) >= 20


def test_motor_gera_malha_hibrida_com_rotas_fixas_e_variantes():
    motor = _criar_motor()

    assert any(rota.fixa for rota in motor.rotas.values())
    assert any(not rota.fixa for rota in motor.rotas.values())


def test_malha_de_rotas_e_deterministica_para_a_mesma_seed():
    primeiro = _criar_motor(semente=17)
    segundo = _criar_motor(semente=17)

    assinatura_primeiro = [
        (rota.identificador, rota.perfil, rota.tempo_base, rota.custo_energia_base)
        for rota in primeiro.rotas.values()
    ]
    assinatura_segundo = [
        (rota.identificador, rota.perfil, rota.tempo_base, rota.custo_energia_base)
        for rota in segundo.rotas.values()
    ]

    assert assinatura_primeiro == assinatura_segundo


def test_malha_de_rotas_varia_entre_seeds_nas_rotas_variantes():
    primeiro = _criar_motor(semente=17)
    segundo = _criar_motor(semente=18)

    variantes_primeiro = {
        rota.identificador: (rota.perfil, rota.tempo_base, rota.custo_energia_base)
        for rota in primeiro.rotas.values()
        if not rota.fixa
    }
    variantes_segundo = {
        rota.identificador: (rota.perfil, rota.tempo_base, rota.custo_energia_base)
        for rota in segundo.rotas.values()
        if not rota.fixa
    }

    assert variantes_primeiro != variantes_segundo


def test_motor_gera_jazidas_com_composicao_real_nao_trivial():
    motor = _criar_motor(semente=7)

    composicoes = [jazida.composicao_real for jazida in motor.jazidas.values()]

    assert all(composicao is not None for composicao in composicoes)
    assert any(len(composicao) > 1 for composicao in composicoes)


def test_avancar_ciclo_incrementa_contador():
    motor = _criar_motor()
    motor.avancar_ciclo(3)
    assert motor.ciclo_atual == 3


def test_comando_enfileirado_e_aplicado_no_proximo_ciclo():
    motor = _criar_motor()
    executado = []
    motor.enfileirar_comando(Comando("teste", "extracao", {}, lambda: executado.append(True)))
    assert executado == []
    motor.avancar_ciclo(1)
    assert executado == [True]


def test_comando_que_lanca_erro_publica_evento_operacao_invalida():
    motor = _criar_motor()

    def falhar():
        raise ValueError("saldo insuficiente")

    motor.enfileirar_comando(Comando("iniciar_extracao", "extracao", {}, falhar))
    motor.avancar_ciclo(1)

    eventos = [e for e in motor.eventos.consultar_eventos() if e.tipo == "operacao_invalida"]
    assert len(eventos) == 1
    assert set(eventos[0].dados) == {"comando", "central", "motivo"}
    assert eventos[0].dados["comando"] == "iniciar_extracao"
    assert eventos[0].dados["central"] == "extracao"
    assert "saldo insuficiente" in eventos[0].dados["motivo"]


def test_comando_com_erro_nao_interrompe_resto_do_ciclo():
    motor = _criar_motor()
    observado: list[str] = []

    def falhar():
        raise ValueError("saldo insuficiente")

    motor.enfileirar_comando(Comando("iniciar_extracao", "extracao", {}, falhar))
    motor.enfileirar_comando(
        Comando("registrar", "armazenagem", {}, lambda: observado.append("comando-seguinte")),
    )
    motor.agendar_efeito(motor.ciclo_atual + 1, lambda: observado.append("efeito-agendado"))

    motor.avancar_ciclo(1)

    assert observado == ["comando-seguinte", "efeito-agendado"]
    assert any(e.tipo == "operacao_invalida" for e in motor.eventos.consultar_eventos())


def test_efeito_com_erro_nao_interrompe_os_demais_efeitos_do_ciclo():
    motor = _criar_motor()
    observado: list[str] = []

    def falhar():
        raise ValueError("jazida removida")

    motor.agendar_efeito(motor.ciclo_atual + 1, falhar)
    motor.agendar_efeito(motor.ciclo_atual + 1, lambda: observado.append("efeito-seguinte"))

    motor.avancar_ciclo(1)

    assert observado == ["efeito-seguinte"]
    eventos = [e for e in motor.eventos.consultar_eventos() if e.tipo == "operacao_invalida"]
    assert len(eventos) == 1
    assert eventos[0].dados["comando"] == "efeito_agendado"
    assert "jazida removida" in eventos[0].dados["motivo"]

    motor.avancar_ciclo(1)
    assert motor.ciclo_atual == 2


def test_efeito_agendado_dispara_no_ciclo_alvo():
    motor = _criar_motor()
    disparado = []
    motor.agendar_efeito(motor.ciclo_atual + 3, lambda: disparado.append(True))
    motor.avancar_ciclo(2)
    assert disparado == []
    motor.avancar_ciclo(1)
    assert disparado == [True]
