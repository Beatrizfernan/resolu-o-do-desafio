from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CatalogoDeArmazenagem:
    """Os quatro preços da armazenagem posicional.

    Volume paga guardar e manter; contagem de itens paga remexer. É essa
    assimetria que faz a ordem da pilha importar sem que nenhuma regra
    mande ordenar.
    """

    custo_de_armazenagem_por_unidade: float
    custo_de_manutencao_por_unidade: float
    custo_por_movimento: float
    custo_por_desempilhamento: float

    @classmethod
    def carregar_de_arquivo(cls, caminho: Path) -> "CatalogoDeArmazenagem":
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return cls(
            custo_de_armazenagem_por_unidade=dados["custo_de_armazenagem_por_unidade"],
            custo_de_manutencao_por_unidade=dados["custo_de_manutencao_por_unidade"],
            custo_por_movimento=dados["custo_por_movimento"],
            custo_por_desempilhamento=dados["custo_por_desempilhamento"],
        )
