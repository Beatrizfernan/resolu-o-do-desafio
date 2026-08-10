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
        energia_inicial_por_central: float = 10,
        energia_total: float = 1000,
    ) -> None:
        saldo_inicial_centrais = energia_inicial_por_central * len(centrais)
        self._saldos: dict[str, float] = {central: energia_inicial_por_central for central in centrais}
        self._saldos[self.RESERVA] = energia_total - saldo_inicial_centrais

    def consultar_energia(self, central: str) -> float:
        self._validar_central(central)
        return self._saldos[central]

    def esta_operante(self, central: str) -> bool:
        """Uma central sem saldo fica dormente: não executa nem consome.

        Dormente, não morta — alocar energia para ela a traz de volta. A única
        exceção é a missão, e não por regra especial daqui: é que sem ela não
        existe quem aloque.
        """
        self._validar_central(central)
        return self._saldos[central] > 0.0

    def debitar_ate_o_saldo(self, central: str, quantidade: float) -> float:
        """Debita no máximo o que houver, e devolve quanto foi debitado.

        O consumo por ciclo é involuntário: a central não escolheu existir
        naquele ciclo, então não pode ser rejeitada por não poder pagar. Ela
        entrega o que resta e fica dormente. `debitar` continua levantando,
        porque uma operação que não cabe no saldo tem mesmo que ser recusada.
        """
        self._validar_central(central)
        if quantidade < 0.0:
            raise ValueError(f"Consumo não pode ser negativo: {quantidade}")
        debitado = min(quantidade, self._saldos[central])
        self._saldos[central] -= debitado
        return debitado

    def alocar_energia(self, origem: str, destino: str, quantidade: float) -> None:
        self._validar_quantidade(quantidade)
        if origem != self.RESERVA:
            raise PermissionError("Somente a Central de Missão pode alocar a partir da reserva")
        self._transferir(origem, destino, quantidade)

    def redistribuir_energia(self, origem: str, destino: str, quantidade: float) -> None:
        self._validar_quantidade(quantidade)
        self._transferir(origem, destino, quantidade)

    def revogar_energia(self, central: str, quantidade: float) -> None:
        self._validar_quantidade(quantidade)
        self._validar_central(central)
        if self._saldos[central] < quantidade:
            raise EnergiaInsuficienteError(central)
        self._saldos[central] -= quantidade
        self._saldos[self.RESERVA] += quantidade

    def debitar(self, central: str, quantidade: float) -> None:
        self._validar_quantidade(quantidade)
        self._validar_central(central)
        if self._saldos[central] < quantidade:
            raise EnergiaInsuficienteError(central)
        self._saldos[central] -= quantidade

    def _transferir(self, origem: str, destino: str, quantidade: float) -> None:
        self._validar_central(origem)
        self._validar_central(destino)
        if self._saldos[origem] < quantidade:
            raise EnergiaInsuficienteError(origem)
        self._saldos[origem] -= quantidade
        self._saldos[destino] += quantidade

    def _validar_central(self, central: str) -> None:
        if central not in self._saldos:
            raise CentralDesconhecidaError(central)

    def _validar_quantidade(self, quantidade: float) -> None:
        if quantidade <= 0:
            raise ValueError("Quantidade deve ser positiva")
