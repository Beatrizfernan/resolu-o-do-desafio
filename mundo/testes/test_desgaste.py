from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.cargas import CargaMineral, LocalDaCarga
from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.dominio.modos import ModoDeExtracao, ModoDeTransporte
from mundo.dominio.robos import EstadoDoRobo
from mundo.motor.motor_de_simulacao import ConfiguracaoDaSimulacao, MotorDeSimulacao

CAMINHO_CATALOGO = Path(__file__).parent.parent / "config" / "minerais.json"


def _criar_motor(semente: int = 1) -> MotorDeSimulacao:
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    return MotorDeSimulacao(ConfiguracaoDaSimulacao(semente=semente, duracao_maxima=50), catalogo)


def test_robo_disponivel_recupera_desgaste_a_cada_ciclo():
    motor = _criar_motor()
    unidade = motor.robos["mineradora-1"]
    unidade.estado = EstadoDoRobo.DISPONIVEL
    unidade.desgaste = 2.0
    recuperacao = motor.catalogo_de_modos.recuperacao_de_desgaste_por_ciclo

    motor.avancar_ciclo(1)

    assert unidade.desgaste == 2.0 - recuperacao


def test_robo_executando_nao_recupera_desgaste():
    motor = _criar_motor()
    unidade = motor.robos["mineradora-1"]
    unidade.estado = EstadoDoRobo.EXECUTANDO
    unidade.desgaste = 2.0

    motor.avancar_ciclo(3)

    assert unidade.desgaste == 2.0


def test_desgaste_nunca_fica_negativo():
    motor = _criar_motor()
    unidade = motor.robos["mineradora-1"]
    unidade.estado = EstadoDoRobo.DISPONIVEL
    unidade.desgaste = 0.1

    motor.avancar_ciclo(20)

    assert unidade.desgaste == 0.0


def test_recuperacao_alcanca_todos_os_robos_disponiveis():
    motor = _criar_motor()
    for robo in motor.robos.values():
        robo.estado = EstadoDoRobo.DISPONIVEL
        robo.desgaste = 1.0

    motor.avancar_ciclo(1)

    recuperacao = motor.catalogo_de_modos.recuperacao_de_desgaste_por_ciclo
    assert all(robo.desgaste == 1.0 - recuperacao for robo in motor.robos.values())


def _extrair(cliente, **campos):
    corpo = {
        "identificador_da_unidade": "mineradora-1",
        "identificador_da_jazida": "jazida-1",
        "quantidade": 10.0,
    }
    corpo.update(campos)
    return cliente.post("/extracao/iniciar-extracao", json=corpo)


