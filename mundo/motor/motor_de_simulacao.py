from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from mundo.dominio.armazenagem import CatalogoDeArmazenagem
from mundo.dominio.armazens import Armazem
from mundo.dominio.autorizacao import RegistroDeAutorizacoes
from mundo.dominio.cargas import CargaMineral, LocalDaCarga
from mundo.dominio.energia import GerenciadorDeEnergia
from mundo.dominio.jazidas import EstadoDaJazida, Jazida
from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.dominio.operacao import CatalogoDeOperacao
from mundo.dominio.modos import CatalogoDeModos
from mundo.dominio.pesquisa import CatalogoDePesquisa
from mundo.dominio.robos import EstadoDoRobo, Robo, UnidadeMineradora, UnidadeTransportadora
from mundo.dominio.rotas import Rota
from mundo.eventos.barramento import BarramentoDeEventos

from .comandos import Comando, FilaDeComandos
from .efeitos import AgendaDeEfeitos

CENTRAIS = ["extracao", "armazenagem", "transporte", "pesquisa", "missao"]
CAMINHO_MODOS_PADRAO = Path(__file__).parent.parent / "config" / "modos.json"


@dataclass
class ConfiguracaoDaSimulacao:
    semente: int
    energia_total: int = 1000
    energia_inicial_por_central: int = 10


