from __future__ import annotations

from pathlib import Path

from avaliador.aplicacao.avaliador_offline import AvaliadorOffline
from avaliador.cli import main
from integridade.manifesto import gerar_manifesto


def test_avaliador_gera_relatorio_markdown(tmp_path: Path):
    raiz_do_projeto = Path.cwd()
    manifesto = tmp_path / "manifesto.sha256.json"
    saida = tmp_path / "relatorio.md"
    gerar_manifesto(raiz_do_projeto, manifesto)

    avaliador = AvaliadorOffline(raiz_do_projeto=raiz_do_projeto)
    relatorio = avaliador.avaliar([1, 2], 1, manifesto, saida)

    assert saida.exists()
    assert len(relatorio.resultados) == 2
    assert "# Relatorio de Avaliacao" in saida.read_text()


def test_avaliador_aborta_quando_manifesto_nao_existe(tmp_path: Path):
    raiz_do_projeto = Path.cwd()
    manifesto = tmp_path / "manifesto-ausente.json"
    saida = tmp_path / "relatorio.md"

    avaliador = AvaliadorOffline(raiz_do_projeto=raiz_do_projeto)
    relatorio = avaliador.avaliar([1], 1, manifesto, saida)

    assert relatorio.integridade_aprovada is False
    assert saida.exists()
    assert "Integridade: reprovada" in saida.read_text()


def test_cli_retorna_zero_quando_integridade_aprova(monkeypatch, tmp_path: Path):
    raiz_do_projeto = Path.cwd()
    manifesto = tmp_path / "manifesto.sha256.json"
    gerar_manifesto(raiz_do_projeto, manifesto)
    saida = tmp_path / "saida.md"

    monkeypatch.chdir(raiz_do_projeto)
    monkeypatch.setattr(
        "sys.argv",
        [
            "avaliador.cli",
            "--seeds",
            "1,2",
            "--limite-de-ciclos",
            "1",
            "--manifesto",
            str(manifesto),
            "--saida",
            str(saida),
        ],
    )

    codigo = main()

    assert codigo == 0
    assert saida.exists()


def test_cli_pode_exibir_relatorio_no_stdout(monkeypatch, tmp_path: Path, capsys):
    raiz_do_projeto = Path.cwd()
    manifesto = tmp_path / "manifesto.sha256.json"
    gerar_manifesto(raiz_do_projeto, manifesto)
    saida = tmp_path / "saida.md"

    monkeypatch.chdir(raiz_do_projeto)
    monkeypatch.setattr(
        "sys.argv",
        [
            "avaliador.cli",
            "--seeds",
            "1",
            "--limite-de-ciclos",
            "1",
            "--manifesto",
            str(manifesto),
            "--saida",
            str(saida),
            "--mostrar-relatorio",
        ],
    )

    codigo = main()

    capturado = capsys.readouterr()
    assert codigo == 0
    assert "# Relatorio de Avaliacao" in capturado.out
    assert "## Resultado agregado" in capturado.out
