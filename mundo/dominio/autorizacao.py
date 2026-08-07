from __future__ import annotations

import itertools
from dataclasses import dataclass


class AutorizacaoInvalidaError(Exception):
    pass


@dataclass(frozen=True)
class Autorizacao:
    identificador: str
    operacao: str
    central_solicitante: str
    usada: bool = False


class RegistroDeAutorizacoes:
    def __init__(self) -> None:
        self._contador = itertools.count(1)
        self._autorizacoes: dict[str, Autorizacao] = {}

    def emitir(self, operacao: str, central_solicitante: str) -> Autorizacao:
        identificador = f"aut-{next(self._contador)}"
        autorizacao = Autorizacao(identificador, operacao, central_solicitante)
        self._autorizacoes[identificador] = autorizacao
        return autorizacao

    def consumir(self, identificador: str, operacao: str) -> None:
        autorizacao = self._autorizacoes.get(identificador)
        if autorizacao is None or autorizacao.usada or autorizacao.operacao != operacao:
            raise AutorizacaoInvalidaError(identificador)
        self._autorizacoes[identificador] = Autorizacao(
            autorizacao.identificador, autorizacao.operacao, autorizacao.central_solicitante, usada=True,
        )
