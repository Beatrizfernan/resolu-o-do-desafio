from mundo.eventos.barramento import BarramentoDeEventos


def test_publicar_registra_e_retorna_evento():
    barramento = BarramentoDeEventos()
    evento = barramento.publicar("carga_disponivel", ciclo=10, dados={"carga": "c1"})
    assert evento.tipo == "carga_disponivel"
    assert evento.ciclo == 10
    assert evento.identificador == "evt-1"


def test_consultar_eventos_filtra_por_ciclo():
    barramento = BarramentoDeEventos()
    barramento.publicar("a", ciclo=1, dados={})
    barramento.publicar("b", ciclo=5, dados={})
    resultado = barramento.consultar_eventos(desde_ciclo=3)
    assert [e.tipo for e in resultado] == ["b"]


def test_assinantes_sao_notificados():
    barramento = BarramentoDeEventos()
    recebidos = []
    barramento.assinar(recebidos.append)
    barramento.publicar("x", ciclo=1, dados={})
    assert len(recebidos) == 1
    assert recebidos[0].tipo == "x"
