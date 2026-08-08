"""Nenhum modo de transporte pode ser o mais barato em todo cenário.

`test_dominancia_de_modos.py` mede o mundo pré-desgaste: `qualidade /
mult_energia`, sem desgaste acumulado e sem custo de duração. Essa métrica é
estruturalmente cega ao defeito que este arquivo existe para impedir — sob
operação contínua o desgaste entra na conta de energia e *reconfigura* a
comparação, e foi exatamente aí que `economico` passou a vencer 10 de 10
combinações de mineral e rota.

A causa é quadrática e não se enxerga na conta estática: cada viagem acumula
`taxa_de_desgaste / mult_duracao`, e o número de viagens por ciclo também
escala com `1 / mult_duracao`. O desgaste *por ciclo* escala portanto com
`1 / mult_duracao²`, e o modo mais lento fica barato num eixo em que ninguém
o estava medindo.

O espelho deste arquivo no eixo de extração é
`test_lideranca_de_custo_gira_conforme_a_janela_de_operacao`, em
`test_desgaste.py`.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.cargas import CargaMineral
from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.dominio.modos import ModoDeTransporte
from mundo.dominio.robos import EstadoDoRobo

CAMINHO_MINERAIS = Path(__file__).parent.parent / "config" / "minerais.json"
MINERAIS = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_MINERAIS)

MODOS = tuple(modo.value for modo in ModoDeTransporte)
ROTAS = ("rota-1", "rota-2")
QUANTIDADE = 10.0

# Janelas de operação contínua, em ciclos. O teto é o orçamento: a reserva
# estratégica inteira tem 950 unidades de energia, e `rapido` na rota-1 — o
# par mais caro — gasta 653 até o ciclo 100 e 933 até o 120. Passar de 100
# faria o orçamento, e não a calibração, decidir quem "vence", que é
# exatamente o artefato que este teste precisa não ter.
JANELAS_DE_OPERACAO_CONTINUA = (40, 60, 80, 100)
ENERGIA_DA_CENTRAL = 900


# Perecibilidade = `taxa_degradacao × sensibilidade_transporte`: o quanto a
# carga perde por ciclo em trânsito, antes do multiplicador do modo. É o eixo
# em que a liderança de custo precisa girar, porque é o único preço que a
# lentidão paga — duração, por si só, não custa energia nenhuma.
def _perecibilidade(nome_do_mineral: str) -> float:
    mineral = MINERAIS.obter(nome_do_mineral)
    return mineral.taxa_degradacao * mineral.sensibilidade_transporte


MINERAIS_POR_PERECIBILIDADE = tuple(
    sorted((m.nome for m in MINERAIS.todos()), key=_perecibilidade)
)
MENOS_PERECIVEL = MINERAIS_POR_PERECIBILIDADE[0]
MAIS_PERECIVEL = MINERAIS_POR_PERECIBILIDADE[-1]


def _autorizar(cliente) -> str:
    resposta = cliente.post(
        "/missao/autorizar-missao",
        json={"operacao": "iniciar_viagem", "central_solicitante": "transporte"},
    )
    return resposta.json()["id_autorizacao"]


def _simular_operacao_continua(
    modo: str, nome_do_mineral: str, rota: str,
) -> dict[int, tuple[float, float]]:
    """Transporta sem pausas e fotografa a conta ao cruzar cada janela.

    Cada janela é um prefixo da seguinte, então uma única simulação atende
    todas elas. Devolve, por janela, (valor entregue, energia gasta) — o valor
    é lido na chegada, via evento `transporte_concluido`, porque é ali que a
    qualidade que sobrou da viagem ainda existe.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "transporte", ENERGIA_DA_CENTRAL)
        unidade = motor.robos["transportadora-1"]
        # A cota de viagens é um recurso à parte; aqui se mede o eixo
        # energia/desgaste, então ela sai da frente.
        unidade.viagens_disponiveis = 10 ** 6
        mineral = MINERAIS.obter(nome_do_mineral)

        entregue = [0.0]

        def ao_concluir(evento) -> None:
            if evento.tipo != "transporte_concluido":
                return
            carga = motor.cargas.get(evento.dados["carga"])
            qualidade = carga.qualidade if carga is not None else 0.0
            entregue[0] += QUANTIDADE * mineral.valor_por_unidade * (qualidade / 100)

        motor.eventos.assinar(ao_concluir)
        energia_antes = motor.energia.consultar_energia("transporte")
        fotos: dict[int, tuple[float, float]] = {}
        despachadas = 0

        for ciclo in range(1, max(JANELAS_DE_OPERACAO_CONTINUA) + 1):
            if unidade.estado == EstadoDoRobo.DISPONIVEL:
                despachadas += 1
                identificador = f"carga-{despachadas}"
                motor.cargas[identificador] = CargaMineral(
                    identificador, nome_do_mineral, QUANTIDADE, 100.0,
                )
                cliente.post("/transporte/iniciar-viagem", json={
                    "identificador_da_unidade": unidade.identificador,
                    "identificador_da_rota": rota,
                    "identificador_da_carga": identificador,
                    "modo": modo,
                    "id_autorizacao": _autorizar(cliente),
                })
            elif unidade.estado in (EstadoDoRobo.AGUARDANDO, EstadoDoRobo.RETORNANDO):
                cliente.post(
                    "/transporte/retornar-unidade",
                    json={"identificador_da_unidade": unidade.identificador},
                )
            motor.avancar_ciclo(1)
            if ciclo in JANELAS_DE_OPERACAO_CONTINUA:
                gasto = energia_antes - motor.energia.consultar_energia("transporte")
                fotos[ciclo] = (entregue[0], gasto)

        return fotos


