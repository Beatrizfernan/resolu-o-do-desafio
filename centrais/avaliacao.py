"""Orquestração da avaliação usando a política da Central de Extração."""

from centrais.extracao import CentralDeExtracao
from centrais.missao import CentralDeMissao


def executar_avaliacao(cliente, limite_de_ciclos: int) -> None:
    fase = "alocar_energia"
    carga_atual = None
    ultimo_ciclo_lido = 0
    central_de_missao = CentralDeMissao(cliente)
    central_de_extracao = CentralDeExtracao(cliente)

    for _ in range(limite_de_ciclos):
        if cliente.simulacao_encerrada():
            return

        # ------------------------------------------------ 1. ver o que houve
        eventos = central_de_missao.consultar_eventos(desde_ciclo=ultimo_ciclo_lido)
        for evento in eventos:
            ultimo_ciclo_lido = max(ultimo_ciclo_lido, evento["ciclo"] + 1)
            tipo, dados = evento["tipo"], evento["dados"]

            if tipo == "extracao_concluida":
                carga_atual = central_de_extracao.processar_evento(evento)
                fase = "transportar"
                # Sem isto a mineradora fica AGUARDANDO para sempre e a
                # segunda extracao nunca acontece.
                cliente.chamar("POST", "/extracao/retornar-unidade", {
                    "identificador_da_unidade": dados["unidade"],
                })
            elif tipo == "transporte_concluido":
                fase = "analisar"
                cliente.chamar("POST", "/transporte/retornar-unidade", {
                    "identificador_da_unidade": dados["unidade"],
                })
            elif tipo == "analise_concluida":
                fase = "aprovar"
            elif tipo == "carga_aprovada":
                fase = "vender"
            elif tipo == "carga_entregue":
                carga_atual = None
                fase = "extrair"
            elif tipo == "operacao_invalida":
                print(f"[ciclo {evento['ciclo']}] INVALIDA: {dados}")
            else:
                central_de_extracao.processar_evento(evento)

        # ------------------------------------------------ 2. agir
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
                # A rota tem que sair do setor da jazida de origem da carga.
                id_autorizacao = central_de_missao.autorizar(
                    "iniciar_viagem", "transporte", classe="rapida",
                )
                cliente.chamar("POST", "/transporte/carregar", {
                    "identificador_da_unidade": unidade["identificador"],
                    "identificador_da_carga": carga_atual,
                })
                cliente.chamar("POST", "/transporte/iniciar-viagem", {
                    "identificador_da_unidade": unidade["identificador"],
                    # ATENCAO: planejar-transporte devolve lista de STRINGS,
                    # nao de dicts. O README nao diz isso.
                    "identificador_da_rota": rotas[0],
                    "identificador_da_carga": carga_atual,
                    "id_autorizacao": id_autorizacao,
                    "modo": "normal",
                })
                fase = "aguardando"

        elif fase == "analisar":
            cliente.chamar("POST", "/pesquisa/iniciar-analise", {
                "identificador_da_carga": carga_atual,
                "tipo_de_analise": "completa",
            })
            fase = "aguardando"

        elif fase == "aprovar":
            cliente.chamar("POST", "/pesquisa/aprovar-carga", {
                "identificador_da_carga": carga_atual,
                "politica": "comercial",
            })
            fase = "aguardando"

        elif fase == "vender":
            id_autorizacao = central_de_missao.autorizar(
                "preparar_distribuicao", "pesquisa", classe="rapida",
            )
            cliente.chamar("POST", "/pesquisa/preparar-distribuicao", {
                "identificador_da_carga": carga_atual,
                "id_autorizacao": id_autorizacao,
            })
            fase = "aguardando"

        # ------------------------------------------------ 3. passar o turno
        cliente.avancar_ciclo()


def _primeiro_robo_disponivel(cliente, rota):
    for robo in cliente.chamar("GET", rota):
        if robo["estado"] == "disponivel":
            return robo
    return None
