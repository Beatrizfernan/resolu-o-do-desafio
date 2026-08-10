from __future__ import annotations

from pathlib import Path

import pytest

from avaliador.aplicacao.carregador_de_centrais import carregar_executor
from avaliador.aplicacao.cliente_de_avaliacao import ClienteDeAvaliacao


def test_carrega_executor_valido(tmp_path: Path):
    pasta = tmp_path / "centrais"
    pasta.mkdir()
    (pasta / "avaliacao.py").write_text(
        "def executar_avaliacao(cliente, limite_de_ciclos):\n"
        "    cliente.avancar_ciclo()\n"
    )

    executor = carregar_executor(tmp_path)

    assert callable(executor)


def test_falha_quando_executar_avaliacao_nao_existe(tmp_path: Path):
    pasta = tmp_path / "centrais"
    pasta.mkdir()
    (pasta / "avaliacao.py").write_text("x = 1\n")

    with pytest.raises(RuntimeError, match="executar_avaliacao"):
        carregar_executor(tmp_path)


def test_cliente_controla_o_mundo_e_expoe_rotas_existentes():
    cliente = ClienteDeAvaliacao()
    cliente.resetar(semente=7)

    estado = cliente.consultar_estado()
    jazidas = cliente.chamar("GET", "/extracao/jazidas")
    cliente.avancar_ciclo(2)
    eventos = cliente.consultar_eventos(0)

    assert estado["ciclo_atual"] == 0
    assert isinstance(jazidas, list)
    assert cliente.consultar_estado()["ciclo_atual"] == 2
    assert isinstance(eventos, list)
