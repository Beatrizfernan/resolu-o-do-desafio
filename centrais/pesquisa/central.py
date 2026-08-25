from __future__ import annotations

from dataclasses import dataclass
import heapq
from enum import Enum
from typing import Any, Protocol


class Mineral(str, Enum):
    HEMATITA = "hematita"
    SILICA_DE_ALTA_PUREZA = "silica_de_alta_pureza"
    JAROSITA = "jarosita"
    GELO_DE_AGUA = "gelo_de_agua"
    CRISTAL_MARCIANO_RARO = "cristal_marciano_raro"
    DESCONHECIDO = "desconhecido"


class TipoDeAnalise(str, Enum):
    RAPIDA = "rapida"


class ClasseDeAutorizacao(str, Enum):
    RAPIDA = "rapida"


class PoliticaDeAprovacao(str, Enum):
    COMERCIAL = "comercial"
    ESTRITA = "estrita"
    PREMIUM = "premium"


class TipoDeEvento(str, Enum):
    TRANSPORTE_CONCLUIDO = "transporte_concluido"
    CARGAS_ARMAZENADAS = "cargas_armazenadas"
    CARGAS_DESEMPILHADAS = "cargas_desempilhadas"


class ClienteDoMundo(Protocol):
    """Contrato mínimo usado pela Central de Pesquisa.

    O protocolo permite testar a central sem subir um servidor HTTP e também
    funciona com o ``ClienteDeAvaliacao`` fornecido pelo projeto.
    """

    def chamar(self, metodo: str, rota: str, json: dict | None = None) -> Any:
        ...


@dataclass(frozen=True)
class CargaParaPesquisa:
    identificador: str
    mineral: Mineral
    quantidade: float = 0.0
    qualidade: float | None = None



class FilaDePrioridade:
    """Fila determinística: raros primeiro, chegada anterior em empate."""

    def __init__(self) -> None:
        self._itens: list[tuple[int, int, str]] = []
        self._cargas: dict[str, CargaParaPesquisa] = {}
        self._sequencia = 0

    def adicionar(self, carga: CargaParaPesquisa, prioridade: int) -> bool:
        if carga.identificador in self._cargas:
            return False
        heapq.heappush(
            self._itens,
            (prioridade, self._sequencia, carga.identificador),
        )
        self._cargas[carga.identificador] = carga
        self._sequencia += 1
        return True

    def retirar(self) -> CargaParaPesquisa | None:
        if not self._itens:
            return None
        _, _, identificador = heapq.heappop(self._itens)
        return self._cargas.pop(identificador)

    def contem(self, identificador: str) -> bool:
        return identificador in self._cargas

    def __len__(self) -> int:
        return len(self._itens)