_medicoes: dict[tuple[str, str, str], dict[int, tuple[float, float]]] = {}


def _medir(modo: str, mineral: str, rota: str) -> dict[int, tuple[float, float]]:
    """Uma simulação por (modo, mineral, rota), compartilhada pelos testes."""
    chave = (modo, mineral, rota)
    if chave not in _medicoes:
        _medicoes[chave] = _simular_operacao_continua(modo, mineral, rota)
    return _medicoes[chave]


def _valor_por_energia(modo: str, mineral: str, rota: str, janela: int) -> float:
    entregue, gasto = _medir(modo, mineral, rota)[janela]
    return entregue / gasto


def _lideres_de_custo() -> dict[tuple[str, str, int], str]:
    """O modo que entrega mais valor por energia em cada cenário."""
    return {
        (mineral, rota, janela): max(
            MODOS, key=lambda modo: _valor_por_energia(modo, mineral, rota, janela)
        )
        for mineral in MINERAIS_POR_PERECIBILIDADE
        for rota in ROTAS
        for janela in JANELAS_DE_OPERACAO_CONTINUA
    }


def _tabela(mineral: str, rota: str) -> str:
    return "; ".join(
        f"{janela} ciclos: "
        + ", ".join(
            f"{modo}={_valor_por_energia(modo, mineral, rota, janela):.3f}"
            for modo in MODOS
        )
        for janela in JANELAS_DE_OPERACAO_CONTINUA
    )


def test_nenhum_modo_de_transporte_e_o_mais_barato_em_todo_cenario():
    """A propriedade que o sub-projeto inteiro existe para manter.

    Sem limiar e sem constante mágica: basta que o modo mais barato *mude*
    de cenário para cenário. Se um único modo for o mais barato em todos
    eles, nenhuma estratégia jamais escolheria outro, e os três modos viram
    um só com três nomes.
    """
    lideres = _lideres_de_custo()
    distintos = set(lideres.values())

    assert len(distintos) > 1, (
        f"'{distintos.pop()}' é o mais barato em todos os "
        f"{len(lideres)} cenários (mineral × rota × janela), logo é "
        f"universalmente melhor. "
        f"{MENOS_PERECIVEL}/rota-1: {_tabela(MENOS_PERECIVEL, 'rota-1')}. "
        f"{MAIS_PERECIVEL}/rota-2: {_tabela(MAIS_PERECIVEL, 'rota-2')}."
    )


