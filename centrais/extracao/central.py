from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class RegraDeExtracao:
    prioridade: int
    tipo_da_unidade: str
    modo: str
    perfil_de_escavacao: str
    fator_desperdicio: float


@dataclass(frozen=True)
class PlanoDeExtracao:
    identificador_da_jazida: str
    identificador_da_unidade: str
    quantidade: float
    modo: str
    perfil_de_escavacao: str


class CentralDeExtracao:
    """Planeja a extração sem acoplar a estratégia ao motor do mundo.

    A central recebe apenas os snapshots expostos pelas APIs. Isso deixa a
    escolha determinística, barata e independente do estado interno do motor.
    A reserva de jazida e unidade evita enviar duas ordens para o mesmo recurso
    antes de o evento da primeira operação chegar.
    """

    REGRAS: dict[str, RegraDeExtracao] = {
        "hematita": RegraDeExtracao(1, "leve", "agressivo", "superficial", 1.4),
        "silica_de_alta_pureza": RegraDeExtracao(2, "leve", "normal", "superficial", 1.2),
        "jarosita": RegraDeExtracao(3, "precisa", "normal", "mapeadora", 1.2),
        "gelo_de_agua": RegraDeExtracao(4, "precisa", "normal", "mapeadora", 1.2),
        "cristal_marciano_raro": RegraDeExtracao(5, "precisa", "cuidadoso", "superficial", 1.0),
    }

    def __init__(self, cliente: Any | None = None) -> None:
        self.cliente = cliente
        self._jazidas_reservadas: set[str] = set()
        self._unidades_reservadas: set[str] = set()

    def planejar(
        self,
        jazidas: Iterable[Mapping[str, Any]],
        mineradoras: Iterable[Mapping[str, Any]],
    ) -> PlanoDeExtracao | None:
        mineradoras_disponiveis = [
            mineradora
            for mineradora in mineradoras
            if mineradora.get("estado") == "disponivel"
            and mineradora.get("identificador") not in self._unidades_reservadas
        ]
        if not mineradoras_disponiveis:
            return None

        jazidas_disponiveis = sorted(
            (
                jazida
                for jazida in jazidas
                if jazida.get("estado") == "disponivel"
                and jazida.get("identificador") not in self._jazidas_reservadas
                and float(jazida.get("quantidade_disponivel", 0.0)) > 0.0
                and jazida.get("mineral") in self.REGRAS
            ),
            key=lambda jazida: (
                -self.REGRAS[jazida["mineral"]].prioridade,
                jazida["identificador"],
            ),
        )

        for jazida in jazidas_disponiveis:
            regra = self.REGRAS[jazida["mineral"]]
            unidade = self._escolher_unidade(mineradoras_disponiveis, regra)
            if unidade is None:
                continue

            quantidade = min(
                float(unidade["capacidade"]),
                float(jazida["quantidade_disponivel"]) / regra.fator_desperdicio,
            )
            if quantidade <= 0.0:
                continue

            return PlanoDeExtracao(
                identificador_da_jazida=jazida["identificador"],
                identificador_da_unidade=unidade["identificador"],
                quantidade=quantidade,
                modo=regra.modo,
                perfil_de_escavacao=regra.perfil_de_escavacao,
            )
        return None

    def iniciar_proxima_extracao(self) -> PlanoDeExtracao | None:
        if self.cliente is None:
            raise RuntimeError("Central de extração precisa de um cliente para iniciar operações")

        plano = self.planejar(
            self.cliente.chamar("GET", "/extracao/jazidas"),
            self.cliente.chamar("GET", "/extracao/mineradoras"),
        )
        if plano is None:
            return None

        self.cliente.chamar(
            "POST",
            "/extracao/iniciar-extracao",
            {
                "identificador_da_unidade": plano.identificador_da_unidade,
                "identificador_da_jazida": plano.identificador_da_jazida,
                "quantidade": plano.quantidade,
                "modo": plano.modo,
                "perfil_de_escavacao": plano.perfil_de_escavacao,
            },
        )
        self._jazidas_reservadas.add(plano.identificador_da_jazida)
        self._unidades_reservadas.add(plano.identificador_da_unidade)
        return plano

    def processar_evento(self, evento: Mapping[str, Any]) -> str | None:
        """Libera recursos e devolve a carga no evento de conclusão.

        O retorno é o identificador que a Central de Transporte precisa para
        planejar a viagem. A central não chama Transporte diretamente: o
        barramento continua sendo a fronteira entre as duas centrais.
        """
        tipo = evento.get("tipo")
        dados = evento.get("dados", {})
        if tipo not in {"extracao_concluida", "extracao_interrompida"}:
            return None

        jazida = dados.get("jazida")
        unidade = dados.get("unidade")
        if jazida is not None:
            self._jazidas_reservadas.discard(jazida)
        if unidade is not None:
            self._unidades_reservadas.discard(unidade)
        return dados.get("carga") if tipo == "extracao_concluida" else None

    @staticmethod
    def _escolher_unidade(
        mineradoras: list[Mapping[str, Any]], regra: RegraDeExtracao,
    ) -> Mapping[str, Any] | None:
        compativeis = [
            mineradora
            for mineradora in mineradoras
            if float(mineradora.get("capacidade", 0.0)) > 0.0
        ]
        if not compativeis:
            return None
        return min(
            compativeis,
            key=lambda mineradora: (
                mineradora.get("tipo") != regra.tipo_da_unidade,
                -float(mineradora.get("capacidade", 0.0)),
                mineradora["identificador"],
            ),
        )
