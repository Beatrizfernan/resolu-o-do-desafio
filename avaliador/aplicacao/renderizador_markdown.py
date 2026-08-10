from __future__ import annotations

from avaliador.dominio.relatorio_de_avaliacao import RelatorioDeAvaliacao


def renderizar_relatorio_markdown(relatorio: RelatorioDeAvaliacao) -> str:
    linhas = ["# Relatorio de Avaliacao", "", "## Status"]
    linhas.append(f"- Integridade: {'aprovada' if relatorio.integridade_aprovada else 'reprovada'}")

    if not relatorio.integridade_aprovada:
        linhas.append("- A avaliacao foi abortada por falha de integridade.")
        linhas.append("")
        linhas.append("## Divergencias")
        linhas.extend(f"- {divergencia}" for divergencia in relatorio.divergencias_de_integridade)
        return "\n".join(linhas) + "\n"

    linhas.extend(
        [
            f"- Seeds executadas: {len(relatorio.resultados)}",
            f"- Falhas operacionais: {sum(1 for resultado in relatorio.resultados if resultado.erro_operacional)}",
            "",
            "## Resultado agregado",
            f"- Faturamento medio: {relatorio.faturamento_medio:.2f}",
            f"- Faturamento mediano: {relatorio.faturamento_mediano:.2f}",
            f"- Ciclo medio de encerramento: {relatorio.ciclo_medio_de_encerramento:.2f}",
            f"- Energia encalhada media: {relatorio.energia_encalhada_media:.2f}",
            "",
            "## Resultados por seed",
            "| Seed | Status | Faturamento | Ciclo final | Energia encalhada |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for resultado in relatorio.resultados:
        linhas.append(
            f"| {resultado.seed} | {resultado.status.value} | {resultado.faturamento_total:.2f} | {resultado.ciclo_final} | {resultado.energia_encalhada:.2f} |"
        )
    return "\n".join(linhas) + "\n"
