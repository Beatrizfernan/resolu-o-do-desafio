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

    Medido: 2925.76 contra 2780.86, margem de 144.90 (5.21%).

    O que carrega essa margem é a **degradação**, não os quatro custos. Baixando
    os quatro ao mínimo que ainda não degenera o cenário (0.0001, 0, 0, 0) a
    margem continua em 133.91 (4.79%) — ou seja, 92% dela é só o minério
    sangrando valor enquanto está enterrado, e o modelo de custo responde por
    uns 11. Dentro desses 11, desempilhar pesa ~8 (zerá-lo leva a margem a
    136.90) e rearmazenar pesa ~5 (baixar `custo_de_armazenagem_por_unidade`
    para 0.001 leva a 140.00).

    Vale registrar por que não se mede isso com os custos em zero: `debitar`
    rejeita quantidade não-positiva, então `custo_de_armazenagem_por_unidade`
    igual a zero derruba o próprio `receber_carga` e o cenário colapsa nos dois
    braços — dá 0.000% de margem por não estar medindo nada, não por o modelo
    de custo ser neutro.

    `custo_de_manutencao_por_unidade` é a alavanca perigosa: em 0.2 a margem cai
    para 1.70% e em 0.5 ela **inverte** (-3.81%), porque manutenção cobra por
    volume parado e pune quem guarda, não quem guarda errado. O valor de linha
    de base (0.004) está com folga confortável desse limite.
    """
    entrega = _ordem_de_entrega()
    liquido_certo = _operar(list(reversed(entrega)), entrega)
    liquido_errado = _operar(list(entrega), entrega)

    assert liquido_certo > liquido_errado, (
        f"guardar na ordem de entrega rendeu {liquido_certo:.2f} contra "
        f"{liquido_errado:.2f} da ordem invertida: a pilha não está cobrando "
        f"por ter sido montada errado"
    )


def test_ordenar_pela_perda_de_valor_rende_mais_que_ordenar_pelo_preco():
    """A chave certa não é a óbvia.

    O teste anterior mostra que a ordem importa; este mostra qual ordem. As
    duas estratégias comparadas são internamente coerentes — cada uma guarda e
    entrega segundo a chave em que acredita — então a profundidade é zero nas
    duas e o desempilhamento não paga nada. O que sobra é só a degradação, que
    é exatamente o que a chave certa antecipa: o preço sozinho põe o cristal
    na frente quando quem sangra mais depressa é o gelo.

    A direção é o que se afirma; a magnitude não impressiona e não deve ser
    lida como se impressionasse. Medido, a chave certa rende 0.02% a mais —
    0.72 em 2925. É pouco porque gelo (25.2 de valor por ciclo) e cristal
    (24.0) sangram quase igual, e são justamente esses dois que trocam de
    lugar entre as duas chaves. A propriedade é real e determinística, mas
    errar a chave é quase de graça: quem quiser que ela pese precisa separar
    as taxas de perda em `minerais.json`.

    O teste se protege: se uma recalibração fizer as duas chaves coincidirem,
    a primeira asserção falha dizendo isso, em vez de passar sem testar nada.
    """
    por_perda = _ordem_de_entrega()
    por_preco = sorted(
        SORTIMENTO, key=lambda n: MINERAIS.obter(n).valor_por_unidade, reverse=True,
    )

    assert por_perda != por_preco, (
        "o catálogo precisa fazer as duas chaves divergirem, senão este teste "
        "não prova nada"
    )

    liquido_por_perda = _operar(list(reversed(por_perda)), por_perda)
    liquido_por_preco = _operar(list(reversed(por_preco)), por_preco)

    assert liquido_por_perda > liquido_por_preco, (
        f"a chave perda-por-ciclo rendeu {liquido_por_perda:.2f} contra "
        f"{liquido_por_preco:.2f} da chave preço: seguir o preço deixou de ser "
        f"o palpite errado, e a decisão de ordenação virou indiferente"
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


def test_a_recompensa_cresce_com_a_qualidade_da_estrategia():
    """A cadeia inteira que a spec pede, num teste só.

    Perda de valor > preço > empilhar sem pensar. Não basta que cada par se
    ordene: a progressão é a afirmação, porque é ela que descreve o que o
    projeto quer — estratégia simples funciona, estratégia melhor funciona
    melhor, e nenhuma é obrigatória.

    As margens são desiguais de propósito e vale saber quais são: reordenar em
    vez de empilhar às cegas rende ~2.2%, enquanto trocar a chave de preço para
    perda rende ~0.025%. O degrau grande é decidir organizar; o pequeno é
    escolher por qual critério.
    """
    entrega = _ordem_de_entrega()
    por_preco = sorted(
        SORTIMENTO, key=lambda n: MINERAIS.obter(n).valor_por_unidade, reverse=True,
    )

    perda = _operar(list(reversed(entrega)), entrega)
    preco = _operar(list(reversed(por_preco)), por_preco)
    sem_reordenar = _operar(list(SORTIMENTO), entrega)

    assert perda > preco > sem_reordenar, (
        f"a progressão quebrou: perda={perda:.2f}, preço={preco:.2f}, "
        f"sem reordenar={sem_reordenar:.2f}"
    )
