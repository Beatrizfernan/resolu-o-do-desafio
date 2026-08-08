from __future__ import annotations

from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.motor.motor_de_simulacao import ConfiguracaoDaSimulacao, MotorDeSimulacao


class InstanciaDoMundo:
    def __init__(self) -> None:
        self.motor: MotorDeSimulacao | None = None

    def inicializar(self, configuracao: ConfiguracaoDaSimulacao, catalogo: CatalogoDeMinerais) -> None:
        self.motor = MotorDeSimulacao(configuracao, catalogo)

    def obter_motor(self) -> MotorDeSimulacao:
        if self.motor is None:
            raise RuntimeError("Mundo não inicializado")
        return self.motor


instancia_do_mundo = InstanciaDoMundo()


def obter_motor() -> MotorDeSimulacao:
    return instancia_do_mundo.obter_motor()
