from __future__ import annotations

from enum import Enum


class StatusDeAvaliacao(str, Enum):
    OK = "ok"
    FALHA_OPERACIONAL = "falha_operacional"
    LIMITE_EXCEDIDO = "limite_excedido"
    ERRO_DE_CONFIGURACAO = "erro_de_configuracao"
    INTEGRIDADE_REPROVADA = "integridade_reprovada"