class CentralDePesquisa:
    """Coordena análise, aprovação e distribuição de cargas.

    A classe não mantém o estado físico das cargas. O Mundo continua sendo a
    fonte de verdade; esta central mantém apenas a fila e os identificadores
    que já receberam comandos, evitando duplicidade entre ciclos.
    """

    PRIORIDADE_POR_MINERAL = {
        Mineral.CRISTAL_MARCIANO_RARO: 0,
        Mineral.GELO_DE_AGUA: 1,
        Mineral.JAROSITA: 2,
        Mineral.SILICA_DE_ALTA_PUREZA: 3,
        Mineral.HEMATITA: 4,
    }
    PRIORIDADE_DESCONHECIDA = 5

    def __init__(self) -> None:
        self.fila = FilaDePrioridade()
        self.cargas: dict[str, CargaParaPesquisa] = {}
        self.analises_solicitadas: set[str] = set()
        self.aprovacoes_solicitadas: set[str] = set()
        self.distribuicoes_solicitadas: set[str] = set()
        self.rejeicoes_solicitadas: set[str] = set()
        self.armazenagens_solicitadas: set[str] = set()
        self.eventos_processados: set[str] = set()

    def observar_cargas(self, cargas: list[dict[str, Any]]) -> None:
        """Adiciona ao fluxo as cargas que ainda não foram analisadas."""
        for dados in cargas:
            try:
                mineral = Mineral(dados["mineral"])
            except ValueError:
                mineral = Mineral.DESCONHECIDO
            carga = CargaParaPesquisa(
                identificador=dados["identificador"],
                mineral=mineral,
                quantidade=float(dados.get("quantidade", 0.0)),
                qualidade=dados.get("qualidade"),
            )
            self.cargas[carga.identificador] = carga
            if carga.qualidade is None and carga.identificador not in self.analises_solicitadas:
                self.fila.adicionar(
                    carga,
                    self.PRIORIDADE_POR_MINERAL.get(
                        carga.mineral,
                        self.PRIORIDADE_DESCONHECIDA,
                    ),
                )

    def processar_ciclo(
        self,
        cliente: ClienteDoMundo,
        eventos: list[dict[str, Any]] | None = None,
    ) -> str | None:
        """Inicia no máximo uma análise quando o laboratório está livre.

        Retorna o identificador da carga analisada neste ciclo, ou ``None``
        quando não havia trabalho elegível. A análise é sempre rápida, pois
        ela reduz duração e custo sem alterar a qualidade no simulador atual.
        """
        # A API lista tambem cargas ainda na jazida. So eventos de chegada
        # podem colocar uma carga na fila da Pesquisa.
        if eventos:
            ids_disponiveis: set[str] = set()
            for evento in eventos:
                tipo = evento.get("tipo")
                dados = evento.get("dados", {})
                if tipo == TipoDeEvento.TRANSPORTE_CONCLUIDO.value:
                    if dados.get("carga"):
                        ids_disponiveis.add(dados["carga"])
                elif tipo in {TipoDeEvento.CARGAS_DESEMPILHADAS.value, TipoDeEvento.CARGAS_ARMAZENADAS.value}:
                    ids_disponiveis.update(dados.get("cargas", []))

            if ids_disponiveis:
                cargas = cliente.chamar("GET", "/transporte/cargas-disponiveis")
                self.observar_cargas([
                    carga for carga in cargas
                    if carga["identificador"] in ids_disponiveis
                ])

        em_andamento = cliente.chamar("GET", "/pesquisa/em-andamento")
        if not len(self.fila):
            return None

        if em_andamento:
            carga = self.fila.retirar()
            if carga is not None:
                self.encaminhar_para_armazenagem(cliente, carga.identificador)
            return None

        carga = self.fila.retirar()
        if carga is None:
            return None

        cliente.chamar(
            "POST",
            "/pesquisa/iniciar-analise",
            {
                "identificador_da_carga": carga.identificador,
                "tipo_de_analise": TipoDeAnalise.RAPIDA.value,
            },
        )
        self.analises_solicitadas.add(carga.identificador)
        return carga.identificador

    def _esta_guardada(self, cliente: ClienteDoMundo, identificador: str) -> bool:
        return any(
            identificador in armazem.get("pilha", [])
            for armazem in cliente.chamar("GET", "/armazenagem/armazens")
        )

    def encaminhar_para_armazenagem(
        self,
        cliente: ClienteDoMundo,
        identificador: str,
    ) -> bool:
        """Guarda uma carga quando o unico slot da Pesquisa esta ocupado."""
        if identificador in self.armazenagens_solicitadas:
            return False
        armazens = cliente.chamar("GET", "/armazenagem/armazens")
        carga = self.cargas.get(identificador)
        if carga is None or not armazens:
            return False
        armazem = next((
            item for item in armazens
            if item["capacidade"] - item["ocupacao"] >= carga.quantidade
        ), None)
        if armazem is None:
            return False
        autorizacao = cliente.chamar(
            "POST", "/missao/autorizar-missao",
            {"operacao": "receber_carga", "central_solicitante": "armazenagem", "classe": ClasseDeAutorizacao.RAPIDA.value},
        )
        cliente.chamar(
            "POST", "/armazenagem/receber-carga",
            {"identificador_do_armazem": armazem["identificador"], "identificadores_das_cargas": [identificador], "id_autorizacao": autorizacao["id_autorizacao"]},
        )
        self.armazenagens_solicitadas.add(identificador)
        return True

    def processar_eventos(
        self,
        cliente: ClienteDoMundo,
        eventos: list[dict[str, Any]],
    ) -> None:
        """Processa cada evento uma unica vez e aciona a proxima etapa."""
        novos_eventos = [
            evento for evento in eventos
            if evento.get("identificador") not in self.eventos_processados
        ]
        for evento in novos_eventos:
            identificador_do_evento = evento.get("identificador")
            if identificador_do_evento:
                self.eventos_processados.add(identificador_do_evento)
            tipo = evento.get("tipo")
            carga = evento.get("dados", {}).get("carga")
            if tipo == "analise_concluida" and carga:
                self.processar_carga_analisada(cliente, carga)
            elif tipo == "carga_aprovada" and carga:
                if not self._esta_guardada(cliente, carga):
                    self.preparar_distribuicao(cliente, carga)
        self.processar_ciclo(cliente, novos_eventos)

    def _escolher_politica(
        self,
        carga: CargaParaPesquisa | None,
        qualidade: float,
    ) -> PoliticaDeAprovacao | None:
        if carga is None:
            return PoliticaDeAprovacao.COMERCIAL
        if carga.mineral == Mineral.CRISTAL_MARCIANO_RARO:
            if qualidade >= 85.0:
                return PoliticaDeAprovacao.PREMIUM
            if qualidade >= 70.0:
                return PoliticaDeAprovacao.ESTRITA
            return None
        if carga.mineral == Mineral.JAROSITA and qualidade >= 70.0:
            return PoliticaDeAprovacao.ESTRITA
        return PoliticaDeAprovacao.COMERCIAL

    def processar_carga_analisada(
        self,
        cliente: ClienteDoMundo,
        identificador: str,
    ) -> PoliticaDeAprovacao | None:
        """Classifica e solicita aprovação comercial da carga analisada."""
        dados = cliente.chamar(
            "POST",
            "/pesquisa/classificar-carga",
            {"identificador_da_carga": identificador},
        )
        qualidade = dados.get("qualidade")
        if qualidade is None:
            raise ValueError("A carga ainda não foi analisada")

        carga = self.cargas.get(identificador)
        politica = self._escolher_politica(carga, float(qualidade))

        if politica is None:
            if identificador not in self.rejeicoes_solicitadas:
                cliente.chamar(
                    "POST",
                    "/pesquisa/rejeitar-carga",
                    {"identificador_da_carga": identificador},
                )
                self.rejeicoes_solicitadas.add(identificador)
            return None

        if identificador not in self.aprovacoes_solicitadas:
            cliente.chamar(
                "POST",
                "/pesquisa/aprovar-carga",
                {"identificador_da_carga": identificador, "politica": politica.value},
            )
            self.aprovacoes_solicitadas.add(identificador)
        return politica

    def preparar_distribuicao(
        self,
        cliente: ClienteDoMundo,
        identificador: str,
    ) -> str:
        """Obtém uma autorização e agenda a entrega da carga aprovada."""
        if identificador in self.distribuicoes_solicitadas:
            return identificador
        autorizacao = cliente.chamar(
            "POST",
            "/missao/autorizar-missao",
            {
                "operacao": "preparar_distribuicao",
                "central_solicitante": "pesquisa",
                "classe": ClasseDeAutorizacao.RAPIDA.value,
            },
        )
        cliente.chamar(
            "POST",
            "/pesquisa/preparar-distribuicao",
            {
                "identificador_da_carga": identificador,
                "id_autorizacao": autorizacao["id_autorizacao"],
            },
        )
        self.distribuicoes_solicitadas.add(identificador)
        return identificador
