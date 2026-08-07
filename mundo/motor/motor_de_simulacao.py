from __future__ import annotations

import random
from dataclasses import dataclass

from mundo.dominio.armazens import Armazem
from mundo.dominio.autorizacao import RegistroDeAutorizacoes
from mundo.dominio.cargas import CargaMineral
from mundo.dominio.energia import GerenciadorDeEnergia
from mundo.dominio.jazidas import EstadoDaJazida, Jazida
from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.dominio.robos import EstadoDoRobo, Robo, UnidadeMineradora, UnidadeTransportadora
from mundo.dominio.rotas import Rota
from mundo.eventos.barramento import BarramentoDeEventos

from .comandos import Comando, FilaDeComandos
from .efeitos import AgendaDeEfeitos

CENTRAIS = ["extracao", "armazenagem", "transporte", "pesquisa", "missao"]


@dataclass
class ConfiguracaoDaSimulacao:
    semente: int
    duracao_maxima: int
    energia_total: int = 1000
    energia_inicial_por_central: int = 10


class MotorDeSimulacao:
    def __init__(
        self, configuracao: ConfiguracaoDaSimulacao, catalogo_de_minerais: CatalogoDeMinerais,
    ) -> None:
        self.configuracao = configuracao
        self.catalogo_de_minerais = catalogo_de_minerais
        self.ciclo_atual = 0
        self.rng = random.Random(configuracao.semente)
        self.energia = GerenciadorDeEnergia(
            CENTRAIS, configuracao.energia_inicial_por_central, configuracao.energia_total,
        )
        self.jazidas: dict[str, Jazida] = {}
        self.robos: dict[str, Robo] = {}
        self.armazens: dict[str, Armazem] = {}
        self.rotas: dict[str, Rota] = {}
        self.cargas: dict[str, CargaMineral] = {}
        self.fila_de_pesquisa: list[str] = []
        self.faturamento_total: float = 0.0
        self.autorizacoes = RegistroDeAutorizacoes()
        self.eventos = BarramentoDeEventos()
        self._fila_de_comandos = FilaDeComandos()
        self._agenda_de_efeitos = AgendaDeEfeitos()
        self._gerar_mundo_inicial()

    def enfileirar_comando(self, comando: Comando) -> None:
        self._fila_de_comandos.enfileirar(comando)

    def agendar_efeito(self, ciclo_alvo: int, callback) -> None:
        self._agenda_de_efeitos.agendar(ciclo_alvo, callback)

    def avancar_ciclo(self, quantidade: int = 1) -> None:
        for _ in range(quantidade):
            self._processar_um_ciclo()

    def _processar_um_ciclo(self) -> None:
        self.ciclo_atual += 1
        for comando in self._fila_de_comandos.drenar():
            try:
                comando.executar()
            except Exception as erro:
                self.eventos.publicar(
                    tipo="operacao_invalida",
                    ciclo=self.ciclo_atual,
                    dados={
                        "comando": comando.tipo,
                        "central": comando.central_origem,
                        "motivo": str(erro),
                    },
                )
        self._agenda_de_efeitos.disparar_ate(self.ciclo_atual)

    def _gerar_mundo_inicial(self) -> None:
        contador_jazidas = 1
        for mineral in self.catalogo_de_minerais.todos():
            for _ in range(2):
                identificador = f"jazida-{contador_jazidas}"
                quantidade = self.rng.uniform(50, 200)
                self.jazidas[identificador] = Jazida(
                    identificador=identificador,
                    localizacao=f"setor-{contador_jazidas}",
                    mineral=mineral.nome,
                    quantidade_disponivel=quantidade,
                    dificuldade_extracao=mineral.custo_extracao,
                    risco=self.rng.uniform(0.0, 0.3),
                    estado=EstadoDaJazida.DISPONIVEL,
                )
                contador_jazidas += 1

        for i in range(1, 3):
            self.robos[f"mineradora-{i}"] = UnidadeMineradora(
                identificador=f"mineradora-{i}",
                estado=EstadoDoRobo.DISPONIVEL,
                energia_necessaria=2,
                desgaste=0.0,
                localizacao="base",
                capacidade=50.0,
            )
        for i in range(1, 3):
            self.robos[f"transportadora-{i}"] = UnidadeTransportadora(
                identificador=f"transportadora-{i}",
                estado=EstadoDoRobo.DISPONIVEL,
                energia_necessaria=3,
                desgaste=0.0,
                localizacao="base",
                capacidade=100.0,
                viagens_disponiveis=10,
            )

        for i in range(1, 3):
            self.armazens[f"armazem-{i}"] = Armazem(
                identificador=f"armazem-{i}",
                capacidade=500.0,
                localizacao=f"setor-{i}",
                condicoes="normal",
            )

        self.rotas["rota-1"] = Rota(
            identificador="rota-1",
            origem="setor-1",
            destino="central-distribuicao",
            distancia=10.0,
            tempo_base=5,
            risco=0.05,
        )
        self.rotas["rota-2"] = Rota(
            identificador="rota-2",
            origem="setor-2",
            destino="central-distribuicao",
            distancia=15.0,
            tempo_base=7,
            risco=0.08,
        )
