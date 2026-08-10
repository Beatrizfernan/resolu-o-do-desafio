from pathlib import Path

from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.motor.comandos import Comando
from mundo.motor.motor_de_simulacao import ConfiguracaoDaSimulacao, MotorDeSimulacao

CAMINHO_CATALOGO = Path(__file__).parent.parent / "config" / "minerais.json"


def _criar_motor(semente: int) -> MotorDeSimulacao:
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    return MotorDeSimulacao(ConfiguracaoDaSimulacao(semente=semente), catalogo)


def _executar_cenario(motor: MotorDeSimulacao) -> None:
    motor.energia.alocar_energia("reserva_estrategica", "extracao", 20)
    jazida_id = next(iter(motor.jazidas))

    def executar() -> None:
        jazida = motor.jazidas[jazida_id]
        motor.energia.debitar("extracao", 2)
        motor.agendar_efeito(motor.ciclo_atual + 3, lambda: jazida.extrair(10))

    motor.enfileirar_comando(Comando("iniciar_extracao", "extracao", {}, executar))
    motor.avancar_ciclo(10)


def test_mesma_semente_e_mesmas_acoes_produzem_mesmo_estado_final():
    motor_a = _criar_motor(semente=48291)
    motor_b = _criar_motor(semente=48291)

    _executar_cenario(motor_a)
    _executar_cenario(motor_b)

    assert motor_a.ciclo_atual == motor_b.ciclo_atual
    assert [j.quantidade_disponivel for j in motor_a.jazidas.values()] == [
        j.quantidade_disponivel for j in motor_b.jazidas.values()
    ]

    eventos_a = [(e.tipo, e.ciclo, e.dados) for e in motor_a.eventos.consultar_eventos()]
    eventos_b = [(e.tipo, e.ciclo, e.dados) for e in motor_b.eventos.consultar_eventos()]
    assert eventos_a == eventos_b


def test_sementes_diferentes_geram_jazidas_iniciais_diferentes():
    motor_a = _criar_motor(semente=1)
    motor_b = _criar_motor(semente=2)

    quantidades_a = [j.quantidade_disponivel for j in motor_a.jazidas.values()]
    quantidades_b = [j.quantidade_disponivel for j in motor_b.jazidas.values()]

    assert quantidades_a != quantidades_b