def test_extracao_acumula_desgaste_conforme_o_ritmo_do_modo():
    """O desgaste mede ritmo de operação, não energia consumida.

    Cada extração acumula `taxa_de_desgaste / mult_duracao`: ciclos mais curtos
    castigam mais a máquina, independentemente do que a operação custou.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 500)
        unidade = motor.robos["mineradora-1"]
        perfil = motor.catalogo_de_modos.obter_extracao(ModoDeExtracao.NORMAL)

        _extrair(cliente, modo="normal")
        motor.avancar_ciclo(1)

        esperado = motor.catalogo_de_modos.taxa_de_desgaste / perfil.mult_duracao
        assert unidade.desgaste == pytest.approx(esperado)


def test_unidade_desgastada_paga_mais_pela_mesma_extracao():
    custos = {}
    for desgaste_inicial in (0.0, 4.0):
        app = criar_app(com_loop_real_time=False)
        with TestClient(app) as cliente:
            motor = instancia_do_mundo.obter_motor()
            motor.energia.alocar_energia("reserva_estrategica", "extracao", 500)
            motor.robos["mineradora-1"].desgaste = desgaste_inicial
            antes = motor.energia.consultar_energia("extracao")

            _extrair(cliente)
            motor.avancar_ciclo(1)

            custos[desgaste_inicial] = antes - motor.energia.consultar_energia("extracao")

    assert custos[4.0] > custos[0.0]


def _autorizar(cliente) -> str:
    resposta = cliente.post(
        "/missao/autorizar-missao",
        json={"operacao": "iniciar_viagem", "central_solicitante": "transporte"},
    )
    return resposta.json()["id_autorizacao"]


def test_transportadora_desgastada_paga_mais_pela_mesma_viagem():
    custos = {}
    for desgaste_inicial in (0.0, 4.0):
        app = criar_app(com_loop_real_time=False)
        with TestClient(app) as cliente:
            motor = instancia_do_mundo.obter_motor()
            motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0, local=LocalDaCarga.NA_MAO)
            motor.energia.alocar_energia("reserva_estrategica", "transporte", 500)
            motor.robos["transportadora-1"].desgaste = desgaste_inicial
            antes = motor.energia.consultar_energia("transporte")

            cliente.post(
                "/transporte/iniciar-viagem",
                json={
                    "identificador_da_unidade": "transportadora-1",
                    "identificador_da_rota": "rota-1",
                    "identificador_da_carga": "carga-1",
                    "id_autorizacao": _autorizar(cliente),
                },
            )
            motor.avancar_ciclo(1)

            custos[desgaste_inicial] = antes - motor.energia.consultar_energia("transporte")

    assert custos[4.0] > custos[0.0]


def test_viagem_acumula_desgaste_na_transportadora():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0, local=LocalDaCarga.NA_MAO)
        motor.energia.alocar_energia("reserva_estrategica", "transporte", 500)
        unidade = motor.robos["transportadora-1"]
        perfil = motor.catalogo_de_modos.obter_transporte(ModoDeTransporte.NORMAL)

        cliente.post(
            "/transporte/iniciar-viagem",
            json={
                "identificador_da_unidade": "transportadora-1",
                "identificador_da_rota": "rota-1",
                "identificador_da_carga": "carga-1",
                "id_autorizacao": _autorizar(cliente),
            },
        )
        motor.avancar_ciclo(1)

        esperado = motor.catalogo_de_modos.taxa_de_desgaste / perfil.mult_duracao
        assert unidade.desgaste == pytest.approx(esperado)


def _desgaste_de_uma_viagem(modo: str) -> tuple[float, float, float]:
    """(desgaste acumulado, mult_duracao do modo, taxa_de_desgaste) numa viagem."""
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0, local=LocalDaCarga.NA_MAO)
        motor.energia.alocar_energia("reserva_estrategica", "transporte", 500)
        unidade = motor.robos["transportadora-1"]

        cliente.post(
            "/transporte/iniciar-viagem",
            json={
                "identificador_da_unidade": "transportadora-1",
                "identificador_da_rota": "rota-1",
                "identificador_da_carga": "carga-1",
                "modo": modo,
                "id_autorizacao": _autorizar(cliente),
            },
        )
        motor.avancar_ciclo(1)
        perfil = motor.catalogo_de_modos.obter_transporte(ModoDeTransporte(modo))
        return (
            unidade.desgaste,
            perfil.mult_duracao,
            motor.catalogo_de_modos.taxa_de_desgaste,
        )


def test_desgaste_da_viagem_escala_com_o_ritmo_do_modo():
    """O divisor `mult_duracao` precisa estar preso por um modo em que ele ≠ 1.

    `test_viagem_acumula_desgaste_na_transportadora` usa `normal`, cujo
    `mult_duracao` é exatamente 1.0 — dividir por 1.0 é inócuo, então aquele
    teste passa igual se o divisor for apagado. Sem este teste, o desgaste do
    transporte poderia virar custo fixo por operação sem nada acusar, e
    `rapido` deixaria de pagar por operar em ritmo dobrado: a mesma classe de
    falha que o desgaste existe para corrigir, sobrevivendo neste eixo.

    A asserção é relacional para continuar significando o mesmo se a
    calibração dos perfis mudar.
    """
    medidas = {modo: _desgaste_de_uma_viagem(modo) for modo in ("economico", "rapido")}

    for modo, (desgaste, mult_duracao, taxa) in medidas.items():
        assert mult_duracao != 1.0, f"'{modo}' perdeu a serventia aqui: mult_duracao virou 1.0"
        assert desgaste == pytest.approx(taxa / mult_duracao)

    desgaste_economico, mult_economico, _ = medidas["economico"]
    desgaste_rapido, mult_rapido, _ = medidas["rapido"]
    assert desgaste_rapido / desgaste_economico == pytest.approx(
        mult_economico / mult_rapido
    ), (
        "o desgaste do transporte deixou de escalar com o ritmo: "
        f"rapido={desgaste_rapido:.3f}, economico={desgaste_economico:.3f}"
    )


# Janela do teste de inversão. Era 60, calibrada quando a entrega era creditada
# pelo HTTP 200 do pedido — o que inflava os modos lentos na fronteira e fazia a
# inversão parecer acontecer antes do que acontece. Com a entrega creditada pelo
# evento `extracao_concluida`, a inversão começa em 70 ciclos e a margem cresce
# de forma monotônica: +11.5% em 70, +38.8% em 80, +61.1% em 120, +120% em 160.
# 120 fica bem depois da virada e longe da faixa onde o líder ainda oscila.
CICLOS_DE_OPERACAO_CONTINUA = 120


def _simular_operacao_continua(
    modo: str, janelas: tuple[int, ...]
) -> dict[int, tuple[float, float]]:
    """Extrai sem pausas e fotografa a conta ao cruzar cada janela.

    Cada janela é um prefixo da seguinte, então uma única simulação atende
    todas elas — medir quatro janelas custa uma execução, não quatro.

    Devolve, por janela, (unidades entregues, energia gasta), ponderando a
    entrega pela qualidade inicial do modo: o que interessa é valor útil, não
    massa bruta.

    A entrega é creditada pelo evento `extracao_concluida`, não pelo HTTP 200
    do pedido. A diferença importa na fronteira da janela: uma extração
    despachada e ainda em voo já teve o 200, mas não produziu minério nenhum.
    Como os modos têm durações diferentes, contar pedidos infla sempre os modos
    lentos — na janela 40, `cuidadoso` fazia 5 pedidos para 4 conclusões (25%)
    contra 8 para 8 do `agressivo` (0%) — e chegava a inverter o líder.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 900)
        unidade = motor.robos["mineradora-1"]
        perfil = motor.catalogo_de_modos.obter_extracao(ModoDeExtracao(modo))
        energia_antes = motor.energia.consultar_energia("extracao")
        concluidas = [0]
        fotos: dict[int, tuple[float, float]] = {}

        def ao_evento(evento) -> None:
            if evento.tipo == "extracao_concluida":
                concluidas[0] += 1

        motor.eventos.assinar(ao_evento)

        for ciclo in range(1, max(janelas) + 1):
            if unidade.estado.value == "disponivel":
                _extrair(cliente, modo=modo, quantidade=2.0)
            elif unidade.estado.value == "aguardando":
                unidade.estado = EstadoDoRobo.DISPONIVEL
            motor.avancar_ciclo(1)
            entregue = concluidas[0] * 2.0 * (perfil.qualidade_inicial / 100)
            if ciclo in janelas:
                gasto = energia_antes - motor.energia.consultar_energia("extracao")
                fotos[ciclo] = (entregue, gasto)

        return fotos