class MotorDeSimulacao:
    def __init__(
        self,
        configuracao: ConfiguracaoDaSimulacao,
        catalogo_de_minerais: CatalogoDeMinerais,
        catalogo_de_modos: CatalogoDeModos | None = None,
        catalogo_de_armazenagem: CatalogoDeArmazenagem | None = None,
        catalogo_de_operacao: CatalogoDeOperacao | None = None,
        catalogo_de_pesquisa: CatalogoDePesquisa | None = None,
    ) -> None:
        self.configuracao = configuracao
        self.catalogo_de_minerais = catalogo_de_minerais
        self.catalogo_de_modos = catalogo_de_modos or CatalogoDeModos.carregar_de_arquivo(
            CAMINHO_MODOS_PADRAO,
        )
        self.catalogo_de_armazenagem = catalogo_de_armazenagem or CatalogoDeArmazenagem.carregar_de_arquivo(
            Path(__file__).parent.parent / "config" / "armazenagem.json"
        )
        self.catalogo_de_operacao = catalogo_de_operacao or CatalogoDeOperacao.carregar_de_arquivo(
            Path(__file__).parent.parent / "config" / "operacao.json"
        )
        self.catalogo_de_pesquisa = catalogo_de_pesquisa or CatalogoDePesquisa.carregar_de_arquivo(
            Path(__file__).parent.parent / "config" / "pesquisa.json"
        )
        self.ciclo_atual = 0
        self.encerrada: bool = False
        self.rng = random.Random(configuracao.semente)
        self.energia = GerenciadorDeEnergia(
            CENTRAIS, configuracao.energia_inicial_por_central, configuracao.energia_total,
        )
        self.jazidas: dict[str, Jazida] = {}
        self.robos: dict[str, Robo] = {}
        self.armazens: dict[str, Armazem] = {}
        self.rotas: dict[str, Rota] = {}
        self.cargas: dict[str, CargaMineral] = {}
        self.analises_em_andamento: list[str] = []
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
            if self.encerrada:
                return
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
        for erro in self._agenda_de_efeitos.disparar_ate(self.ciclo_atual):
            self.eventos.publicar(
                tipo="operacao_invalida",
                ciclo=self.ciclo_atual,
                dados={
                    "comando": "efeito_agendado",
                    "central": "motor",
                    "motivo": str(erro),
                },
            )
        self._degradar_cargas()
        self._recuperar_desgaste()
        self._cobrar_manutencao_dos_armazens()
        self._cobrar_consumo_das_centrais()
        self._verificar_encerramento()

    def _degradar_cargas(self) -> None:
        for carga in self.cargas.values():
            mineral = self.catalogo_de_minerais.obter(carga.mineral)
            perda = (
                mineral.taxa_degradacao
                * carga.sensibilidade_aplicavel(mineral)
                * self.catalogo_de_modos.mult_do_local(carga.local.value)
                * carga.mult_degradacao_local
            )
            # A raridade só pesa no caminho: minério raro é instável fora de um
            # armazém, então cada ciclo de viagem custa mais quanto mais raro
            # for. É o que faz a pressa valer a pena para carga valiosa e não
            # valer para carga comum.
            if carga.local == LocalDaCarga.EM_TRANSITO:
                perda *= self.catalogo_de_modos.fator_de_raridade_em_transito(mineral.raridade)
            carga.degradar(taxa_degradacao=perda)

    def _recuperar_desgaste(self) -> None:
        recuperacao = self.catalogo_de_modos.recuperacao_de_desgaste_por_ciclo
        for robo in self.robos.values():
            if robo.estado == EstadoDoRobo.DISPONIVEL:
                robo.desgaste = max(0.0, robo.desgaste - recuperacao)

    def _verificar_encerramento(self) -> None:
        """O fim é consequência do esgotamento, não constante escolhida.

        Quando nenhuma central paga o próprio consumo, não há mais nada que o
        mundo possa fazer: as dormentes não operam, e sem a missão ninguém
        pode ser ressuscitado. Encerrar aqui também é o que garante que toda
        execução termina, do que o Avaliador depende.

        A energia encalhada é relatada porque é o placar do erro: quem deixou
        a missão secar morre com a reserva quase intacta.
        """
        if self.encerrada:
            return
        # A condição é "todas dormentes", não "ninguém cobre o consumo". Uma
        # central com menos que o consumo ainda entrega o resto no próximo
        # ciclo e só então seca, e comparar saldo com consumo em float encerra
        # um ciclo cedo: subtrações sucessivas deixam o saldo um fio abaixo do
        # valor exato.
        if any(self.energia.esta_operante(central) for central in CENTRAIS):
            return
        self.encerrada = True
        encalhada = sum(
            self.energia.consultar_energia(central)
            for central in (*CENTRAIS, self.energia.RESERVA)
        )
        self.eventos.publicar(
            tipo="simulacao_encerrada",
            ciclo=self.ciclo_atual,
            dados={
                "ciclo": self.ciclo_atual,
                "faturamento_total": self.faturamento_total,
                "energia_encalhada": encalhada,
            },
        )

    def _cobrar_consumo_das_centrais(self) -> None:
        """Existir custa: cada central paga do próprio saldo, todo ciclo.

        É o que impede a indecisão de ser gratuita — um robô parado ainda
        consome, então adiar a alocação tem preço sem precisar de nenhuma
        regra que proíba adiar.

        Cobra com `debitar_ate_o_saldo` porque o consumo é involuntário: a
        central não escolheu existir naquele ciclo, então não pode ser
        rejeitada por não poder pagar. Quem não cobre entrega o que resta e
        fica dormente, sem acumular dívida.
        """
        consumo = self.catalogo_de_operacao.consumo_por_ciclo_da_central
        for central in CENTRAIS:
            self.energia.debitar_ate_o_saldo(central, consumo)

    def _cobrar_manutencao_dos_armazens(self) -> None:
        """Guardar minério custa energia a cada ciclo, proporcional ao volume.

        A cobrança nunca derruba o tick: sem saldo, publica-se o evento e a
        simulação segue. Travar o mundo por dívida de manutenção seria pior
        que deixá-lo endividado.
        """
        total = sum(armazem.ocupacao for armazem in self.armazens.values())
        if total <= 0.0:
            return
        custo = total * self.catalogo_de_armazenagem.custo_de_manutencao_por_unidade
        try:
            self.energia.debitar("armazenagem", custo)
        except Exception as erro:
            self.eventos.publicar(
                tipo="armazem_sem_energia",
                ciclo=self.ciclo_atual,
                dados={"custo": custo, "motivo": str(erro)},
            )

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
                    quantidade_inicial=quantidade,
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
