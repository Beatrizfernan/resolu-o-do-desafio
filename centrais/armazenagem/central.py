from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class PerfilDeMineral:
    """Números de `mundo/config/minerais.json`.

    Replicados aqui de propósito: nenhuma rota expõe o valor de um mineral, e
    importar de `mundo/` acoplaria a central ao território protegido.
    """

    valor_por_unidade: float
    taxa_degradacao: float
    sensibilidade_armazenagem: float


CATALOGO: Mapping[str, PerfilDeMineral] = {
    "hematita": PerfilDeMineral(5.0, 0.2, 0.1),
    "silica_de_alta_pureza": PerfilDeMineral(20.0, 0.4, 0.3),
    "jarosita": PerfilDeMineral(35.0, 0.7, 0.6),
    "gelo_de_agua": PerfilDeMineral(40.0, 0.9, 0.7),
    "cristal_marciano_raro": PerfilDeMineral(200.0, 0.3, 0.4),
}

# `multiplicador_por_local` em mundo/config/modos.json.
MULT_NA_MAO = 2.0
MULT_EM_ARMAZEM = 1.0


class CentralDeArmazenagem:
    """Decide o que guardar, em que ordem empilhar e quando desenterrar.

    Duas descobertas do motor sustentam este desenho:

    1. `iniciar-analise` e `aprovar-carga` não checam o local da carga. Só
       `preparar-distribuicao` exige que ela não esteja guardada. Então a
       carga pode passar a análise inteira dentro do armazém, degradando por
       `sensibilidade_armazenagem` em vez de pelo dobro da taxa cheia.

    2. Desenterrar custa pouca energia (0,8 por nível), mas `desempilhar_ate`
       arrasta tudo que está acima para `NA_MAO`. O preço real de uma pilha
       mal ordenada é a qualidade das cargas inocentes, não o débito.

    Daí a política: guarda quase sempre, empilha na ordem inversa da fila do
    laboratório, e paga `nova_ordem` no depósito (0,3 por deslocamento) para
    nunca precisar desenterrar.
    """

    def __init__(self, cliente: Any, central_de_missao: Any) -> None:
        self.cliente = cliente
        self.missao = central_de_missao

    # ------------------------------------------------------------ prioridade

    @staticmethod
    def sangria_por_ciclo(mineral: str, quantidade: float, *, guardada: bool) -> float:
        """Valor que a carga perde a cada ciclo parada, em unidades de faturamento.

        É a métrica que ordena a pilha. Ordenar por `taxa_degradacao` sozinha
        enterra o cristal — ele degrada devagar, mas vale 200 por quilo, então
        sangra mais que qualquer outro mineral fora do armazém.
        """
        perfil = CATALOGO.get(mineral)
        if perfil is None:
            return 0.0
        sensibilidade = perfil.sensibilidade_armazenagem if guardada else 1.0
        multiplicador = MULT_EM_ARMAZEM if guardada else MULT_NA_MAO
        perda_de_qualidade = perfil.taxa_degradacao * sensibilidade * multiplicador
        return quantidade * perfil.valor_por_unidade * (perda_de_qualidade / 100.0)

    def economia_ao_guardar(self, mineral: str, quantidade: float, ciclos: float) -> float:
        na_mao = self.sangria_por_ciclo(mineral, quantidade, guardada=False)
        guardada = self.sangria_por_ciclo(mineral, quantidade, guardada=True)
        return (na_mao - guardada) * ciclos

    # ------------------------------------------------------------- ordenação

    def ordem_desejada(self, cargas: Iterable[Mapping[str, Any]]) -> list[str]:
        """Do fundo para o topo, que é a ordem que `GET /armazens` devolve.

        Quem sangra mais fica no topo, porque sai primeiro e sai de graça:
        `profundidade` do topo é zero e o motor nem debita.
        """
        return [
            carga["identificador"]
            for carga in sorted(
                cargas,
                key=lambda c: (
                    self.sangria_por_ciclo(c["mineral"], float(c["quantidade"]), guardada=True),
                    c["identificador"],
                ),
            )
        ]

    # ----------------------------------------------------------------- ações

    def guardar(
        self,
        identificadores: list[str],
        cargas_conhecidas: Mapping[str, Mapping[str, Any]],
        *,
        armazem: str = "armazem-1",
    ) -> bool:
        """Deposita e já reordena a pilha inteira na mesma operação.

        Reordenar no depósito custa `0,3 x deslocamento` e é a única forma
        barata de colocar uma carga no meio da pilha. A alternativa é
        desenterrar depois, que joga as cargas de cima em `NA_MAO`.
        """
        if not identificadores:
            return False

        pilha_atual = self.consultar_pilha(armazem)
        pilha_resultante = pilha_atual + identificadores
        conhecidas = [
            cargas_conhecidas[identificador]
            for identificador in pilha_resultante
            if identificador in cargas_conhecidas
        ]
        nova_ordem = (
            self.ordem_desejada(conhecidas)
            if len(conhecidas) == len(pilha_resultante)
            else None
        )

        id_autorizacao = self.missao.autorizar("receber_carga", "armazenagem")
        payload: dict[str, Any] = {
            "identificador_do_armazem": armazem,
            "identificadores_das_cargas": identificadores,
            "id_autorizacao": id_autorizacao,
        }
        if nova_ordem is not None:
            payload["nova_ordem"] = nova_ordem
        self.cliente.chamar("POST", "/armazenagem/receber-carga", payload)
        return True

    def retirar(self, identificador: str, *, armazem: str = "armazem-1") -> list[str]:
        """Desenterra a carga. Devolve quem mais saiu junto, do topo para baixo.

        O retorno importa: tudo que veio junto está agora em `NA_MAO`
        degradando pelo dobro, e precisa ser guardado de novo ou vendido logo.
        """
        pilha = self.consultar_pilha(armazem)
        if identificador not in pilha:
            return []
        arrastados = pilha[pilha.index(identificador) + 1 :]

        id_autorizacao = self.missao.autorizar("retirar_carga", "armazenagem")
        self.cliente.chamar("POST", "/armazenagem/retirar-carga", {
            "identificador_do_armazem": armazem,
            "identificador_da_carga": identificador,
            "id_autorizacao": id_autorizacao,
        })
        return list(reversed(arrastados))

    # ---------------------------------------------------------------- estado

    def consultar_pilha(self, armazem: str = "armazem-1") -> list[str]:
        for registro in self.cliente.chamar("GET", "/armazenagem/armazens"):
            if registro["identificador"] == armazem:
                return list(registro.get("pilha", []))
        return []

    def esta_guardada(self, identificador: str, *, armazem: str = "armazem-1") -> bool:
        return identificador in self.consultar_pilha(armazem)
