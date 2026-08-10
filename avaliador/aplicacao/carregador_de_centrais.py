from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Callable


def carregar_executor(raiz_do_projeto: Path) -> Callable:
    caminho = raiz_do_projeto / "centrais" / "avaliacao.py"
    if not caminho.exists():
        raise RuntimeError(f"Arquivo de avaliacao ausente: {caminho}")

    spec = importlib.util.spec_from_file_location("centrais.avaliacao", caminho)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nao foi possivel carregar: {caminho}")

    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    executor = getattr(modulo, "executar_avaliacao", None)
    if not callable(executor):
        raise RuntimeError("centrais/avaliacao.py deve expor executar_avaliacao(cliente, limite_de_ciclos)")
    return executor
