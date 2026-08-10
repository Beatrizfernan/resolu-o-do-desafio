from __future__ import annotations

from avaliador.aplicacao.cliente_de_avaliacao import ClienteDeAvaliacao
from avaliador.aplicacao.coletor_de_metricas import agregar_resultados, coletar_resultado_da_seed
from avaliador.aplicacao.renderizador_markdown import renderizar_relatorio_markdown
from avaliador.dominio.status_de_avaliacao import StatusDeAvaliacao


def test_coleta_metricas_basicas_da_seed():
    cliente = ClienteDeAvaliacao()
    cliente.resetar(semente=11)
    cliente.avancar_ciclo(1)

    resultado = coletar_resultado_da_seed(11, cliente, StatusDeAvaliacao.OK)

    assert resultado.seed == 11
    assert resultado.ciclo_final == 1
    assert resultado.faturamento_total >= 0.0
    assert resultado.energia_encalhada >= 0.0


def test_renderiza_relatorio_markdown_deterministico():
    cliente = ClienteDeAvaliacao()
    cliente.resetar(semente=12)
    resultado = coletar_resultado_da_seed(12, cliente, StatusDeAvaliacao.OK)
    relatorio = agregar_resultados([resultado], True, [], {"seeds": [12], "limite_de_ciclos": 5})

    markdown = renderizar_relatorio_markdown(relatorio)

    assert "# Relatorio de Avaliacao" in markdown
    assert "## Status" in markdown
    assert "## Resultados por seed" in markdown
    assert "12" in markdown


def test_renderiza_bloqueio_por_integridade_sem_placar():
    relatorio = agregar_resultados([], False, ["Hash divergente: mundo/x.py"], {"seeds": [1]})

    markdown = renderizar_relatorio_markdown(relatorio)

    assert "Integridade: reprovada" in markdown
    assert "avaliacao foi abortada" in markdown.lower()
    assert "## Resultados por seed" not in markdown
