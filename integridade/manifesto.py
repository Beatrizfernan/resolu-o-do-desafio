from __future__ import annotations

import hashlib
import json
from pathlib import Path


ESCOPOS_PROTEGIDOS = ("mundo", "avaliador")
ARQUIVOS_NA_RAIZ = ("pyproject.toml",)
DIRETORIOS_IGNORADOS = {"__pycache__", ".pytest_cache"}


def iterar_arquivos_protegidos(raiz_do_projeto: Path) -> list[Path]:
    arquivos: list[Path] = []
    for nome_do_escopo in ESCOPOS_PROTEGIDOS:
        base = raiz_do_projeto / nome_do_escopo
        if not base.exists():
            continue
        for caminho in sorted(base.rglob("*")):
            if caminho.is_dir() or caminho.suffix == ".pyc":
                continue
            if any(parte in DIRETORIOS_IGNORADOS for parte in caminho.parts):
                continue
            arquivos.append(caminho)
    for nome_do_arquivo in ARQUIVOS_NA_RAIZ:
        caminho = raiz_do_projeto / nome_do_arquivo
        if caminho.exists():
            arquivos.append(caminho)
    return sorted(arquivos)


def calcular_hash_do_arquivo(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def gerar_manifesto(raiz_do_projeto: Path, caminho_do_manifesto: Path) -> dict:
    arquivos = {
        str(caminho.relative_to(raiz_do_projeto)): calcular_hash_do_arquivo(caminho)
        for caminho in iterar_arquivos_protegidos(raiz_do_projeto)
    }
    manifesto = {
        "versao": 1,
        "algoritmo": "sha256",
        "arquivos": arquivos,
    }
    caminho_do_manifesto.parent.mkdir(parents=True, exist_ok=True)
    caminho_do_manifesto.write_text(json.dumps(manifesto, indent=2, sort_keys=True) + "\n")
    return manifesto
