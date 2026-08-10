from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import traceback

from avaliador.aplicacao.carregador_de_centrais import carregar_executor
from avaliador.aplicacao.cliente_de_avaliacao import ClienteDeAvaliacao
from avaliador.aplicacao.coletor_de_metricas import agregar_resultados, coletar_resultado_da_seed
from avaliador.aplicacao.renderizador_markdown import renderizar_relatorio_markdown
from avaliador.dominio.relatorio_de_avaliacao import RelatorioDeAvaliacao
from avaliador.dominio.status_de_avaliacao import StatusDeAvaliacao
from integridade.verificador import verificar_integridade


@dataclass
class AvaliadorOffline:
    raiz_do_projeto: Path

    def avaliar(
        self,
        seeds: list[int],
        limite_de_ciclos: int,
        caminho_do_manifesto: Path,
        caminho_de_saida: Path,
    ) -> RelatorioDeAvaliacao:
        resultado_da_integridade = verificar_integridade(self.raiz_do_projeto, caminho_do_manifesto)
        if not resultado_da_integridade.aprovada:
            relatorio = agregar_resultados(
                resultados=[],
                integridade_aprovada=False,
                divergencias=resultado_da_integridade.divergencias,
                configuracao={"seeds": seeds, "limite_de_ciclos": limite_de_ciclos},
            )
            self._escrever_relatorio(caminho_de_saida, relatorio)
            return relatorio

        try:
            executor = carregar_executor(self.raiz_do_projeto)
        except RuntimeError as erro:
            relatorio = agregar_resultados(
                resultados=[],
                integridade_aprovada=True,
                divergencias=[],
                configuracao={
                    "seeds": seeds,
                    "limite_de_ciclos": limite_de_ciclos,
                    "erro_de_configuracao": str(erro),
                },
            )
            self._escrever_relatorio(caminho_de_saida, relatorio)
            return relatorio

        resultados = []
        for seed in seeds:
            cliente = ClienteDeAvaliacao()
            cliente.resetar(seed)
            status = StatusDeAvaliacao.OK
            erro_operacional = None
            try:
                executor(cliente, limite_de_ciclos)
                if not cliente.simulacao_encerrada() and cliente.consultar_estado()["ciclo_atual"] >= limite_de_ciclos:
                    status = StatusDeAvaliacao.LIMITE_EXCEDIDO
            except Exception:
                status = StatusDeAvaliacao.FALHA_OPERACIONAL
                erro_operacional = traceback.format_exc(limit=5)
            resultados.append(
                coletar_resultado_da_seed(
                    seed=seed,
                    cliente=cliente,
                    status=status,
                    erro_operacional=erro_operacional,
                )
            )

        relatorio = agregar_resultados(
            resultados=resultados,
            integridade_aprovada=True,
            divergencias=[],
            configuracao={"seeds": seeds, "limite_de_ciclos": limite_de_ciclos},
        )
        self._escrever_relatorio(caminho_de_saida, relatorio)
        return relatorio

    def _escrever_relatorio(self, caminho_de_saida: Path, relatorio: RelatorioDeAvaliacao) -> None:
        caminho_de_saida.parent.mkdir(parents=True, exist_ok=True)
        caminho_de_saida.write_text(renderizar_relatorio_markdown(relatorio))
