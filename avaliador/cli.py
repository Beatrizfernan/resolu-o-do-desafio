from __future__ import annotations

import argparse
from pathlib import Path

from avaliador.aplicacao.avaliador_offline import AvaliadorOffline


def _parsear_seeds(argumentos: argparse.Namespace) -> list[int]:
    if argumentos.seeds:
        return [int(item) for item in argumentos.seeds.split(",") if item]
    return [argumentos.seed_inicial + deslocamento for deslocamento in range(argumentos.quantidade_seeds)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds")
    parser.add_argument("--quantidade-seeds", type=int, default=5)
    parser.add_argument("--seed-inicial", type=int, default=1000)
    parser.add_argument("--saida", default="docs/relatorios/avaliacao.md")
    parser.add_argument("--limite-de-ciclos", type=int, default=5000)
    parser.add_argument("--manifesto", default="integridade/manifesto.sha256.json")
    parser.add_argument("--mostrar-relatorio", action="store_true")
    argumentos = parser.parse_args()

    caminho_de_saida = Path(argumentos.saida)
    avaliador = AvaliadorOffline(raiz_do_projeto=Path.cwd())
    relatorio = avaliador.avaliar(
        seeds=_parsear_seeds(argumentos),
        limite_de_ciclos=argumentos.limite_de_ciclos,
        caminho_do_manifesto=Path(argumentos.manifesto),
        caminho_de_saida=caminho_de_saida,
    )
    if argumentos.mostrar_relatorio:
        print(caminho_de_saida.read_text(), end="")
    return 0 if relatorio.integridade_aprovada else 1


if __name__ == "__main__":
    raise SystemExit(main())