def _operar_continuamente(
    modo: str, ciclos: int = CICLOS_DE_OPERACAO_CONTINUA
) -> tuple[float, float]:
    """(unidades entregues, energia gasta) numa única janela de `ciclos` ciclos."""
    return _simular_operacao_continua(modo, (ciclos,))[ciclos]


def test_agressivo_deixa_de_dominar_sob_operacao_continua():
    """O ponto do sub-projeto inteiro.

    Sem desgaste, agressivo vence por 1,88x em qualquer cenário estático.
    Sob uso contínuo ele executa mais operações por ciclo, acumula desgaste
    mais rápido e o custo por unidade entregue passa a subir.
    """
    entregue_agressivo, energia_agressivo = _operar_continuamente("agressivo")
    entregue_cuidadoso, energia_cuidadoso = _operar_continuamente("cuidadoso")

    custo_agressivo = energia_agressivo / entregue_agressivo
    custo_cuidadoso = energia_cuidadoso / entregue_cuidadoso

    assert custo_agressivo > custo_cuidadoso, (
        f"agressivo ainda domina sob uso contínuo: "
        f"{custo_agressivo:.2f} vs {custo_cuidadoso:.2f} de energia por unidade entregue"
    )


# Modos do mais contido ao mais intenso. A posição na tupla é a própria
# definição de "mais conservador": índice menor, ritmo menor.
MODOS_DO_MAIS_CONSERVADOR_AO_MAIS_INTENSO = ("cuidadoso", "normal", "agressivo")

# Janelas de operação contínua, em ciclos.
#
# A escolha é deliberada e já errou uma vez: uma versão anterior usava
# (40, 60, 80, 120) e afirmava que `agressivo` nunca lidera. Uma varredura de 5
# em 5 mostrou que `agressivo` é o mais barato em toda janela ≤ 30 — a
# afirmação só se sustentava porque as quatro janelas caíam depois da virada,
# por volta de 32 ciclos. Era artefato da amostragem, não propriedade.
#
# Perto das viradas o líder também oscila de janela para janela, porque numa
# fronteira qualquer o modo pode ter acabado de concluir uma extração ou estar
# no meio de outra. Por isso as janelas escolhidas ficam longe das viradas: 20
# está bem dentro do território de `agressivo`, e de 120 a 200 `cuidadoso`
# lidera de forma monotônica, com margem que só cresce.
#
# A janela mínima precisa comportar ao menos uma extração completa do modo mais
# lento (`cuidadoso`: 5 × 1.4 = 7 ciclos), senão o custo por unidade é infinito.
JANELAS_DE_OPERACAO_CONTINUA = (20, 120, 160, 200)


