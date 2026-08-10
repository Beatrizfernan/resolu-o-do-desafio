from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CatalogoDeOperacao:
    """O que custa existir e o que custa autorizar.

    Existir por ciclo é o que impede a indecisão de ser gratuita: um robô
    parado ainda consome. Autorizar é o que dá preço a operar em muitas
    chamadas pequenas em vez de agrupar.
    """

    consumo_por_ciclo_da_central: float
    custo_de_autorizacao: float

    @classmethod
    def carregar_de_arquivo(cls, caminho: Path) -> "CatalogoDeOperacao":
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return cls(
            consumo_por_ciclo_da_central=dados["consumo_por_ciclo_da_central"],
            custo_de_autorizacao=dados["custo_de_autorizacao"],
        )
