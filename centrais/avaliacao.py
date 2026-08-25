"""SPIKE DESCARTAVEL - prova que a cadeia fecha e gera faturamento.

NAO E ARQUITETURA. Nao otimiza nada. Pega a primeira jazida, o primeiro robo,
a primeira rota compativel, modo normal, politica comercial. Trata UMA carga
por vez, do inicio ao fim, e so entao comeca a proxima.

Serve para uma coisa so: ver o faturamento sair de 0.00 e provar que a
sequencia extrair -> transportar -> analisar -> aprovar -> vender funciona.
Depois de entender, DELETE e escreva a versao de verdade.
"""

QUANTIDADE_POR_EXTRACAO = 20.0

# A energia alocada nunca volta, entao um spike gasta a reserva sem cerimonia.
# Uma solucao de verdade decide isso ciclo a ciclo.
ORCAMENTO_INICIAL = {
    "extracao": 250,
    "transporte": 250,
    "pesquisa": 250,
    "armazenagem": 20,
    "missao": 100,
}


def executar_avaliacao(cliente, limite_de_ciclos: int) -> None:
    fase = "alocar_energia"
    carga_atual = None
    ultimo_ciclo_lido = 0
    jazidas_ja_usadas = set()

    for _ in range(limite_de_ciclos):
        if cliente.simulacao_encerrada():
            return

        # ------------------------------------------------ 1. ver o que houve
        eventos = cliente.consultar_eventos(desde_ciclo=ultimo_ciclo_lido)
        for evento in eventos:
            ultimo_ciclo_lido = max(ultimo_ciclo_lido, evento["ciclo"] + 1)
            tipo, dados = evento["tipo"], evento["dados"]

            if tipo == "extracao_concluida":
                carga_atual = dados["carga"]
                fase = "transportar"
            elif tipo == "transporte_concluido":
                fase = "analisar"
            elif tipo == "analise_concluida":
                fase = "aprovar"
            elif tipo == "carga_aprovada":
                fase = "vender"
            elif tipo == "carga_entregue":
                carga_atual = None
                fase = "extrair"
            elif tipo == "operacao_invalida":
                # Unico feedback de erro que existe. Num spike so imprimimos.
                print(f"[ciclo {evento['ciclo']}] INVALIDA: {dados}")

        # ------------------------------------------------ 2. agir
        if fase == "alocar_energia":
            for destino, quantidade in ORCAMENTO_INICIAL.items():
                cliente.chamar("POST", "/missao/alocar-energia", {
                    "destino": destino,
                    "quantidade": quantidade,
                    "politica": "pulso",
                })
            fase = "extrair"

        elif fase == "extrair":
            alvo = _primeira_jazida_livre(cliente, jazidas_ja_usadas)
            robo = _primeiro_robo_disponivel(cliente, "/extracao/mineradoras")
            if alvo and robo:
                jazidas_ja_usadas.add(alvo["identificador"])
                cliente.chamar("POST", "/extracao/iniciar-extracao", {
                    "identificador_da_unidade": robo["identificador"],
                    "identificador_da_jazida": alvo["identificador"],
                    "quantidade": QUANTIDADE_POR_EXTRACAO,
                    "modo": "normal",
                    "perfil_de_escavacao": "superficial",
                })
                fase = "aguardando"

        elif fase == "transportar":
            unidade = _primeiro_robo_disponivel(cliente, "/transporte/transportadores")
            plano = cliente.chamar(
                "GET", f"/transporte/planejar-transporte?identificador_da_carga={carga_atual}"
            )
            rotas = plano.get("rotas_disponiveis", [])
            if unidade and rotas:
                # A rota tem que sair do setor da jazida de origem da carga.
                autorizacao = cliente.chamar("POST", "/missao/autorizar-missao", {
                    "operacao": "iniciar_viagem",
                    "central_solicitante": "transporte",
                    "classe": "rapida",
                })
                cliente.chamar("POST", "/transporte/carregar", {
                    "identificador_da_unidade": unidade["identificador"],
                    "identificador_da_carga": carga_atual,
                })
                cliente.chamar("POST", "/transporte/iniciar-viagem", {
                    "identificador_da_unidade": unidade["identificador"],
                    "identificador_da_rota": rotas[0]["identificador"],
                    "identificador_da_carga": carga_atual,
                    "id_autorizacao": autorizacao["id_autorizacao"],
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
            autorizacao = cliente.chamar("POST", "/missao/autorizar-missao", {
                "operacao": "preparar_distribuicao",
                "central_solicitante": "pesquisa",
                "classe": "rapida",
            })
            cliente.chamar("POST", "/pesquisa/preparar-distribuicao", {
                "identificador_da_carga": carga_atual,
                "id_autorizacao": autorizacao["id_autorizacao"],
            })
            fase = "aguardando"

        # ------------------------------------------------ 3. passar o turno
        cliente.avancar_ciclo()


def _primeira_jazida_livre(cliente, ja_usadas):
    for jazida in cliente.chamar("GET", "/extracao/jazidas"):
        if jazida["identificador"] in ja_usadas:
            continue
        if jazida["estado"] == "disponivel":
            return jazida
    return None


def _primeiro_robo_disponivel(cliente, rota):
    for robo in cliente.chamar("GET", rota):
        if robo["estado"] == "disponivel":
            return robo
    return None