def _custo_por_unidade_util(modo: str) -> dict[int, float]:
    """Custo por unidade útil do modo em cada janela, numa só simulação."""
    fotos = _simular_operacao_continua(modo, JANELAS_DE_OPERACAO_CONTINUA)
    return {janela: energia / entregue for janela, (entregue, energia) in fotos.items()}


def test_lideranca_de_custo_gira_conforme_a_janela_de_operacao():
    """A liderança de custo *gira* com o tamanho da janela de operação.

    O sub-projeto existe para eliminar um modo universalmente melhor. Testar
    isso como "os custos ficam a menos de X% de distância" exige um limiar
    arbitrário, e mede a coisa errada: modos empatados também tornariam a
    escolha irrelevante. A propriedade que realmente importa é que o modo mais
    barato *muda* conforme a janela — `normal` rende mais em rajadas curtas,
    `cuidadoso` assume quando a operação se estende e o desgaste acumulado
    domina o custo. Isso é uma afirmação sem constante mágica: nenhum modo é o
    mais barato em todas as janelas, então nenhuma estratégia fixa é ótima.

    A rotação vai de `agressivo` (rajada curta) a `cuidadoso` (operação
    prolongada), passando por `normal` na faixa intermediária. `agressivo` é
    genuinamente o modo certo para rajadas: ele lidera em custo em toda janela
    curta. O que o desgaste tira dele é a permanência — sustentar o ritmo faz o
    custo por unidade disparar, e é isso que
    `test_agressivo_deixa_de_dominar_sob_operacao_continua` fixa.
    """
    por_modo = {
        modo: _custo_por_unidade_util(modo)
        for modo in MODOS_DO_MAIS_CONSERVADOR_AO_MAIS_INTENSO
    }
    custos = {
        janela: {modo: por_modo[modo][janela] for modo in por_modo}
        for janela in JANELAS_DE_OPERACAO_CONTINUA
    }
    lideres = {
        janela: min(por_modo, key=lambda modo: por_modo[modo])
        for janela, por_modo in custos.items()
    }
    tabela = "; ".join(
        f"{janela} ciclos: "
        + ", ".join(f"{modo}={custo:.3f}" for modo, custo in custos[janela].items())
        for janela in JANELAS_DE_OPERACAO_CONTINUA
    )

    assert len(set(lideres.values())) > 1, (
        f"'{next(iter(lideres.values()))}' é o mais barato em todas as janelas, "
        f"logo é universalmente melhor: {tabela}"
    )

    lider_curto = lideres[JANELAS_DE_OPERACAO_CONTINUA[0]]
    lider_longo = lideres[JANELAS_DE_OPERACAO_CONTINUA[-1]]

    # As duas pontas da rotação, afirmadas separadamente. Juntas dizem mais do
    # que a versão anterior ("agressivo nunca lidera"), que além de mais fraca
    # era falsa: agressivo lidera em toda janela curta.
    assert lider_curto == "agressivo", (
        f"em rajada curta esperava-se 'agressivo' liderando — é para isso que o "
        f"modo existe —, mas lidera '{lider_curto}': {tabela}"
    )

    janelas_longas = JANELAS_DE_OPERACAO_CONTINUA[1:]
    assert all(lideres[janela] != "agressivo" for janela in janelas_longas), (
        f"'agressivo' ainda lidera em custo numa janela longa {janelas_longas}: "
        f"sustentar o ritmo deveria custar caro. {tabela}"
    )

    posicao = MODOS_DO_MAIS_CONSERVADOR_AO_MAIS_INTENSO.index
    assert posicao(lider_longo) < posicao(lider_curto), (
        f"a virada aponta para o lado errado: em janela curta lidera "
        f"'{lider_curto}' e em janela longa '{lider_longo}'; esperava-se um "
        f"líder mais conservador na janela longa. {tabela}"
    )


def test_normal_tambem_acumula_desgaste():
    """Nenhum modo é isento: operar em ritmo intermediário também castiga."""
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 500)
        unidade = motor.robos["mineradora-1"]

        _extrair(cliente, modo="normal")
        motor.avancar_ciclo(1)

        assert unidade.desgaste > 0.0
