from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .manifesto import calcular_hash_do_arquivo, iterar_arquivos_protegidos


@dataclass(frozen=True)
class ResultadoDaIntegridade:
    aprovada: bool
    divergencias: list[str]
    manifesto_lido: dict | None


def verificar_integridade(raiz_do_projeto: Path, caminho_do_manifesto: Path) -> ResultadoDaIntegridade:
    if not caminho_do_manifesto.exists():
        return ResultadoDaIntegridade(
            aprovada=False,
            divergencias=[f"Manifesto ausente: {caminho_do_manifesto}"],
            manifesto_lido=None,
        )

    manifesto = json.loads(caminho_do_manifesto.read_text())
    hashes_esperados = manifesto.get("arquivos", {})
    hashes_atuais = {
        str(caminho.relative_to(raiz_do_projeto)): calcular_hash_do_arquivo(caminho)
        for caminho in iterar_arquivos_protegidos(raiz_do_projeto)
    }

    divergencias: list[str] = []
    for caminho_relativo, hash_esperado in hashes_esperados.items():
        hash_atual = hashes_atuais.get(caminho_relativo)
        if hash_atual is None:
            divergencias.append(f"Arquivo protegido ausente: {caminho_relativo}")
            continue
        if hash_atual != hash_esperado:
            divergencias.append(f"Hash divergente: {caminho_relativo}")

    for caminho_relativo in hashes_atuais:
        if caminho_relativo not in hashes_esperados:
            divergencias.append(f"Arquivo protegido novo nao manifestado: {caminho_relativo}")

    return ResultadoDaIntegridade(
        aprovada=not divergencias,
        divergencias=divergencias,
        manifesto_lido=manifesto,
    )
