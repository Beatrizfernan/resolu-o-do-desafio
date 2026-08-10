"""A ordem da pilha precisa ser uma decisão, não uma obrigação.

Três propriedades: guardar na ordem em que se vai entregar rende mais que
guardar contra ela; atingir uma ordem-alvo com movimento mínimo custa menos que
remontar a pilha; e quem nunca reordena continua jogando.

Um cenário que entregasse sempre o topo não provaria nada: a profundidade seria
sempre zero e o custo de desempilhamento nunca seria pago. Por isso a ordem de
entrega é fixa e o que varia é a ordem de armazenagem — é assim que a pilha
cobra por ter sido montada errado.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.cargas import CargaMineral, LocalDaCarga
from mundo.dominio.minerais import CatalogoDeMinerais

CAMINHO_MINERAIS = Path(__file__).parent.parent / "config" / "minerais.json"
MINERAIS = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_MINERAIS)

# Um de cada mineral do catálogo, mesma quantidade, para isolar a ordem como
# única variável.
SORTIMENTO = [m.nome for m in MINERAIS.todos()]
QUANTIDADE = 10.0
CICLOS_ENTRE_ENTREGAS = 5


def _perda_de_valor_por_ciclo(nome: str) -> float:
    """Quanto valor uma carga deste mineral sangra a cada ciclo parada.

    É a chave que decide a ordem de entrega: o que perde mais depressa deve
    sair primeiro. Combina três campos do catálogo, e nenhum deles sozinho
    responde — o preço, sozinho, dá outra ordem.
    """
    mineral = MINERAIS.obter(nome)
    return (
        mineral.taxa_degradacao
        * mineral.sensibilidade_armazenagem
        * mineral.valor_por_unidade
    )


def _autorizar(cliente, operacao: str, central: str) -> str:
    return cliente.post(
        "/missao/autorizar-missao",
        json={"operacao": operacao, "central_solicitante": central},
    ).json()["id_autorizacao"]


def _operar(ordem_de_armazenagem: list[str], ordem_de_entrega: list[str]) -> float:
    """Guarda numa ordem, entrega noutra, e devolve o resultado líquido.

    Líquido é faturamento menos energia gasta, porque as duas coisas que a
    ordem errada custa são justamente essas: o desempilhamento cobra energia, e
    o que foi desenterrado sem ser entregue volta para a pilha degradando mais
    um pouco a cada vez.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        for central in ("armazenagem", "pesquisa"):
            motor.energia.alocar_energia("reserva_estrategica", central, 400)
        for nome in ordem_de_armazenagem:
            motor.cargas[nome] = CargaMineral(
                nome, nome, QUANTIDADE, 100.0, local=LocalDaCarga.NA_MAO,
            )

        def energia_total() -> float:
            return (
                motor.energia.consultar_energia("armazenagem")
                + motor.energia.consultar_energia("pesquisa")
            )

        energia_antes = energia_total()
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": list(ordem_de_armazenagem),
            "id_autorizacao": _autorizar(cliente, "receber_carga", "armazenagem"),
        })
        motor.avancar_ciclo(1)
        faturamento_antes = motor.faturamento_total

        for alvo in ordem_de_entrega:
            cliente.post("/armazenagem/retirar-carga", json={
                "identificador_do_armazem": "armazem-1",
                "identificador_da_carga": alvo,
                "id_autorizacao": _autorizar(cliente, "retirar_carga", "armazenagem"),
            })
            motor.avancar_ciclo(1)
            cliente.post("/pesquisa/preparar-distribuicao", json={
                "identificador_da_carga": alvo,
                "id_autorizacao": _autorizar(cliente, "preparar_distribuicao", "pesquisa"),
            })
            motor.avancar_ciclo(CICLOS_ENTRE_ENTREGAS)

            # O que veio junto e ainda não será entregue volta para a pilha, e
            # pagar por isso é justamente o preço de ter guardado fora de ordem.
            desenterradas = [
                nome for nome, carga in motor.cargas.items()
                if carga.local == LocalDaCarga.NA_MAO
            ]
            if desenterradas:
                cliente.post("/armazenagem/receber-carga", json={
                    "identificador_do_armazem": "armazem-1",
                    "identificadores_das_cargas": desenterradas,
                    "id_autorizacao": _autorizar(cliente, "receber_carga", "armazenagem"),
                })
                motor.avancar_ciclo(1)

        return (motor.faturamento_total - faturamento_antes) - (energia_antes - energia_total())


def _ordem_de_entrega() -> list[str]:
    """O que sangra mais valor por ciclo sai primeiro."""
    return sorted(SORTIMENTO, key=_perda_de_valor_por_ciclo, reverse=True)


def test_guardar_na_ordem_de_entrega_rende_mais_que_guardar_contra_ela():
    """A decisão central do sub-projeto.

    Como o topo é o fim da lista, guardar na ordem certa significa empilhar do
    último ao primeiro a sair. Quem faz isso paga profundidade zero em toda
    retirada. Quem empilha ao contrário desenterra a pilha inteira na primeira
    entrega, paga o desempilhamento, e ainda rearmazena o que veio junto.

    Medido: a ordem certa rende cerca de 5% a mais. O que carrega essa
    diferença é o **custo de rearmazenar**, não o de desempilhar — zerando
    `custo_de_armazenagem_por_unidade` a margem cai para 0.2%, enquanto zerando
    `custo_por_desempilhamento` ela ainda fica em 4.9%. Faz sentido: quem
    guardou errado desenterra quatro cargas para entregar uma e paga
    armazenagem pelas três que voltam, toda vez. Com os quatro custos em zero a
    margem é exatamente 0.000%, o que confirma que é o modelo de custo — e não
    algum artefato do cenário — que cria a decisão.
    """
    entrega = _ordem_de_entrega()
    liquido_certo = _operar(list(reversed(entrega)), entrega)
    liquido_errado = _operar(list(entrega), entrega)

    assert liquido_certo > liquido_errado, (
        f"guardar na ordem de entrega rendeu {liquido_certo:.2f} contra "
        f"{liquido_errado:.2f} da ordem invertida: a pilha não está cobrando "
        f"por ter sido montada errado"
    )


def test_movimento_minimo_custa_menos_que_remontar_a_pilha():
    """A implementação esperta é recompensada.

    Como reordenar cobra por deslocamento, atingir a ordem-alvo preservando a
    maior parte já correta é estritamente mais barato que reescrever tudo.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        armazem = motor.armazens["armazem-1"]
        for nome in ("a", "b", "c", "d", "e"):
            armazem.empilhar(nome, 1.0)

        # Trocar só as duas do topo.
        movimentos_minimos = armazem.reordenar(["a", "b", "c", "e", "d"])
        armazem.reordenar(["a", "b", "c", "d", "e"])
        # Inverter tudo.
        movimentos_totais = armazem.reordenar(["e", "d", "c", "b", "a"])

        assert movimentos_minimos < movimentos_totais
        assert movimentos_minimos == 2
        assert movimentos_totais == 12


def test_quem_nunca_reordena_continua_jogando():
    """Reordenar precisa ser vantagem, nunca obrigação.

    Uma estratégia que só empilha na ordem em que o minério aparece e desenterra
    quando precisa tem que conseguir completar as entregas. Se não conseguir, o
    mecanismo virou pedágio e a calibração é que está errada — não o teste.
    """
    liquido = _operar(list(SORTIMENTO), _ordem_de_entrega())

    assert liquido > 0.0, (
        f"empilhar sem pensar rendeu {liquido:.2f}: guardar minério deixou de "
        f"valer a pena, então a armazenagem virou pedágio"
    )
