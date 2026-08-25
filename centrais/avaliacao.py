"""Orquestração das centrais durante a avaliação."""

from __future__ import annotations

from centrais.extracao import CentralDeExtracao
from centrais.missao import CentralDeMissao
from centrais.pesquisa.central import CentralDePesquisa
from centrais.transporte import CentralDeTransporte


def executar_avaliacao(cliente, limite_de_ciclos: int) -> None:
    ultimo_ciclo_lido = 0
    energia_inicial_alocada = False
    central_de_missao = CentralDeMissao(cliente)
    central_de_extracao = CentralDeExtracao(cliente)
    central_de_pesquisa = CentralDePesquisa()
    central_de_transporte = CentralDeTransporte()

    for _ in range(limite_de_ciclos):
        if cliente.simulacao_encerrada():
            return

        estado = central_de_missao.consultar_estado()
        ciclo_atual = estado["ciclo_atual"]
        eventos = central_de_missao.consultar_eventos(desde_ciclo=ultimo_ciclo_lido)

        for evento in eventos:
            ultimo_ciclo_lido = max(ultimo_ciclo_lido, evento["ciclo"] + 1)
            tipo = evento["tipo"]
            dados = evento["dados"]
            central_de_extracao.processar_evento(evento)

            if tipo in {"extracao_concluida", "extracao_interrompida"} and dados.get("unidade"):
                cliente.chamar("POST", "/extracao/retornar-unidade", {
                    "identificador_da_unidade": dados["unidade"],
                })
            elif tipo == "operacao_invalida":
                print("[ciclo {}] INVALIDA: {}".format(evento["ciclo"], dados))

        if not energia_inicial_alocada:
            central_de_missao.distribuir_orcamento_inicial()
            energia_inicial_alocada = True

        central_de_extracao.iniciar_proxima_extracao()
        central_de_transporte.tick(cliente, eventos, ciclo_atual)
        central_de_pesquisa.processar_eventos(cliente, eventos)

        cliente.avancar_ciclo()
