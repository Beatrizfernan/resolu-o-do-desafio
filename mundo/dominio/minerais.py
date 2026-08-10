from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Mineral:
    nome: str
    valor_por_unidade: float
    raridade: float
    custo_extracao: float
    massa: float
    taxa_degradacao: float
    sensibilidade_temperatura: float
    sensibilidade_transporte: float
    sensibilidade_armazenagem: float
    ciclos_de_analise: int


class CatalogoDeMinerais:
    def __init__(self, minerais: dict[str, Mineral]) -> None:
        self._minerais = minerais

    @classmethod
    def carregar_de_arquivo(cls, caminho: Path) -> "CatalogoDeMinerais":
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        minerais = {item["nome"]: Mineral(**item) for item in dados}
        return cls(minerais)

    def obter(self, nome: str) -> Mineral:
        if nome not in self._minerais:
            raise ValueError(f"Mineral desconhecido: {nome}")
        return self._minerais[nome]

    def todos(self) -> list[Mineral]:
        return list(self._minerais.values())
