from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class CatalogoDePesquisa:
    capacidade_paralela: int
    custo_base_de_analise: float
    limiar_qualidade_aprovacao: float

    @classmethod
    def carregar_de_arquivo(cls, caminho: Path) -> "CatalogoDePesquisa":
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return cls(**dados)
