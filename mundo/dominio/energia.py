from __future__ import annotations


class EnergiaInsuficienteError(Exception):
    pass


class CentralDesconhecidaError(Exception):
    pass


class GerenciadorDeEnergia:
    RESERVA = "reserva_estrategica"

    def __init__(
        self,
        centrais: list[str],
        energia_inicial_por_central: int = 10,
        energia_total: int = 1000,
    ) -> None:
        saldo_inicial_centrais = energia_inicial_por_central * len(centrais)
        self._saldos: dict[str, int] = {central: energia_inicial_por_central for central in centrais}
        self._saldos[self.RESERVA] = energia_total - saldo_inicial_centrais

    def consultar_energia(self, central: str) -> int:
        self._validar_central(central)
        return self._saldos[central]

    def alocar_energia(self, origem: str, destino: str, quantidade: int) -> None:
        if origem != self.RESERVA:
            raise PermissionError("Somente a Central de Missão pode alocar a partir da reserva")
        self._transferir(origem, destino, quantidade)

    def redistribuir_energia(self, origem: str, destino: str, quantidade: int) -> None:
        self._transferir(origem, destino, quantidade)

    def revogar_energia(self, central: str, quantidade: int) -> None:
        self._validar_central(central)
        if self._saldos[central] < quantidade:
            raise EnergiaInsuficienteError(central)
        self._saldos[central] -= quantidade
        self._saldos[self.RESERVA] += quantidade

    def debitar(self, central: str, quantidade: int) -> None:
        self._validar_central(central)
        if self._saldos[central] < quantidade:
            raise EnergiaInsuficienteError(central)
        self._saldos[central] -= quantidade

    def _transferir(self, origem: str, destino: str, quantidade: int) -> None:
        self._validar_central(origem)
        self._validar_central(destino)
        if self._saldos[origem] < quantidade:
            raise EnergiaInsuficienteError(origem)
        self._saldos[origem] -= quantidade
        self._saldos[destino] += quantidade

    def _validar_central(self, central: str) -> None:
        if central not in self._saldos:
            raise CentralDesconhecidaError(central)
