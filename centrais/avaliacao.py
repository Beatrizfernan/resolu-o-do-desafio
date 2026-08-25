"""Orquestração das Centrais durante a avaliação."""

from centrais.extracao import CentralDeExtracao
from centrais.missao import CentralDeMissao
from centrais.pesquisa.central import CentralDePesquisa


def executar_avaliacao(cliente, limite_de_ciclos: int) -> None:
    fase = "alocar_energia"
    carga_atual = None
    ultimo_ciclo_lido = 0
    central_de_missao = CentralDeMissao(cliente)
    central_de_extracao = CentralDeExtracao(cliente)
    central_de_pesquisa = CentralDePesquisa()

    for _ in range(limite_de_ciclos):
        if cliente.simulacao_encerrada():
            return

        eventos = central_de_missao.consultar_eventos(desde_ciclo=ultimo_ciclo_lido)
        central_de_pesquisa.processar_eventos(cliente, eventos)

        for evento in eventos:
            ultimo_ciclo_lido = max(ultimo_ciclo_lido, evento["ciclo"] + 1)
            tipo, dados = evento["tipo"], evento["dados"]

            if tipo == "extracao_concluida":
                carga_atual = central_de_extracao.processar_evento(evento)
                fase = "transportar"
                cliente.chamar("POST", "/extracao/retornar-unidade", {
                    "identificador_da_unidade": dados["unidade"],
                })
            elif tipo == "transporte_concluido":
                fase = "aguardando"
                cliente.chamar("POST", "/transporte/retornar-unidade", {
                    "identificador_da_unidade": dados["unidade"],
                })
            elif tipo == "carga_entregue":
                carga_atual = None
                fase = "extrair"
            elif tipo == "operacao_invalida":
                print("[ciclo {}] INVALIDA: {}".format(evento["ciclo"], dados))
            else:
                central_de_extracao.processar_evento(evento)

        if fase == "alocar_energia":
            central_de_missao.distribuir_orcamento_inicial()
            fase = "extrair"
        elif fase == "extrair":
            if central_de_extracao.iniciar_proxima_extracao() is not None:
                fase = "aguardando"
        elif fase == "transportar":
            unidade = _primeiro_robo_disponivel(cliente, "/transporte/transportadores")
            plano = cliente.chamar(
                "GET", f"/transporte/planejar-transporte?identificador_da_carga={carga_atual}"
            )
            rotas = plano.get("rotas_disponiveis", [])
            if unidade and rotas:
                id_autorizacao = central_de_missao.autorizar(
                    "iniciar_viagem", "transporte", classe="rapida",
                )
                cliente.chamar("POST", "/transporte/carregar", {
                    "identificador_da_unidade": unidade["identificador"],
                    "identificador_da_carga": carga_atual,
                })
                cliente.chamar("POST", "/transporte/iniciar-viagem", {
                    "identificador_da_unidade": unidade["identificador"],
                    "identificador_da_rota": rotas[0],
                    "identificador_da_carga": carga_atual,
                    "id_autorizacao": id_autorizacao,
                    "modo": "normal",
                })
                fase = "aguardando"

        cliente.avancar_ciclo()


def _primeiro_robo_disponivel(cliente, rota):
    for robo in cliente.chamar("GET", rota):
        if robo["estado"] == "disponivel":
            return robo
    return None