def test_a_lideranca_de_custo_gira_com_a_perecibilidade_da_carga():
    """E gira na direção certa: a lentidão é paga em carga estragada.

    `economico` gasta menos energia por viagem e, por fazer menos viagens
    por ciclo, também acumula menos desgaste — vantagem em dois eixos ao
    mesmo tempo. O único preço que ele paga é a carga degradar durante uma
    viagem mais longa. Então a liderança precisa girar exatamente aí: com o
    minério que aguenta a viagem, `economico`; com o que não aguenta, não.

    Asserção direcional em vez de numérica: continua significando o mesmo se
    a calibração dos perfis mudar de novo.
    """
    lideres = _lideres_de_custo()
    resistentes = [lideres[(MENOS_PERECIVEL, rota, janela)]
                   for rota in ROTAS for janela in JANELAS_DE_OPERACAO_CONTINUA]
    pereciveis = [lideres[(MAIS_PERECIVEL, rota, janela)]
                  for rota in ROTAS for janela in JANELAS_DE_OPERACAO_CONTINUA]

    assert set(resistentes) == {ModoDeTransporte.ECONOMICO.value}, (
        f"com o mineral menos perecível ({MENOS_PERECIVEL}, perde "
        f"{_perecibilidade(MENOS_PERECIVEL):.2f} por ciclo em trânsito) a viagem "
        f"lenta deveria compensar, mas lideraram {sorted(set(resistentes))}. "
        f"rota-1: {_tabela(MENOS_PERECIVEL, 'rota-1')}"
    )
    assert ModoDeTransporte.ECONOMICO.value not in pereciveis, (
        f"com o mineral mais perecível ({MAIS_PERECIVEL}, perde "
        f"{_perecibilidade(MAIS_PERECIVEL):.2f} por ciclo em trânsito) 'economico' "
        f"ainda lidera o custo: a degradação parou de ser um preço real e a "
        f"lentidão voltou a ser grátis. "
        f"rota-2: {_tabela(MAIS_PERECIVEL, 'rota-2')}"
    )


def test_rapido_nao_lidera_custo_mas_lidera_o_volume_entregue():
    """O que sustenta `rapido` é vazão, não eficiência — e isso é verificado.

    `rapido` opera em ritmo dobrado, então acumula desgaste mais depressa e
    nunca é o mais barato por unidade de valor: é o espelho de `agressivo` no
    eixo de extração. Sem a segunda metade desta asserção o teste acima
    poderia passar com `rapido` simplesmente inútil — aqui se prova que ele
    continua sendo a escolha de quem tem ciclos, e não energia, como gargalo.
    """
    lideres = _lideres_de_custo()
    assert ModoDeTransporte.RAPIDO.value not in lideres.values(), (
        f"'rapido' lidera o custo em algum cenário, invertendo a direção "
        f"esperada: quem opera em ritmo mais curto deveria pagar mais desgaste "
        f"por ciclo. {MENOS_PERECIVEL}/rota-1: {_tabela(MENOS_PERECIVEL, 'rota-1')}"
    )

    for mineral in MINERAIS_POR_PERECIBILIDADE:
        for rota in ROTAS:
            janela = max(JANELAS_DE_OPERACAO_CONTINUA)
            por_ciclo = {
                modo: _medir(modo, mineral, rota)[janela][0] / janela for modo in MODOS
            }
            lider = max(por_ciclo, key=por_ciclo.get)
            assert lider == ModoDeTransporte.RAPIDO.value, (
                f"'rapido' deixou de liderar o valor entregue por ciclo em "
                f"{mineral}/{rota} — perdeu a única vantagem que lhe resta e "
                f"nenhuma estratégia teria motivo para escolhê-lo: "
                + ", ".join(f"{m}={v:.2f}/ciclo" for m, v in por_ciclo.items())
            )
