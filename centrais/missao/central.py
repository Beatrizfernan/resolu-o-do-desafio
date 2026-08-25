from __future__ import annotations

from collections.abc import Mapping
from typing import Any


ORCAMENTO_INICIAL: Mapping[str, int] = {
    "extracao": 250,
    "transporte": 250,
    "pesquisa": 250,
    "armazenagem": 20,
    "missao": 100,
}


class CentralDeMissao:
    """Coordena energia, autorizações e observabilidade global.

    A central conhece apenas o cliente de avaliação. O motor continua sendo
    responsável por validar e aplicar as mutações no ciclo correto.
    """

    def __init__(
        self,
        cliente: Any,
        *,
        orcamento: Mapping[str, int] = ORCAMENTO_INICIAL,
    ) -> None:
        self.cliente = cliente
        self.orcamento = orcamento

    def consultar_estado(self) -> dict:
        return self.cliente.chamar("GET", "/missao/estado")

    def consultar_eventos(self, desde_ciclo: int = 0) -> list[dict]:
        return self.cliente.consultar_eventos(desde_ciclo)

    def distribuir_orcamento_inicial(self) -> None:
        # ATENCAO (beatriz): estava `contingencia` e travava tudo no ciclo 2.
        # A contingencia limita pelo saldo da PROPRIA missao, nao pela reserva:
        #   quantidade = min(pedido, max(0, saldo_da_missao - 5.0))
        # Como a missao comeca com 10, cada central recebia 5 em vez de 250, e
        # a primeira extracao morria com EnergiaInsuficienteError. Na
        # distribuicao inicial a politica tem que ser `pulso`.
        for destino, quantidade in self.orcamento.items():
            self.alocar_energia(destino, quantidade, politica="pulso")

    def alocar_energia(
        self,
        destino: str,
        quantidade: int,
        *,
        politica: str = "contingencia",
    ) -> dict:
        if quantidade <= 0:
            raise ValueError("Quantidade de energia deve ser positiva")
        return self.cliente.chamar(
            "POST",
            "/missao/alocar-energia",
            {
                "destino": destino,
                "quantidade": quantidade,
                "politica": politica,
            },
        )

    def autorizar(
        self,
        operacao: str,
        central_solicitante: str,
        *,
        classe: str = "rapida",
    ) -> str:
        resposta = self.cliente.chamar(
            "POST",
            "/missao/autorizar-missao",
            {
                "operacao": operacao,
                "central_solicitante": central_solicitante,
                "classe": classe,
            },
        )
        return resposta["id_autorizacao"]

    def missao_operante(self) -> bool:
        estado = self.consultar_estado()
        return estado["energia"]["missao"] > 0.0
