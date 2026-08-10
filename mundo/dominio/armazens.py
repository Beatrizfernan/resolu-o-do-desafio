from __future__ import annotations

from dataclasses import dataclass, field


class CapacidadeExcedidaError(Exception):
    pass


class CargaNaoEstaNoArmazemError(Exception):
    pass


@dataclass
class Armazem:
    identificador: str
    capacidade: float
    localizacao: str
    condicoes: str
    compatibilidades: set[str] = field(default_factory=set)
    ocupacao: float = 0.0
    pilha: list[str] = field(default_factory=list)

    def reservar_espaco(self, quantidade: float) -> None:
        if self.ocupacao + quantidade > self.capacidade:
            raise CapacidadeExcedidaError(self.identificador)
        self.ocupacao += quantidade

    def liberar_espaco(self, quantidade: float) -> None:
        self.ocupacao = max(0.0, self.ocupacao - quantidade)

    def compativel_com(self, mineral: str) -> bool:
        return not self.compatibilidades or mineral in self.compatibilidades

    def empilhar(self, identificador: str, quantidade: float) -> None:
        """Coloca a carga no topo e soma a ocupação.

        Pilha e ocupação são um par: a ocupação é função do que está
        empilhado, e escrever uma sem a outra faz o armazém mentir sobre o
        próprio conteúdo.
        """
        if identificador in self.pilha:
            raise ValueError(f"Carga já está no armazém: {identificador}")
        self.reservar_espaco(quantidade)
        self.pilha.append(identificador)

    def profundidade(self, identificador: str) -> int:
        """Quantas cargas estão em cima desta. O topo tem profundidade zero."""
        if identificador not in self.pilha:
            raise CargaNaoEstaNoArmazemError(identificador)
        return len(self.pilha) - 1 - self.pilha.index(identificador)

    def desempilhar_ate(self, identificador: str, quantidades: dict[str, float]) -> list[str]:
        """Remove a carga alvo e tudo que está acima dela.

        Devolve os removidos do topo para baixo, que é a ordem em que saem.
        Não existe retirada cirúrgica: alcançar o que está enterrado
        desenterra o que está por cima, e recolocar é decisão à parte.
        """
        if identificador not in self.pilha:
            raise CargaNaoEstaNoArmazemError(identificador)
        indice = self.pilha.index(identificador)
        removidos = self.pilha[indice:]
        faltando = [nome for nome in removidos if nome not in quantidades]
        if faltando:
            raise KeyError(f"Quantidade ausente para: {faltando}")
        self.pilha = self.pilha[:indice]
        for nome in removidos:
            self.liberar_espaco(quantidades[nome])
        return list(reversed(removidos))

    def reordenar(self, nova_ordem: list[str]) -> int:
        """Reorganiza a pilha e devolve a soma dos deslocamentos.

        O custo de reorganizar é proporcional ao quanto se mexeu, e não ao
        tamanho da pilha: preservar a parte que já está na ordem certa é mais
        barato que remontar tudo.
        """
        if sorted(nova_ordem) != sorted(self.pilha):
            raise ValueError("A nova ordem precisa ser uma permutação exata da pilha")
        posicao_antiga = {nome: i for i, nome in enumerate(self.pilha)}
        movimentos = sum(abs(i - posicao_antiga[nome]) for i, nome in enumerate(nova_ordem))
        self.pilha = list(nova_ordem)
        return movimentos
