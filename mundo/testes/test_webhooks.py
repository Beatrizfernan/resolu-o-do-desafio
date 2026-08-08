from mundo.eventos.evento import Evento
from mundo.eventos.webhooks import DispatcherDeWebhooks


def test_registrar_adiciona_url():
    dispatcher = DispatcherDeWebhooks()
    dispatcher.registrar("http://exemplo.local/webhook")
    assert "http://exemplo.local/webhook" in dispatcher.urls_registradas()


def test_notificar_sem_urls_registradas_nao_lanca_erro():
    dispatcher = DispatcherDeWebhooks()
    evento = Evento(identificador="evt-1", tipo="carga_disponivel", ciclo=1, dados={})
    dispatcher.notificar(evento)  # não deve lançar, mesmo sem event loop rodando
