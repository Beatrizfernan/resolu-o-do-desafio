from mundo.motor.efeitos import AgendaDeEfeitos


def test_dispara_apenas_efeitos_com_ciclo_alvo_atingido():
    agenda = AgendaDeEfeitos()
    disparados = []
    agenda.agendar(5, lambda: disparados.append("a"))
    agenda.agendar(10, lambda: disparados.append("b"))

    agenda.disparar_ate(5)

    assert disparados == ["a"]


def test_dispara_efeitos_em_ordem_de_ciclo_alvo():
    agenda = AgendaDeEfeitos()
    disparados = []
    agenda.agendar(10, lambda: disparados.append("b"))
    agenda.agendar(5, lambda: disparados.append("a"))

    agenda.disparar_ate(10)

    assert disparados == ["a", "b"]


def test_efeito_ja_disparado_nao_dispara_de_novo():
    agenda = AgendaDeEfeitos()
    disparados = []
    agenda.agendar(5, lambda: disparados.append("a"))
    agenda.disparar_ate(5)
    agenda.disparar_ate(10)
    assert disparados == ["a"]
