from __future__ import annotations

from pathlib import Path

from integridade.manifesto import gerar_manifesto
from integridade.verificador import verificar_integridade


def test_gera_e_verifica_manifesto_sem_alteracoes(tmp_path: Path):
    (tmp_path / "mundo").mkdir()
    (tmp_path / "mundo" / "arquivo.py").write_text("print('ok')\n")
    (tmp_path / "avaliador").mkdir()
    (tmp_path / "avaliador" / "cli.py").write_text("print('cli')\n")
    (tmp_path / "centrais").mkdir()
    (tmp_path / "centrais" / "avaliacao.py").write_text("# livre\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    manifesto = tmp_path / "integridade" / "manifesto.sha256.json"
    manifesto.parent.mkdir()

    gerar_manifesto(tmp_path, manifesto)
    resultado = verificar_integridade(tmp_path, manifesto)

    assert resultado.aprovada is True
    assert resultado.divergencias == []


def test_detecta_arquivo_protegido_alterado_e_ignora_centrais(tmp_path: Path):
    (tmp_path / "mundo").mkdir()
    arquivo_protegido = tmp_path / "mundo" / "arquivo.py"
    arquivo_protegido.write_text("print('a')\n")
    (tmp_path / "avaliador").mkdir()
    (tmp_path / "avaliador" / "cli.py").write_text("print('cli')\n")
    (tmp_path / "centrais").mkdir()
    arquivo_livre = tmp_path / "centrais" / "avaliacao.py"
    arquivo_livre.write_text("print('livre')\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    manifesto = tmp_path / "integridade" / "manifesto.sha256.json"
    manifesto.parent.mkdir()

    gerar_manifesto(tmp_path, manifesto)
    arquivo_protegido.write_text("print('b')\n")
    arquivo_livre.write_text("print('mudou mas pode')\n")

    resultado = verificar_integridade(tmp_path, manifesto)

    assert resultado.aprovada is False
    assert any("mundo/arquivo.py" in item for item in resultado.divergencias)
    assert all("centrais/avaliacao.py" not in item for item in resultado.divergencias)


def test_detecta_arquivo_protegido_ausente_ou_novo(tmp_path: Path):
    (tmp_path / "mundo").mkdir()
    arquivo = tmp_path / "mundo" / "arquivo.py"
    arquivo.write_text("print('a')\n")
    (tmp_path / "avaliador").mkdir()
    (tmp_path / "avaliador" / "cli.py").write_text("print('cli')\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    manifesto = tmp_path / "integridade" / "manifesto.sha256.json"
    manifesto.parent.mkdir()

    gerar_manifesto(tmp_path, manifesto)
    arquivo.unlink()
    (tmp_path / "mundo" / "novo.py").write_text("print('novo')\n")

    resultado = verificar_integridade(tmp_path, manifesto)

    assert resultado.aprovada is False
    assert any("ausente" in item.lower() for item in resultado.divergencias)
    assert any("novo" in item.lower() for item in resultado.divergencias)
