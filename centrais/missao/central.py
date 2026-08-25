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
        for destino, quantidade in self.orcamento.items():
            # O orçamento inicial é um compromisso deliberado. A política de
            # contingência limita cada repasse ao colchão de 5.0 definido pela
            # API; aplicada aqui, ela deixaria Extração com apenas 15.0 e
            # impediria a primeira operação valiosa. Contingência continua
            # disponível para repasses incrementais após esta distribuição.
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
