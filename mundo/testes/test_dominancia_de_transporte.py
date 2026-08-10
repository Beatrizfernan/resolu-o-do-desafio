"""Cada modo de transporte precisa vencer em algum cenário — no mundo real.

A suíte de `test_dominancia_de_modos.py` mede o transporte com uma conta
estática, sem desgaste e varrendo comprimentos de rota arbitrários. Ela não
enxerga o mundo que a simulação de fato gera: enquanto as rotas do mundo
existirem só em dois comprimentos, é sobre esses dois que a decisão precisa
existir.

Estes testes operam o motor de verdade — com desgaste, degradação em trânsito e
o acúmulo de ambos ao longo de uma janela contínua — e usam as rotas que o
mundo cria, lidas do próprio motor.
"""
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.cargas import CargaMineral, LocalDaCarga
from mundo.dominio.modos import ModoDeTransporte
from mundo.dominio.robos import EstadoDoRobo

CICLOS_DE_OPERACAO_CONTINUA = 250
QUANTIDADE_POR_VIAGEM = 10.0


def _autorizar(cliente) -> str:
    resposta = cliente.post(
        "/missao/autorizar-missao",
        json={"operacao": "iniciar_viagem", "central_solicitante": "transporte"},
    )
    return resposta.json()["id_autorizacao"]


def _rotas_do_mundo() -> list[str]:
    """Os identificadores de rota que a geração do mundo cria.

    Lido do motor, não fixado aqui: se o mundo passar a gerar outras rotas, o
    teste acompanha em vez de continuar medindo um mundo que não existe mais.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        return list(instancia_do_mundo.obter_motor().rotas)


def _valor_por_energia(modo: str, mineral: str, rota: str) -> float:
    """Valor entregue por energia gasta, transportando sem pausas.

    O valor é medido na chegada, então a degradação sofrida no caminho já está
    descontada — é isso que faz a pressa valer ou não valer a pena.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "transporte", 800)
        unidade = motor.robos["transportadora-1"]
        # O teto de viagens existe para a missão, não para esta medição: aqui o
        # que se compara é o regime sustentado, não quantas viagens cabem.
        unidade.viagens_disponiveis = 10**6
        info = motor.catalogo_de_minerais.obter(mineral)
        entregue = [0.0]

        def ao_evento(evento) -> None:
            if evento.tipo == "transporte_concluido":
                carga = motor.cargas.get(evento.dados["carga"])
                qualidade = carga.qualidade if carga else 0.0
                entregue[0] += (
                    QUANTIDADE_POR_VIAGEM * info.valor_por_unidade * (qualidade / 100)
                )

        motor.eventos.assinar(ao_evento)
        energia_antes = motor.energia.consultar_energia("transporte")
        despachadas = 0

        for _ in range(CICLOS_DE_OPERACAO_CONTINUA):
            if unidade.estado == EstadoDoRobo.DISPONIVEL:
                despachadas += 1
                nome = f"carga-{despachadas}"
                motor.cargas[nome] = CargaMineral(
                    nome, mineral, QUANTIDADE_POR_VIAGEM, 100.0,
                    local=LocalDaCarga.NA_MAO,
                )
                cliente.post(
                    "/transporte/iniciar-viagem",
                    json={
                        "identificador_da_unidade": "transportadora-1",
                        "identificador_da_rota": rota,
                        "identificador_da_carga": nome,
                        "modo": modo,
                        "id_autorizacao": _autorizar(cliente),
                    },
                )
            elif unidade.estado in (EstadoDoRobo.AGUARDANDO, EstadoDoRobo.RETORNANDO):
                # A unidade volta para DISPONIVEL sozinha só depois de retornar;
                # aqui a liberamos na hora porque o que se mede é o transporte,
                # não a logística de retorno.
                unidade.estado = EstadoDoRobo.DISPONIVEL
            motor.avancar_ciclo(1)

        gasto = energia_antes - motor.energia.consultar_energia("transporte")
        assert gasto > 0.0, f"nenhuma energia gasta em modo {modo}: medição inválida"
        return entregue[0] / gasto


def _vencedores_por_cenario() -> dict[tuple[str, str], str]:
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        minerais = [m.nome for m in instancia_do_mundo.obter_motor().catalogo_de_minerais.todos()]

    vencedores = {}
    for rota in _rotas_do_mundo():
        for mineral in minerais:
            retorno = {
                modo.value: _valor_por_energia(modo.value, mineral, rota)
                for modo in ModoDeTransporte
            }
            vencedores[(rota, mineral)] = max(retorno, key=retorno.get)
    return vencedores


def test_todo_modo_de_transporte_vence_em_algum_cenario_do_mundo_real():
    """Nenhum modo pode ser inútil, e nenhum pode ser a resposta universal.

    Este teste existe porque a suíte estática deixou passar exatamente isso: por
    muito tempo `economico` foi a escolha certa em todas as combinações que o
    mundo é capaz de produzir, enquanto a suíte, varrendo comprimentos de rota
    inexistentes, continuava verde.
    """
    vencedores = _vencedores_por_cenario()
    presentes = set(vencedores.values())
    ausentes = {modo.value for modo in ModoDeTransporte} - presentes

    detalhe = "; ".join(
        f"{rota}/{mineral}={modo}" for (rota, mineral), modo in sorted(vencedores.items())
    )
    assert not ausentes, (
        f"modos de transporte que não vencem em cenário nenhum do mundo: "
        f"{sorted(ausentes)}. {detalhe}"
    )


def test_a_pressa_compensa_para_carga_rara_e_nao_para_carga_comum():
    """A raridade em trânsito é o que dá sentido ao modo rápido.

    Minério raro se degrada mais depressa no caminho, então quem carrega
    cristal ou jarosita paga por velocidade; quem carrega hematita não tem por
    que pagar. Sem esse eixo, `economico` seria sempre a resposta — velocidade
    não compraria nada que valesse a energia a mais.

    A comparação é entre o mineral menos raro do catálogo e o mais raro, lidos
    do catálogo em vez de fixados, para o teste não descolar da configuração.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        minerais = instancia_do_mundo.obter_motor().catalogo_de_minerais.todos()
    mais_comum = min(minerais, key=lambda m: m.raridade)
    mais_raro = max(minerais, key=lambda m: m.raridade)
    rota = _rotas_do_mundo()[0]

    def lider(mineral: str) -> str:
        retorno = {
            modo.value: _valor_por_energia(modo.value, mineral, rota)
            for modo in ModoDeTransporte
        }
        return max(retorno, key=retorno.get)

    lider_comum = lider(mais_comum.nome)
    lider_raro = lider(mais_raro.nome)

    assert lider_comum == ModoDeTransporte.ECONOMICO.value, (
        f"para o mineral mais comum ({mais_comum.nome}, raridade "
        f"{mais_comum.raridade}) esperava-se que o transporte barato vencesse, "
        f"mas venceu '{lider_comum}'"
    )
    assert lider_raro != ModoDeTransporte.ECONOMICO.value, (
        f"para o mineral mais raro ({mais_raro.nome}, raridade "
        f"{mais_raro.raridade}) o transporte mais lento e barato ainda vence "
        f"('{lider_raro}'): a raridade em trânsito não está cobrando nada"
    )
