from __future__ import annotations

from math import ceil

from centrais.contratos import HandoffDeTransporte

from .catalogo import MINERAIS
from .modelos import CargaDisponivel, UnidadeProjetada
from .planejador import escolher_candidato, escolher_carga, destino_para


class CentralDeTransporte:
    def __init__(self) -> None:
        self.cargas: dict[str, CargaDisponivel] = {}
        self.estados: dict[str, str] = {}
        self.unidades: dict[str, UnidadeProjetada] = {}
        self.eventos_processados: set[str] = set()
        self.handoffs: list[HandoffDeTransporte] = []
        self._handoffs_emitidos: set[str] = set()
        self._energia_pedida_no_ciclo: set[int] = set()
        self._armazem_de_cristais = "armazem-2"
        self.despachos_raros_consecutivos = 0
        self.decisoes: list[dict] = []

    @property
    def armazem_de_cristais(self) -> str:
        return self._armazem_de_cristais

    def tick(self, cliente, eventos: list[dict], ciclo_atual: int) -> None:
        self._descobrir_armazens(cliente)
        self._sincronizar_unidades(cliente)
        self._processar_eventos(cliente, eventos, ciclo_atual)
        self._sincronizar_cargas(cliente)
        self._despachar_se_possivel(cliente, ciclo_atual)

    def _descobrir_armazens(self, cliente) -> None:
        armazens = cliente.chamar("GET", "/armazenagem/armazens")
        ids = {armazem["identificador"] for armazem in armazens}
        self._armazem_de_cristais = "armazem-3" if "armazem-3" in ids else "armazem-2"

    def _sincronizar_unidades(self, cliente) -> None:
        publicas = cliente.chamar("GET", "/transporte/transportadores")
        publicas_por_id = {u["identificador"]: u for u in publicas}
        for identificador, unidade in publicas_por_id.items():
            atual = self.unidades.get(identificador, UnidadeProjetada(identificador, "disponivel"))
            desgaste = atual.desgaste
            if unidade["estado"] == "disponivel":
                desgaste = max(0.0, desgaste - 0.15)
            self.unidades[identificador] = UnidadeProjetada(
                identificador=identificador,
                estado=unidade["estado"],
                desgaste=desgaste,
                viagens_restantes=atual.viagens_restantes,
            )

    def _processar_eventos(self, cliente, eventos: list[dict], ciclo_atual: int) -> None:
        for evento in eventos:
            identificador = evento.get("identificador", f"{evento['tipo']}:{evento['ciclo']}:{evento['dados']}")
            if identificador in self.eventos_processados:
                continue
            self.eventos_processados.add(identificador)
            tipo = evento["tipo"]
            dados = evento["dados"]
            if tipo == "extracao_concluida":
                self._registrar_carga(dados["carga"], ciclo_atual)
            elif tipo == "carga_disponivel":
                if self.estados.get(dados["carga"]) not in {"handoff_concluido", "em_transito"}:
                    self._registrar_carga(dados["carga"], ciclo_atual)
            elif tipo == "viagem_abortada":
                self.estados[dados["carga"]] = "pendente"
                self._atualizar_unidade(dados["unidade"], estado="disponivel")
            elif tipo == "transporte_concluido":
                carga = dados["carga"]
                unidade = dados["unidade"]
                self._atualizar_unidade(unidade, estado="retornando", desgaste=dados.get("desgaste_da_unidade"))
                cliente.chamar("POST", "/transporte/descarregar", {
                    "identificador_da_unidade": unidade,
                    "identificador_da_carga": carga,
                })
                cliente.chamar("POST", "/transporte/retornar-unidade", {
                    "identificador_da_unidade": unidade,
                })
                self._emitir_handoff(carga, ciclo_atual)
            elif tipo == "operacao_invalida" and dados.get("central") == "transporte":
                self.decisoes.append({"ciclo": ciclo_atual, "motivo": "OPERACAO_INVALIDA", "dados": dados})

    def _registrar_carga(self, identificador: str, ciclo_atual: int) -> None:
        if identificador in self._handoffs_emitidos:
            return
        self.estados.setdefault(identificador, "pendente")
        self.cargas.setdefault(identificador, CargaDisponivel(identificador, "hematita", 0.0, ciclo_atual))

    def _sincronizar_cargas(self, cliente) -> None:
        dados_por_id = {c["identificador"]: c for c in cliente.chamar("GET", "/transporte/cargas-disponiveis")}
        for identificador in list(self.cargas):
            dados = dados_por_id.get(identificador)
            if dados is None:
                self.cargas.pop(identificador, None)
                self.estados.pop(identificador, None)
                continue
            antiga = self.cargas[identificador]
            self.cargas[identificador] = CargaDisponivel(
                identificador=identificador,
                mineral=dados["mineral"],
                quantidade=dados["quantidade"],
                ciclo_de_entrada=antiga.ciclo_de_entrada,
            )

    def _despachar_se_possivel(self, cliente, ciclo_atual: int) -> None:
        estado = cliente.consultar_estado()
        saldo_transporte = estado["energia"]["transporte"]
        rotas_por_id = {rota["identificador"]: rota for rota in cliente.chamar("GET", "/transporte/rotas")}
        pendentes = [
            carga for carga in self.cargas.values()
            if self.estados.get(carga.identificador) == "pendente" and carga.quantidade > 0
        ]
        for _ in range(len([u for u in self.unidades.values() if u.estado == "disponivel"])):
            pendentes = [c for c in pendentes if self.estados.get(c.identificador) == "pendente"]
            carga = escolher_carga(
                pendentes,
                ciclo_atual,
                self.despachos_raros_consecutivos,
                sum(u.viagens_restantes for u in self.unidades.values()),
            )
            if carga is None:
                return
            plano = cliente.chamar("GET", f"/transporte/planejar-transporte?identificador_da_carga={carga.identificador}")
            rotas = [rotas_por_id[identificador] for identificador in plano.get("rotas_disponiveis", []) if identificador in rotas_por_id]
            unidades = list(self.unidades.values())
            if _ha_rara(pendentes):
                disponiveis = [u for u in unidades if u.estado == "disponivel"]
                if MINERAIS[carga.mineral].prioridade >= 3 and len(disponiveis) <= 1:
                    self._registrar_decisao(ciclo_atual, carga, "COMUM_ADIADO_POR_RARO")
                    return
            candidato = escolher_candidato(carga, unidades, rotas, exigir_preferencial=True)
            if candidato is None:
                self._registrar_decisao(ciclo_atual, carga, "SEM_ROTA_SEGURA")
                return
            if saldo_transporte < candidato.saldo_minimo:
                self._solicitar_energia(cliente, ciclo_atual, candidato.saldo_minimo - saldo_transporte)
                self._registrar_decisao(ciclo_atual, carga, "ENERGIA_INCREMENTAL_SOLICITADA")
                return
            autorizacao = cliente.chamar("POST", "/missao/autorizar-missao", {
                "operacao": "iniciar_viagem",
                "central_solicitante": "transporte",
                "classe": "rapida",
            })["id_autorizacao"]
            cliente.chamar("POST", "/transporte/carregar", {
                "identificador_da_unidade": candidato.unidade.identificador,
                "identificador_da_carga": carga.identificador,
            })
            cliente.chamar("POST", "/transporte/iniciar-viagem", {
                "identificador_da_unidade": candidato.unidade.identificador,
                "identificador_da_rota": candidato.rota["identificador"],
                "identificador_da_carga": carga.identificador,
                "id_autorizacao": autorizacao,
                "modo": candidato.modo,
            })
            self.estados[carga.identificador] = "em_transito"
            self._atualizar_unidade(
                candidato.unidade.identificador,
                estado="aguardando",
                viagens_restantes=max(0, candidato.unidade.viagens_restantes - 1),
            )
            saldo_transporte -= candidato.energia
            if MINERAIS[carga.mineral].prioridade <= 2:
                self.despachos_raros_consecutivos += 1
            else:
                self.despachos_raros_consecutivos = 0
            self.decisoes.append({
                "ciclo": ciclo_atual,
                "carga": carga.identificador,
                "mineral": carga.mineral,
                "prioridade": f"P{MINERAIS[carga.mineral].prioridade}",
                "rota": candidato.rota["identificador"],
                "perfil": candidato.rota["perfil"],
                "modo": candidato.modo,
                "unidade": candidato.unidade.identificador,
                "duracao": candidato.duracao,
                "energia": round(candidato.energia, 3),
                "perda_de_valor": round(candidato.perda_de_valor, 3),
                "risco": candidato.risco,
                "score": round(candidato.score, 6),
                "motivo": "PLANO_DESPACHADO",
            })

    def _solicitar_energia(self, cliente, ciclo_atual: int, deficit: float) -> None:
        if ciclo_atual in self._energia_pedida_no_ciclo:
            return
        quantidade = max(1, ceil(deficit))
        cliente.chamar("POST", "/missao/alocar-energia", {
            "destino": "transporte",
            "quantidade": quantidade,
            "politica": "contingencia",
        })
        self._energia_pedida_no_ciclo.add(ciclo_atual)

    def _emitir_handoff(self, identificador: str, ciclo_atual: int) -> None:
        if identificador in self._handoffs_emitidos or identificador not in self.cargas:
            return
        carga = self.cargas[identificador]
        destino = destino_para(carga, self._armazem_de_cristais, ciclo_atual)
        self.handoffs.append(HandoffDeTransporte(identificador, carga.mineral, **destino))
        self._handoffs_emitidos.add(identificador)
        self.estados[identificador] = "handoff_concluido"

    def _atualizar_unidade(
        self,
        identificador: str,
        estado: str | None = None,
        desgaste: float | None = None,
        viagens_restantes: int | None = None,
    ) -> None:
        atual = self.unidades.get(identificador, UnidadeProjetada(identificador, "disponivel"))
        self.unidades[identificador] = UnidadeProjetada(
            identificador=identificador,
            estado=estado or atual.estado,
            desgaste=atual.desgaste if desgaste is None else desgaste,
            viagens_restantes=atual.viagens_restantes if viagens_restantes is None else viagens_restantes,
        )

    def _registrar_decisao(self, ciclo_atual: int, carga: CargaDisponivel, motivo: str) -> None:
        self.decisoes.append({
            "ciclo": ciclo_atual,
            "carga": carga.identificador,
            "mineral": carga.mineral,
            "prioridade": f"P{MINERAIS[carga.mineral].prioridade}",
            "motivo": motivo,
        })


def _ha_rara(cargas: list[CargaDisponivel]) -> bool:
    return any(MINERAIS[carga.mineral].prioridade <= 2 for carga in cargas)
