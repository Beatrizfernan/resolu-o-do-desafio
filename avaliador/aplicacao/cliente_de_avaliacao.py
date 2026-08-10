from __future__ import annotations

from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import obter_motor


class ClienteDeAvaliacao:
    def __init__(self) -> None:
        self._app = criar_app(com_loop_real_time=False)
        self._cliente_http_contexto = TestClient(self._app)
        self._cliente_http = self._cliente_http_contexto.__enter__()

    def __del__(self) -> None:
        contexto = getattr(self, "_cliente_http_contexto", None)
        if contexto is not None:
            contexto.__exit__(None, None, None)

    def resetar(self, semente: int) -> None:
        resposta = self._cliente_http.post("/missao/resetar-mundo", json={"semente": semente})
        resposta.raise_for_status()

    def consultar_estado(self) -> dict:
        return self.chamar("GET", "/missao/estado")

    def consultar_eventos(self, desde_ciclo: int = 0) -> list[dict]:
        return self.chamar("GET", f"/missao/eventos?desde_ciclo={desde_ciclo}")

    def chamar(self, metodo: str, rota: str, json: dict | None = None):
        resposta = self._cliente_http.request(metodo, rota, json=json)
        resposta.raise_for_status()
        return resposta.json()

    def avancar_ciclo(self, quantidade: int = 1) -> None:
        obter_motor().avancar_ciclo(quantidade)

    def simulacao_encerrada(self) -> bool:
        return obter_motor().encerrada
