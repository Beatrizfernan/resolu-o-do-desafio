# Mundo — Núcleo Mecânico Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the working, testable core of `mundo/` — domain entities, the tick-based simulation engine (command queue + scheduled effects + seeded RNG), and HTTP APIs for all five Centrais — as a walking skeleton over `SPEC_INICIAL.md` and `DOCUMENTACAO_DO_PROJETO.md`.

**Architecture:** Single-process, single-event-loop FastAPI app. A `MotorDeSimulacao` owns all domain state; HTTP handlers translate requests into `Comando` objects appended to a queue, never mutating state directly. A tick (`avancar_ciclo`) drains the queue, fires scheduled effects, and publishes events — driven either by a real-time asyncio loop or by direct manual calls (tests, future Avaliador).

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, httpx (webhook delivery), pytest.

## Global Constraints

- Todo código de domínio (classes, métodos, funções, variáveis, eventos, comandos, endpoints, docs, mensagens, testes) em português. Termos técnicos inevitáveis de framework podem permanecer no idioma original. (`SPEC_INICIAL.md` §2)
- `energia_total = 1000`, `energia_inicial_por_central = 10` para cada uma das 5 Centrais; reserva estratégica = 950, controlada só pela Central de Missão. (`SPEC_INICIAL.md` §7)
- **Sem geração de energia** — decisão explícita do dono do projeto, diverge de `SPEC_INICIAL.md` §8. Pool estritamente finito, nunca regenera.
- Toda aleatoriedade usa uma única instância `random.Random(semente)` por simulação — nunca o módulo `random` global. (`SPEC_INICIAL.md` §6, §37)
- `qualidade` de carga mineral sempre no intervalo [0, 100], clamped. (`SPEC_INICIAL.md` §12)
- Jazida esgotada nunca regenera. (`SPEC_INICIAL.md` §10)
- Comandos vindos de API não mutam estado na hora da chamada HTTP — entram em fila e são aplicados no próximo `avancar_ciclo` que os processar.
- Operações cross-central sensíveis exigem `id_autorizacao` emitido pela Central de Missão.
- Webhooks são fire-and-forget, sem retry.

## Fora de escopo deste plano

Geração automática de eventos ambientais/climáticos, eventos geológicos exploratórios (`jazida_identificada`, `desmoronamento`, etc.) e o sistema de oportunidades raras exigem fórmulas ainda não travadas na spec de design (`docs/superpowers/specs/2026-08-07-mundo-mvp-design.md` §3 deixa isso explicitamente parametrizável/não definitivo). Este plano entrega o núcleo mecânico completo e testável — domínio, motor, fila/agendamento, autorização, energia sem geração, e APIs das 5 Centrais. Um plano seguinte cobre clima, eventos geológicos e recursos raros sobre esse núcleo.

---

### Task 1: Scaffolding do projeto

**Files:**
- Create: `pyproject.toml`
- Create: `mundo/__init__.py`
- Create: `mundo/testes/__init__.py`
- Test: `mundo/testes/test_scaffolding.py`

**Interfaces:**
- Produces: pacote `mundo` importável, ambiente pytest configurado com `testpaths = ["mundo/testes"]`.

- [ ] **Step 1: Criar `pyproject.toml`**

```toml
[project]
name = "operacao-marte-mundo"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "pydantic>=2.9",
    "uvicorn[standard]>=0.30",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = ["pytest>=8.3", "pytest-asyncio>=0.24"]

[tool.pytest.ini_options]
testpaths = ["mundo/testes"]
asyncio_mode = "auto"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["mundo*"]
```

- [ ] **Step 2: Criar `mundo/__init__.py` e `mundo/testes/__init__.py` (vazios)**

- [ ] **Step 3: Instalar dependências**

Run: `pip install -e ".[dev]"`

- [ ] **Step 4: Escrever teste de fumaça**

```python
# mundo/testes/test_scaffolding.py
import mundo


def test_pacote_mundo_e_importavel():
    assert mundo is not None
```

- [ ] **Step 5: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_scaffolding.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml mundo/__init__.py mundo/testes/__init__.py mundo/testes/test_scaffolding.py
git commit -m "chore: scaffold mundo/ package and pytest config"
```

---

### Task 2: Catálogo de Minerais

**Files:**
- Create: `mundo/dominio/__init__.py`
- Create: `mundo/dominio/minerais.py`
- Create: `mundo/config/minerais.json`
- Test: `mundo/testes/test_minerais.py`

**Interfaces:**
- Produces: `Mineral` (dataclass), `CatalogoDeMinerais` com `.carregar_de_arquivo(caminho: Path) -> CatalogoDeMinerais`, `.obter(nome: str) -> Mineral`, `.todos() -> list[Mineral]`.

- [ ] **Step 1: Criar `mundo/config/minerais.json`**

```json
[
  {
    "nome": "hematita",
    "valor_por_unidade": 5.0,
    "raridade": 0.1,
    "custo_extracao": 1.0,
    "massa": 1.0,
    "taxa_degradacao": 0.2,
    "sensibilidade_temperatura": 0.1,
    "sensibilidade_transporte": 0.1,
    "sensibilidade_armazenagem": 0.1
  },
  {
    "nome": "silica_de_alta_pureza",
    "valor_por_unidade": 20.0,
    "raridade": 0.3,
    "custo_extracao": 2.0,
    "massa": 0.8,
    "taxa_degradacao": 0.4,
    "sensibilidade_temperatura": 0.3,
    "sensibilidade_transporte": 0.3,
    "sensibilidade_armazenagem": 0.3
  },
  {
    "nome": "jarosita",
    "valor_por_unidade": 35.0,
    "raridade": 0.6,
    "custo_extracao": 3.5,
    "massa": 1.2,
    "taxa_degradacao": 0.7,
    "sensibilidade_temperatura": 0.6,
    "sensibilidade_transporte": 0.6,
    "sensibilidade_armazenagem": 0.6
  },
  {
    "nome": "gelo_de_agua",
    "valor_por_unidade": 40.0,
    "raridade": 0.5,
    "custo_extracao": 2.5,
    "massa": 0.9,
    "taxa_degradacao": 0.9,
    "sensibilidade_temperatura": 0.9,
    "sensibilidade_transporte": 0.5,
    "sensibilidade_armazenagem": 0.7
  },
  {
    "nome": "cristal_marciano_raro",
    "valor_por_unidade": 200.0,
    "raridade": 0.95,
    "custo_extracao": 8.0,
    "massa": 0.3,
    "taxa_degradacao": 0.3,
    "sensibilidade_temperatura": 0.4,
    "sensibilidade_transporte": 0.4,
    "sensibilidade_armazenagem": 0.4
  }
]
```

- [ ] **Step 2: Criar `mundo/dominio/__init__.py` (vazio)**

- [ ] **Step 3: Escrever o teste falhando**

```python
# mundo/testes/test_minerais.py
from pathlib import Path

from mundo.dominio.minerais import CatalogoDeMinerais

CAMINHO_CATALOGO = Path(__file__).parent.parent / "config" / "minerais.json"


def test_carrega_catalogo_com_cinco_minerais():
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    assert len(catalogo.todos()) == 5


def test_obter_mineral_por_nome():
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    hematita = catalogo.obter("hematita")
    assert hematita.valor_por_unidade == 5.0


def test_obter_mineral_desconhecido_lanca_erro():
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    try:
        catalogo.obter("inexistente")
        assert False, "deveria ter lançado ValueError"
    except ValueError:
        pass
```

- [ ] **Step 4: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_minerais.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'mundo.dominio.minerais'`

- [ ] **Step 5: Implementar**

```python
# mundo/dominio/minerais.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Mineral:
    nome: str
    valor_por_unidade: float
    raridade: float
    custo_extracao: float
    massa: float
    taxa_degradacao: float
    sensibilidade_temperatura: float
    sensibilidade_transporte: float
    sensibilidade_armazenagem: float


class CatalogoDeMinerais:
    def __init__(self, minerais: dict[str, Mineral]) -> None:
        self._minerais = minerais

    @classmethod
    def carregar_de_arquivo(cls, caminho: Path) -> "CatalogoDeMinerais":
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        minerais = {item["nome"]: Mineral(**item) for item in dados}
        return cls(minerais)

    def obter(self, nome: str) -> Mineral:
        if nome not in self._minerais:
            raise ValueError(f"Mineral desconhecido: {nome}")
        return self._minerais[nome]

    def todos(self) -> list[Mineral]:
        return list(self._minerais.values())
```

- [ ] **Step 6: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_minerais.py -v`
Expected: PASS (3 passed)

- [ ] **Step 7: Commit**

```bash
git add mundo/dominio/__init__.py mundo/dominio/minerais.py mundo/config/minerais.json mundo/testes/test_minerais.py
git commit -m "feat: add mineral catalog loaded from config"
```

---

### Task 3: Envelope de Evento e Barramento de Eventos

**Files:**
- Create: `mundo/eventos/__init__.py`
- Create: `mundo/eventos/evento.py`
- Create: `mundo/eventos/barramento.py`
- Test: `mundo/testes/test_barramento_de_eventos.py`

**Interfaces:**
- Produces: `Evento` (dataclass frozen: `identificador`, `tipo`, `ciclo`, `dados`), `BarramentoDeEventos` com `.publicar(tipo, ciclo, dados) -> Evento`, `.consultar_eventos(desde_ciclo=0) -> list[Evento]`, `.assinar(callback)`.

- [ ] **Step 1: Criar `mundo/eventos/__init__.py` (vazio)**

- [ ] **Step 2: Escrever o teste falhando**

```python
# mundo/testes/test_barramento_de_eventos.py
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
```

- [ ] **Step 3: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_barramento_de_eventos.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 4: Implementar**

```python
# mundo/eventos/evento.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Evento:
    identificador: str
    tipo: str
    ciclo: int
    dados: dict[str, Any] = field(default_factory=dict)
```

```python
# mundo/eventos/barramento.py
from __future__ import annotations

import itertools
from typing import Callable

from .evento import Evento


class BarramentoDeEventos:
    def __init__(self) -> None:
        self._contador = itertools.count(1)
        self._registro: list[Evento] = []
        self._assinantes: list[Callable[[Evento], None]] = []

    def assinar(self, callback: Callable[[Evento], None]) -> None:
        self._assinantes.append(callback)

    def publicar(self, tipo: str, ciclo: int, dados: dict) -> Evento:
        identificador = f"evt-{next(self._contador)}"
        evento = Evento(identificador=identificador, tipo=tipo, ciclo=ciclo, dados=dados)
        self._registro.append(evento)
        for assinante in self._assinantes:
            assinante(evento)
        return evento

    def consultar_eventos(self, desde_ciclo: int = 0) -> list[Evento]:
        return [e for e in self._registro if e.ciclo >= desde_ciclo]
```

- [ ] **Step 5: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_barramento_de_eventos.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add mundo/eventos/__init__.py mundo/eventos/evento.py mundo/eventos/barramento.py mundo/testes/test_barramento_de_eventos.py
git commit -m "feat: add event envelope and event bus"
```

---

### Task 4: Gerenciador de Energia

**Files:**
- Create: `mundo/dominio/energia.py`
- Test: `mundo/testes/test_energia.py`

**Interfaces:**
- Consumes: nenhuma dependência interna nova.
- Produces: `GerenciadorDeEnergia(centrais, energia_inicial_por_central, energia_total)` com `.consultar_energia(central) -> int`, `.alocar_energia(origem, destino, quantidade)`, `.redistribuir_energia(origem, destino, quantidade)`, `.revogar_energia(central, quantidade)`, `.debitar(central, quantidade)`; constante `GerenciadorDeEnergia.RESERVA = "reserva_estrategica"`; exceções `EnergiaInsuficienteError`, `CentralDesconhecidaError`.

- [ ] **Step 1: Escrever o teste falhando**

```python
# mundo/testes/test_energia.py
import pytest

from mundo.dominio.energia import CentralDesconhecidaError, EnergiaInsuficienteError, GerenciadorDeEnergia

CENTRAIS = ["extracao", "armazenagem", "transporte", "pesquisa", "missao"]


def _criar_gerenciador() -> GerenciadorDeEnergia:
    return GerenciadorDeEnergia(CENTRAIS, energia_inicial_por_central=10, energia_total=1000)


def test_saldo_inicial_por_central_e_reserva():
    gerenciador = _criar_gerenciador()
    for central in CENTRAIS:
        assert gerenciador.consultar_energia(central) == 10
    assert gerenciador.consultar_energia(GerenciadorDeEnergia.RESERVA) == 950


def test_debitar_reduz_saldo():
    gerenciador = _criar_gerenciador()
    gerenciador.debitar("extracao", 4)
    assert gerenciador.consultar_energia("extracao") == 6


def test_debitar_alem_do_saldo_lanca_erro():
    gerenciador = _criar_gerenciador()
    with pytest.raises(EnergiaInsuficienteError):
        gerenciador.debitar("extracao", 999)


def test_alocar_energia_so_a_partir_da_reserva():
    gerenciador = _criar_gerenciador()
    with pytest.raises(PermissionError):
        gerenciador.alocar_energia("extracao", "transporte", 5)


def test_alocar_energia_da_reserva_transfere_saldo():
    gerenciador = _criar_gerenciador()
    gerenciador.alocar_energia(GerenciadorDeEnergia.RESERVA, "extracao", 50)
    assert gerenciador.consultar_energia("extracao") == 60
    assert gerenciador.consultar_energia(GerenciadorDeEnergia.RESERVA) == 900


def test_revogar_energia_devolve_para_reserva():
    gerenciador = _criar_gerenciador()
    gerenciador.revogar_energia("extracao", 5)
    assert gerenciador.consultar_energia("extracao") == 5
    assert gerenciador.consultar_energia(GerenciadorDeEnergia.RESERVA) == 955


def test_central_desconhecida_lanca_erro():
    gerenciador = _criar_gerenciador()
    with pytest.raises(CentralDesconhecidaError):
        gerenciador.consultar_energia("inexistente")
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_energia.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

```python
# mundo/dominio/energia.py
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
```

- [ ] **Step 4: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_energia.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add mundo/dominio/energia.py mundo/testes/test_energia.py
git commit -m "feat: add energy manager with fixed, non-regenerating pool"
```

---

### Task 5: Jazidas

**Files:**
- Create: `mundo/dominio/jazidas.py`
- Test: `mundo/testes/test_jazidas.py`

**Interfaces:**
- Produces: `EstadoDaJazida` (Enum: `DESCONHECIDA`, `IDENTIFICADA`, `DISPONIVEL`, `INTERDITADA`, `ESGOTADA`), `Jazida` (dataclass) com `.transicionar(novo_estado)`, `.extrair(quantidade)`; exceção `TransicaoDeEstadoInvalidaError`.

- [ ] **Step 1: Escrever o teste falhando**

```python
# mundo/testes/test_jazidas.py
import pytest

from mundo.dominio.jazidas import EstadoDaJazida, Jazida, TransicaoDeEstadoInvalidaError


def _criar_jazida(estado=EstadoDaJazida.DISPONIVEL, quantidade=100.0) -> Jazida:
    return Jazida(
        identificador="j1", localizacao="setor-1", mineral="hematita",
        quantidade_disponivel=quantidade, dificuldade_extracao=1.0, risco=0.1, estado=estado,
    )


def test_extrair_reduz_quantidade_disponivel():
    jazida = _criar_jazida(quantidade=100.0)
    jazida.extrair(30.0)
    assert jazida.quantidade_disponivel == 70.0


def test_extrair_ate_esgotar_transiciona_estado():
    jazida = _criar_jazida(quantidade=10.0)
    jazida.extrair(10.0)
    assert jazida.estado == EstadoDaJazida.ESGOTADA


def test_extrair_alem_do_disponivel_lanca_erro():
    jazida = _criar_jazida(quantidade=10.0)
    with pytest.raises(ValueError):
        jazida.extrair(20.0)


def test_extrair_de_jazida_nao_disponivel_lanca_erro():
    jazida = _criar_jazida(estado=EstadoDaJazida.INTERDITADA)
    with pytest.raises(ValueError):
        jazida.extrair(1.0)


def test_transicao_invalida_lanca_erro():
    jazida = _criar_jazida(estado=EstadoDaJazida.ESGOTADA)
    with pytest.raises(TransicaoDeEstadoInvalidaError):
        jazida.transicionar(EstadoDaJazida.DISPONIVEL)
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_jazidas.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

```python
# mundo/dominio/jazidas.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EstadoDaJazida(str, Enum):
    DESCONHECIDA = "desconhecida"
    IDENTIFICADA = "identificada"
    DISPONIVEL = "disponivel"
    INTERDITADA = "interditada"
    ESGOTADA = "esgotada"


class TransicaoDeEstadoInvalidaError(Exception):
    pass


_TRANSICOES_VALIDAS: dict[EstadoDaJazida, set[EstadoDaJazida]] = {
    EstadoDaJazida.DESCONHECIDA: {EstadoDaJazida.IDENTIFICADA},
    EstadoDaJazida.IDENTIFICADA: {EstadoDaJazida.DISPONIVEL, EstadoDaJazida.INTERDITADA},
    EstadoDaJazida.DISPONIVEL: {EstadoDaJazida.INTERDITADA, EstadoDaJazida.ESGOTADA},
    EstadoDaJazida.INTERDITADA: {EstadoDaJazida.DISPONIVEL},
    EstadoDaJazida.ESGOTADA: set(),
}


@dataclass
class Jazida:
    identificador: str
    localizacao: str
    mineral: str
    quantidade_disponivel: float
    dificuldade_extracao: float
    risco: float
    estado: EstadoDaJazida = EstadoDaJazida.DESCONHECIDA

    def transicionar(self, novo_estado: EstadoDaJazida) -> None:
        if novo_estado not in _TRANSICOES_VALIDAS[self.estado]:
            raise TransicaoDeEstadoInvalidaError(f"{self.estado} -> {novo_estado}")
        self.estado = novo_estado

    def extrair(self, quantidade: float) -> None:
        if self.estado != EstadoDaJazida.DISPONIVEL:
            raise ValueError("Jazida não disponível para extração")
        if quantidade > self.quantidade_disponivel:
            raise ValueError("Quantidade solicitada excede o disponível")
        self.quantidade_disponivel -= quantidade
        if self.quantidade_disponivel == 0:
            self.transicionar(EstadoDaJazida.ESGOTADA)
```

- [ ] **Step 4: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_jazidas.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add mundo/dominio/jazidas.py mundo/testes/test_jazidas.py
git commit -m "feat: add jazida entity with state machine, never regenerates when depleted"
```

---

### Task 6: Robôs

**Files:**
- Create: `mundo/dominio/robos.py`
- Test: `mundo/testes/test_robos.py`

**Interfaces:**
- Produces: `EstadoDoRobo` (Enum: `DISPONIVEL`, `EXECUTANDO`, `AGUARDANDO`, `RETORNANDO`, `INDISPONIVEL`), `Robo` (dataclass base), `UnidadeMineradora(Robo)`, `UnidadeTransportadora(Robo)` (com `viagens_disponiveis: int`).

- [ ] **Step 1: Escrever o teste falhando**

```python
# mundo/testes/test_robos.py
from mundo.dominio.robos import EstadoDoRobo, UnidadeMineradora, UnidadeTransportadora


def test_unidade_mineradora_inicia_disponivel():
    unidade = UnidadeMineradora(
        identificador="m1", estado=EstadoDoRobo.DISPONIVEL,
        energia_necessaria=2, desgaste=0.0, localizacao="base", capacidade=50.0,
    )
    assert unidade.estado == EstadoDoRobo.DISPONIVEL


def test_unidade_transportadora_possui_viagens_disponiveis():
    unidade = UnidadeTransportadora(
        identificador="t1", estado=EstadoDoRobo.DISPONIVEL,
        energia_necessaria=3, desgaste=0.0, localizacao="base", capacidade=100.0,
        viagens_disponiveis=5,
    )
    assert unidade.viagens_disponiveis == 5


def test_estado_do_robo_pode_ser_alterado():
    unidade = UnidadeMineradora(
        identificador="m1", estado=EstadoDoRobo.DISPONIVEL,
        energia_necessaria=2, desgaste=0.0, localizacao="base", capacidade=50.0,
    )
    unidade.estado = EstadoDoRobo.EXECUTANDO
    assert unidade.estado == EstadoDoRobo.EXECUTANDO
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_robos.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

```python
# mundo/dominio/robos.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EstadoDoRobo(str, Enum):
    DISPONIVEL = "disponivel"
    EXECUTANDO = "executando"
    AGUARDANDO = "aguardando"
    RETORNANDO = "retornando"
    INDISPONIVEL = "indisponivel"


@dataclass
class Robo:
    identificador: str
    estado: EstadoDoRobo
    energia_necessaria: int
    desgaste: float
    localizacao: str
    capacidade: float


@dataclass
class UnidadeMineradora(Robo):
    pass


@dataclass
class UnidadeTransportadora(Robo):
    viagens_disponiveis: int = 0
```

- [ ] **Step 4: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_robos.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add mundo/dominio/robos.py mundo/testes/test_robos.py
git commit -m "feat: add UnidadeMineradora and UnidadeTransportadora entities"
```

---

### Task 7: Carga Mineral

**Files:**
- Create: `mundo/dominio/cargas.py`
- Test: `mundo/testes/test_cargas.py`

**Interfaces:**
- Produces: `clamp_qualidade(valor) -> float`, `CargaMineral` (dataclass) com `.degradar(taxa_degradacao, fator_contexto=1.0)`, `.valor_efetivo(valor_por_unidade) -> float`.

- [ ] **Step 1: Escrever o teste falhando**

```python
# mundo/testes/test_cargas.py
from mundo.dominio.cargas import CargaMineral, clamp_qualidade


def test_qualidade_e_clamped_ao_criar_acima_de_100():
    carga = CargaMineral(identificador="c1", mineral="hematita", quantidade=10.0, qualidade=150.0)
    assert carga.qualidade == 100.0


def test_qualidade_e_clamped_ao_criar_abaixo_de_0():
    carga = CargaMineral(identificador="c1", mineral="hematita", quantidade=10.0, qualidade=-5.0)
    assert carga.qualidade == 0.0


def test_degradar_reduz_qualidade():
    carga = CargaMineral(identificador="c1", mineral="hematita", quantidade=10.0, qualidade=50.0)
    carga.degradar(taxa_degradacao=10.0)
    assert carga.qualidade == 40.0


def test_degradar_nunca_abaixo_de_zero():
    carga = CargaMineral(identificador="c1", mineral="hematita", quantidade=10.0, qualidade=5.0)
    carga.degradar(taxa_degradacao=50.0)
    assert carga.qualidade == 0.0


def test_valor_efetivo_considera_qualidade():
    carga = CargaMineral(identificador="c1", mineral="hematita", quantidade=10.0, qualidade=50.0)
    assert carga.valor_efetivo(valor_por_unidade=5.0) == 25.0


def test_clamp_qualidade_funcao_isolada():
    assert clamp_qualidade(200) == 100
    assert clamp_qualidade(-10) == 0
    assert clamp_qualidade(42) == 42
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_cargas.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

```python
# mundo/dominio/cargas.py
from __future__ import annotations

from dataclasses import dataclass


def clamp_qualidade(valor: float) -> float:
    return max(0.0, min(100.0, valor))


@dataclass
class CargaMineral:
    identificador: str
    mineral: str
    quantidade: float
    qualidade: float = 100.0

    def __post_init__(self) -> None:
        self.qualidade = clamp_qualidade(self.qualidade)

    def degradar(self, taxa_degradacao: float, fator_contexto: float = 1.0) -> None:
        perda = taxa_degradacao * fator_contexto
        self.qualidade = clamp_qualidade(self.qualidade - perda)

    def valor_efetivo(self, valor_por_unidade: float) -> float:
        return self.quantidade * valor_por_unidade * (self.qualidade / 100)
```

- [ ] **Step 4: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_cargas.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add mundo/dominio/cargas.py mundo/testes/test_cargas.py
git commit -m "feat: add CargaMineral with clamped quality and effective value"
```

---

### Task 8: Armazéns

**Files:**
- Create: `mundo/dominio/armazens.py`
- Test: `mundo/testes/test_armazens.py`

**Interfaces:**
- Produces: `Armazem` (dataclass) com `.reservar_espaco(quantidade)`, `.liberar_espaco(quantidade)`, `.compativel_com(mineral) -> bool`; exceção `CapacidadeExcedidaError`.

- [ ] **Step 1: Escrever o teste falhando**

```python
# mundo/testes/test_armazens.py
import pytest

from mundo.dominio.armazens import Armazem, CapacidadeExcedidaError


def test_reservar_espaco_aumenta_ocupacao():
    armazem = Armazem(identificador="a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    armazem.reservar_espaco(30.0)
    assert armazem.ocupacao == 30.0


def test_reservar_alem_da_capacidade_lanca_erro():
    armazem = Armazem(identificador="a1", capacidade=10.0, localizacao="setor-1", condicoes="normal")
    with pytest.raises(CapacidadeExcedidaError):
        armazem.reservar_espaco(20.0)


def test_liberar_espaco_reduz_ocupacao_sem_ir_negativo():
    armazem = Armazem(identificador="a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    armazem.reservar_espaco(10.0)
    armazem.liberar_espaco(50.0)
    assert armazem.ocupacao == 0.0


def test_compativel_com_vazio_aceita_qualquer_mineral():
    armazem = Armazem(identificador="a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    assert armazem.compativel_com("hematita") is True


def test_compativel_com_lista_restrita():
    armazem = Armazem(
        identificador="a1", capacidade=100.0, localizacao="setor-1", condicoes="normal",
        compatibilidades={"hematita"},
    )
    assert armazem.compativel_com("hematita") is True
    assert armazem.compativel_com("jarosita") is False
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_armazens.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

```python
# mundo/dominio/armazens.py
from __future__ import annotations

from dataclasses import dataclass, field


class CapacidadeExcedidaError(Exception):
    pass


@dataclass
class Armazem:
    identificador: str
    capacidade: float
    localizacao: str
    condicoes: str
    compatibilidades: set[str] = field(default_factory=set)
    ocupacao: float = 0.0

    def reservar_espaco(self, quantidade: float) -> None:
        if self.ocupacao + quantidade > self.capacidade:
            raise CapacidadeExcedidaError(self.identificador)
        self.ocupacao += quantidade

    def liberar_espaco(self, quantidade: float) -> None:
        self.ocupacao = max(0.0, self.ocupacao - quantidade)

    def compativel_com(self, mineral: str) -> bool:
        return not self.compatibilidades or mineral in self.compatibilidades
```

- [ ] **Step 4: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_armazens.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add mundo/dominio/armazens.py mundo/testes/test_armazens.py
git commit -m "feat: add Armazem entity with capacity and compatibility rules"
```

---

### Task 9: Rotas

**Files:**
- Create: `mundo/dominio/rotas.py`
- Test: `mundo/testes/test_rotas.py`

**Interfaces:**
- Produces: `CondicaoDaRota` (Enum: `LIVRE`, `INTERDITADA`), `Rota` (dataclass).

- [ ] **Step 1: Escrever o teste falhando**

```python
# mundo/testes/test_rotas.py
from mundo.dominio.rotas import CondicaoDaRota, Rota


def test_rota_inicia_livre_por_padrao():
    rota = Rota(identificador="r1", origem="setor-1", destino="central-distribuicao",
                 distancia=10.0, tempo_base=5, risco=0.1)
    assert rota.condicao == CondicaoDaRota.LIVRE


def test_rota_pode_ser_interditada():
    rota = Rota(identificador="r1", origem="setor-1", destino="central-distribuicao",
                 distancia=10.0, tempo_base=5, risco=0.1)
    rota.condicao = CondicaoDaRota.INTERDITADA
    assert rota.condicao == CondicaoDaRota.INTERDITADA
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_rotas.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

```python
# mundo/dominio/rotas.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CondicaoDaRota(str, Enum):
    LIVRE = "livre"
    INTERDITADA = "interditada"


@dataclass
class Rota:
    identificador: str
    origem: str
    destino: str
    distancia: float
    tempo_base: int
    risco: float
    condicao: CondicaoDaRota = CondicaoDaRota.LIVRE
```

- [ ] **Step 4: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_rotas.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add mundo/dominio/rotas.py mundo/testes/test_rotas.py
git commit -m "feat: add Rota entity"
```

---

### Task 10: Registro de Autorizações

**Files:**
- Create: `mundo/dominio/autorizacao.py`
- Test: `mundo/testes/test_autorizacao.py`

**Interfaces:**
- Produces: `Autorizacao` (dataclass frozen), `RegistroDeAutorizacoes` com `.emitir(operacao, central_solicitante) -> Autorizacao`, `.consumir(identificador, operacao)`; exceção `AutorizacaoInvalidaError`.

- [ ] **Step 1: Escrever o teste falhando**

```python
# mundo/testes/test_autorizacao.py
import pytest

from mundo.dominio.autorizacao import AutorizacaoInvalidaError, RegistroDeAutorizacoes


def test_emitir_gera_autorizacao_com_identificador():
    registro = RegistroDeAutorizacoes()
    autorizacao = registro.emitir("iniciar_viagem", "missao")
    assert autorizacao.identificador == "aut-1"
    assert autorizacao.operacao == "iniciar_viagem"


def test_consumir_autorizacao_valida_nao_lanca_erro():
    registro = RegistroDeAutorizacoes()
    autorizacao = registro.emitir("iniciar_viagem", "missao")
    registro.consumir(autorizacao.identificador, "iniciar_viagem")


def test_consumir_autorizacao_duas_vezes_lanca_erro():
    registro = RegistroDeAutorizacoes()
    autorizacao = registro.emitir("iniciar_viagem", "missao")
    registro.consumir(autorizacao.identificador, "iniciar_viagem")
    with pytest.raises(AutorizacaoInvalidaError):
        registro.consumir(autorizacao.identificador, "iniciar_viagem")


def test_consumir_com_operacao_errada_lanca_erro():
    registro = RegistroDeAutorizacoes()
    autorizacao = registro.emitir("iniciar_viagem", "missao")
    with pytest.raises(AutorizacaoInvalidaError):
        registro.consumir(autorizacao.identificador, "outra_operacao")


def test_consumir_identificador_inexistente_lanca_erro():
    registro = RegistroDeAutorizacoes()
    with pytest.raises(AutorizacaoInvalidaError):
        registro.consumir("aut-999", "iniciar_viagem")
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_autorizacao.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

```python
# mundo/dominio/autorizacao.py
from __future__ import annotations

import itertools
from dataclasses import dataclass


class AutorizacaoInvalidaError(Exception):
    pass


@dataclass(frozen=True)
class Autorizacao:
    identificador: str
    operacao: str
    central_solicitante: str
    usada: bool = False


class RegistroDeAutorizacoes:
    def __init__(self) -> None:
        self._contador = itertools.count(1)
        self._autorizacoes: dict[str, Autorizacao] = {}

    def emitir(self, operacao: str, central_solicitante: str) -> Autorizacao:
        identificador = f"aut-{next(self._contador)}"
        autorizacao = Autorizacao(identificador, operacao, central_solicitante)
        self._autorizacoes[identificador] = autorizacao
        return autorizacao

    def consumir(self, identificador: str, operacao: str) -> None:
        autorizacao = self._autorizacoes.get(identificador)
        if autorizacao is None or autorizacao.usada or autorizacao.operacao != operacao:
            raise AutorizacaoInvalidaError(identificador)
        self._autorizacoes[identificador] = Autorizacao(
            autorizacao.identificador, autorizacao.operacao, autorizacao.central_solicitante, usada=True,
        )
```

- [ ] **Step 4: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_autorizacao.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add mundo/dominio/autorizacao.py mundo/testes/test_autorizacao.py
git commit -m "feat: add authorization registry enforcing Missão gatekeeping"
```

---

### Task 11: Fila de Comandos

**Files:**
- Create: `mundo/motor/__init__.py`
- Create: `mundo/motor/comandos.py`
- Test: `mundo/testes/test_fila_de_comandos.py`

**Interfaces:**
- Produces: `Comando` (dataclass: `tipo`, `central_origem`, `payload`, `executar: Callable[[], None]`), `FilaDeComandos` com `.enfileirar(comando)`, `.drenar() -> list[Comando]`.

- [ ] **Step 1: Criar `mundo/motor/__init__.py` (vazio)**

- [ ] **Step 2: Escrever o teste falhando**

```python
# mundo/testes/test_fila_de_comandos.py
from mundo.motor.comandos import Comando, FilaDeComandos


def test_drenar_retorna_comandos_na_ordem_de_chegada_e_esvazia_fila():
    fila = FilaDeComandos()
    execucoes = []
    fila.enfileirar(Comando("a", "extracao", {}, lambda: execucoes.append("a")))
    fila.enfileirar(Comando("b", "transporte", {}, lambda: execucoes.append("b")))

    comandos = fila.drenar()

    assert [c.tipo for c in comandos] == ["a", "b"]
    assert fila.drenar() == []
```

- [ ] **Step 3: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_fila_de_comandos.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 4: Implementar**

```python
# mundo/motor/comandos.py
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Comando:
    tipo: str
    central_origem: str
    payload: dict[str, Any]
    executar: Callable[[], None]


class FilaDeComandos:
    def __init__(self) -> None:
        self._fila: deque[Comando] = deque()

    def enfileirar(self, comando: Comando) -> None:
        self._fila.append(comando)

    def drenar(self) -> list[Comando]:
        comandos = list(self._fila)
        self._fila.clear()
        return comandos
```

- [ ] **Step 5: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_fila_de_comandos.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add mundo/motor/__init__.py mundo/motor/comandos.py mundo/testes/test_fila_de_comandos.py
git commit -m "feat: add command queue with deterministic FIFO draining"
```

---

### Task 12: Agenda de Efeitos

**Files:**
- Create: `mundo/motor/efeitos.py`
- Test: `mundo/testes/test_agenda_de_efeitos.py`

**Interfaces:**
- Produces: `AgendaDeEfeitos` com `.agendar(ciclo_alvo, callback)`, `.disparar_ate(ciclo_atual)`.

- [ ] **Step 1: Escrever o teste falhando**

```python
# mundo/testes/test_agenda_de_efeitos.py
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
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_agenda_de_efeitos.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

```python
# mundo/motor/efeitos.py
from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from typing import Callable


@dataclass(order=True)
class _ItemAgenda:
    ciclo_alvo: int
    sequencia: int
    callback: Callable[[], None] = field(compare=False)


class AgendaDeEfeitos:
    def __init__(self) -> None:
        self._heap: list[_ItemAgenda] = []
        self._contador = itertools.count()

    def agendar(self, ciclo_alvo: int, callback: Callable[[], None]) -> None:
        heapq.heappush(self._heap, _ItemAgenda(ciclo_alvo, next(self._contador), callback))

    def disparar_ate(self, ciclo_atual: int) -> None:
        while self._heap and self._heap[0].ciclo_alvo <= ciclo_atual:
            item = heapq.heappop(self._heap)
            item.callback()
```

- [ ] **Step 4: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_agenda_de_efeitos.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add mundo/motor/efeitos.py mundo/testes/test_agenda_de_efeitos.py
git commit -m "feat: add scheduled-effects heap ordered by target cycle"
```

---

### Task 13: Motor de Simulação

**Files:**
- Create: `mundo/motor/motor_de_simulacao.py`
- Test: `mundo/testes/test_motor_de_simulacao.py`

**Interfaces:**
- Consumes: `GerenciadorDeEnergia` (Task 4), `CatalogoDeMinerais`/`Mineral` (Task 2), `EstadoDaJazida`/`Jazida` (Task 5), `EstadoDoRobo`/`UnidadeMineradora`/`UnidadeTransportadora` (Task 6), `CargaMineral` (Task 7), `Armazem` (Task 8), `Rota` (Task 9), `RegistroDeAutorizacoes` (Task 10), `Comando`/`FilaDeComandos` (Task 11), `AgendaDeEfeitos` (Task 12), `BarramentoDeEventos` (Task 3).
- Produces: `ConfiguracaoDaSimulacao(semente, duracao_maxima, energia_total=1000, energia_inicial_por_central=10)`, `MotorDeSimulacao(configuracao, catalogo_de_minerais)` com atributos públicos `ciclo_atual`, `rng`, `energia`, `catalogo_de_minerais`, `jazidas`, `robos`, `armazens`, `rotas`, `cargas`, `fila_de_pesquisa: list[str]`, `faturamento_total: float`, `autorizacoes`, `eventos`; métodos `.enfileirar_comando(comando)`, `.agendar_efeito(ciclo_alvo, callback)`, `.avancar_ciclo(quantidade=1)`.

- [ ] **Step 1: Escrever o teste falhando**

```python
# mundo/testes/test_motor_de_simulacao.py
from pathlib import Path

from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.motor.comandos import Comando
from mundo.motor.motor_de_simulacao import ConfiguracaoDaSimulacao, MotorDeSimulacao

CAMINHO_CATALOGO = Path(__file__).parent.parent / "config" / "minerais.json"


def _criar_motor(semente: int = 1) -> MotorDeSimulacao:
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    return MotorDeSimulacao(ConfiguracaoDaSimulacao(semente=semente, duracao_maxima=50), catalogo)


def test_motor_gera_mundo_inicial_com_entidades():
    motor = _criar_motor()
    assert len(motor.jazidas) == 10  # 5 minerais x 2 jazidas
    assert "mineradora-1" in motor.robos
    assert "transportadora-1" in motor.robos
    assert len(motor.armazens) == 2
    assert len(motor.rotas) == 2


def test_avancar_ciclo_incrementa_contador():
    motor = _criar_motor()
    motor.avancar_ciclo(3)
    assert motor.ciclo_atual == 3


def test_comando_enfileirado_e_aplicado_no_proximo_ciclo():
    motor = _criar_motor()
    executado = []
    motor.enfileirar_comando(Comando("teste", "extracao", {}, lambda: executado.append(True)))
    assert executado == []
    motor.avancar_ciclo(1)
    assert executado == [True]


def test_comando_que_lanca_erro_publica_evento_operacao_invalida():
    motor = _criar_motor()

    def falhar():
        raise ValueError("saldo insuficiente")

    motor.enfileirar_comando(Comando("iniciar_extracao", "extracao", {}, falhar))
    motor.avancar_ciclo(1)

    eventos = motor.eventos.consultar_eventos()
    assert any(e.tipo == "operacao_invalida" for e in eventos)


def test_efeito_agendado_dispara_no_ciclo_alvo():
    motor = _criar_motor()
    disparado = []
    motor.agendar_efeito(motor.ciclo_atual + 3, lambda: disparado.append(True))
    motor.avancar_ciclo(2)
    assert disparado == []
    motor.avancar_ciclo(1)
    assert disparado == [True]
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_motor_de_simulacao.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

```python
# mundo/motor/motor_de_simulacao.py
from __future__ import annotations

import random
from dataclasses import dataclass

from mundo.dominio.armazens import Armazem
from mundo.dominio.autorizacao import RegistroDeAutorizacoes
from mundo.dominio.cargas import CargaMineral
from mundo.dominio.energia import GerenciadorDeEnergia
from mundo.dominio.jazidas import EstadoDaJazida, Jazida
from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.dominio.robos import EstadoDoRobo, Robo, UnidadeMineradora, UnidadeTransportadora
from mundo.dominio.rotas import Rota
from mundo.eventos.barramento import BarramentoDeEventos
from .comandos import FilaDeComandos
from .efeitos import AgendaDeEfeitos

CENTRAIS = ["extracao", "armazenagem", "transporte", "pesquisa", "missao"]


@dataclass
class ConfiguracaoDaSimulacao:
    semente: int
    duracao_maxima: int
    energia_total: int = 1000
    energia_inicial_por_central: int = 10


class MotorDeSimulacao:
    def __init__(self, configuracao: ConfiguracaoDaSimulacao, catalogo_de_minerais: CatalogoDeMinerais) -> None:
        self.configuracao = configuracao
        self.catalogo_de_minerais = catalogo_de_minerais
        self.ciclo_atual = 0
        self.rng = random.Random(configuracao.semente)
        self.energia = GerenciadorDeEnergia(
            CENTRAIS, configuracao.energia_inicial_por_central, configuracao.energia_total,
        )
        self.jazidas: dict[str, Jazida] = {}
        self.robos: dict[str, Robo] = {}
        self.armazens: dict[str, Armazem] = {}
        self.rotas: dict[str, Rota] = {}
        self.cargas: dict[str, CargaMineral] = {}
        self.fila_de_pesquisa: list[str] = []
        self.faturamento_total: float = 0.0
        self.autorizacoes = RegistroDeAutorizacoes()
        self.eventos = BarramentoDeEventos()
        self._fila_de_comandos = FilaDeComandos()
        self._agenda_de_efeitos = AgendaDeEfeitos()
        self._gerar_mundo_inicial()

    def enfileirar_comando(self, comando) -> None:
        self._fila_de_comandos.enfileirar(comando)

    def agendar_efeito(self, ciclo_alvo: int, callback) -> None:
        self._agenda_de_efeitos.agendar(ciclo_alvo, callback)

    def avancar_ciclo(self, quantidade: int = 1) -> None:
        for _ in range(quantidade):
            self._processar_um_ciclo()

    def _processar_um_ciclo(self) -> None:
        self.ciclo_atual += 1
        for comando in self._fila_de_comandos.drenar():
            try:
                comando.executar()
            except Exception as erro:
                self.eventos.publicar(
                    tipo="operacao_invalida",
                    ciclo=self.ciclo_atual,
                    dados={"comando": comando.tipo, "central": comando.central_origem, "motivo": str(erro)},
                )
        self._agenda_de_efeitos.disparar_ate(self.ciclo_atual)

    def _gerar_mundo_inicial(self) -> None:
        contador_jazidas = 1
        for mineral in self.catalogo_de_minerais.todos():
            for _ in range(2):
                identificador = f"jazida-{contador_jazidas}"
                quantidade = self.rng.uniform(50, 200)
                self.jazidas[identificador] = Jazida(
                    identificador=identificador,
                    localizacao=f"setor-{contador_jazidas}",
                    mineral=mineral.nome,
                    quantidade_disponivel=quantidade,
                    dificuldade_extracao=mineral.custo_extracao,
                    risco=self.rng.uniform(0.0, 0.3),
                    estado=EstadoDaJazida.DISPONIVEL,
                )
                contador_jazidas += 1

        for i in range(1, 3):
            self.robos[f"mineradora-{i}"] = UnidadeMineradora(
                identificador=f"mineradora-{i}", estado=EstadoDoRobo.DISPONIVEL,
                energia_necessaria=2, desgaste=0.0, localizacao="base", capacidade=50.0,
            )
        for i in range(1, 3):
            self.robos[f"transportadora-{i}"] = UnidadeTransportadora(
                identificador=f"transportadora-{i}", estado=EstadoDoRobo.DISPONIVEL,
                energia_necessaria=3, desgaste=0.0, localizacao="base", capacidade=100.0,
                viagens_disponiveis=10,
            )

        for i in range(1, 3):
            self.armazens[f"armazem-{i}"] = Armazem(
                identificador=f"armazem-{i}", capacidade=500.0, localizacao=f"setor-{i}", condicoes="normal",
            )

        self.rotas["rota-1"] = Rota(
            identificador="rota-1", origem="setor-1", destino="central-distribuicao",
            distancia=10.0, tempo_base=5, risco=0.05,
        )
        self.rotas["rota-2"] = Rota(
            identificador="rota-2", origem="setor-2", destino="central-distribuicao",
            distancia=15.0, tempo_base=7, risco=0.08,
        )
```

- [ ] **Step 4: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_motor_de_simulacao.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add mundo/motor/motor_de_simulacao.py mundo/testes/test_motor_de_simulacao.py
git commit -m "feat: add MotorDeSimulacao integrating domain, queue, schedule, and RNG"
```

---

### Task 14: Teste de Determinismo

**Files:**
- Test: `mundo/testes/test_determinismo.py`

**Interfaces:**
- Consumes: `MotorDeSimulacao`, `ConfiguracaoDaSimulacao` (Task 13), `Comando` (Task 11), `CatalogoDeMinerais` (Task 2).

- [ ] **Step 1: Escrever o teste (já deve passar, valida invariante crítico da spec)**

```python
# mundo/testes/test_determinismo.py
from pathlib import Path

from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.motor.comandos import Comando
from mundo.motor.motor_de_simulacao import ConfiguracaoDaSimulacao, MotorDeSimulacao

CAMINHO_CATALOGO = Path(__file__).parent.parent / "config" / "minerais.json"


def _criar_motor(semente: int) -> MotorDeSimulacao:
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    return MotorDeSimulacao(ConfiguracaoDaSimulacao(semente=semente, duracao_maxima=50), catalogo)


def _executar_cenario(motor: MotorDeSimulacao) -> None:
    motor.energia.alocar_energia("reserva_estrategica", "extracao", 20)
    jazida_id = next(iter(motor.jazidas))

    def executar() -> None:
        jazida = motor.jazidas[jazida_id]
        motor.energia.debitar("extracao", 2)
        motor.agendar_efeito(motor.ciclo_atual + 3, lambda: jazida.extrair(10))

    motor.enfileirar_comando(Comando("iniciar_extracao", "extracao", {}, executar))
    motor.avancar_ciclo(10)


def test_mesma_semente_e_mesmas_acoes_produzem_mesmo_estado_final():
    motor_a = _criar_motor(semente=48291)
    motor_b = _criar_motor(semente=48291)

    _executar_cenario(motor_a)
    _executar_cenario(motor_b)

    assert motor_a.ciclo_atual == motor_b.ciclo_atual
    assert [j.quantidade_disponivel for j in motor_a.jazidas.values()] == [
        j.quantidade_disponivel for j in motor_b.jazidas.values()
    ]

    eventos_a = [(e.tipo, e.ciclo, e.dados) for e in motor_a.eventos.consultar_eventos()]
    eventos_b = [(e.tipo, e.ciclo, e.dados) for e in motor_b.eventos.consultar_eventos()]
    assert eventos_a == eventos_b


def test_sementes_diferentes_geram_jazidas_iniciais_diferentes():
    motor_a = _criar_motor(semente=1)
    motor_b = _criar_motor(semente=2)

    quantidades_a = [j.quantidade_disponivel for j in motor_a.jazidas.values()]
    quantidades_b = [j.quantidade_disponivel for j in motor_b.jazidas.values()]

    assert quantidades_a != quantidades_b
```

- [ ] **Step 2: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_determinismo.py -v`
Expected: PASS (2 passed)

- [ ] **Step 3: Commit**

```bash
git add mundo/testes/test_determinismo.py
git commit -m "test: verify same-seed-same-actions determinism (SPEC_INICIAL §37)"
```

---

### Task 15: Dispatcher de Webhooks

**Files:**
- Create: `mundo/eventos/webhooks.py`
- Test: `mundo/testes/test_webhooks.py`

**Interfaces:**
- Consumes: `Evento` (Task 3).
- Produces: `DispatcherDeWebhooks` com `.registrar(url)`, `.notificar(evento)` (assinável no `BarramentoDeEventos`).

- [ ] **Step 1: Escrever o teste falhando**

```python
# mundo/testes/test_webhooks.py
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
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_webhooks.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

```python
# mundo/eventos/webhooks.py
from __future__ import annotations

import asyncio
import logging

from .evento import Evento

logger = logging.getLogger(__name__)


class DispatcherDeWebhooks:
    def __init__(self) -> None:
        self._urls: set[str] = set()

    def registrar(self, url: str) -> None:
        self._urls.add(url)

    def urls_registradas(self) -> set[str]:
        return set(self._urls)

    def notificar(self, evento: Evento) -> None:
        for url in self._urls:
            asyncio.create_task(self._enviar(url, evento))

    async def _enviar(self, url: str, evento: Evento) -> None:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=2.0) as cliente:
                await cliente.post(url, json={
                    "identificador": evento.identificador,
                    "tipo": evento.tipo,
                    "ciclo": evento.ciclo,
                    "dados": evento.dados,
                })
        except httpx.HTTPError:
            logger.warning("Falha ao entregar webhook para %s (evento %s)", url, evento.identificador)
```

- [ ] **Step 4: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_webhooks.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add mundo/eventos/webhooks.py mundo/testes/test_webhooks.py
git commit -m "feat: add fire-and-forget webhook dispatcher"
```

---

### Task 16: API — app factory, ciclo de vida e instância do Mundo

**Files:**
- Create: `mundo/api/__init__.py`
- Create: `mundo/api/dependencias.py`
- Create: `mundo/api/app.py`
- Test: `mundo/testes/test_app.py`

**Interfaces:**
- Consumes: `MotorDeSimulacao`, `ConfiguracaoDaSimulacao` (Task 13), `CatalogoDeMinerais` (Task 2).
- Produces: `instancia_do_mundo: InstanciaDoMundo` (singleton do módulo) com `.inicializar(configuracao, catalogo)`, `.obter_motor() -> MotorDeSimulacao`; função `obter_motor()`; `criar_app() -> FastAPI`; `app` (instância FastAPI pronta).

- [ ] **Step 1: Criar `mundo/api/__init__.py` (vazio)**

- [ ] **Step 2: Escrever o teste falhando**

```python
# mundo/testes/test_app.py
from fastapi.testclient import TestClient

from mundo.api.app import criar_app


def test_app_inicializa_mundo_no_startup_e_expoe_estado():
    app = criar_app()
    with TestClient(app) as cliente:
        resposta = cliente.get("/missao/estado")
        assert resposta.status_code == 200
        assert resposta.json()["ciclo_atual"] == 0
```

- [ ] **Step 3: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_app.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 4: Implementar `mundo/api/dependencias.py`**

```python
# mundo/api/dependencias.py
from __future__ import annotations

from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.motor.motor_de_simulacao import ConfiguracaoDaSimulacao, MotorDeSimulacao


class InstanciaDoMundo:
    def __init__(self) -> None:
        self.motor: MotorDeSimulacao | None = None

    def inicializar(self, configuracao: ConfiguracaoDaSimulacao, catalogo: CatalogoDeMinerais) -> None:
        self.motor = MotorDeSimulacao(configuracao, catalogo)

    def obter_motor(self) -> MotorDeSimulacao:
        if self.motor is None:
            raise RuntimeError("Mundo não inicializado")
        return self.motor


instancia_do_mundo = InstanciaDoMundo()


def obter_motor() -> MotorDeSimulacao:
    return instancia_do_mundo.obter_motor()
```

- [ ] **Step 5: Implementar `mundo/api/app.py` (routers dos Steps seguintes ainda não existem — criados nas Tasks 17-20; por ora registrar só o de missão, criado nesta mesma task em `mundo/api/missao.py` mínimo)**

```python
# mundo/api/app.py
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.motor.motor_de_simulacao import ConfiguracaoDaSimulacao
from .dependencias import instancia_do_mundo

INTERVALO_DE_CICLO_SEGUNDOS = 1.0
CAMINHO_CATALOGO_PADRAO = Path(__file__).parent.parent / "config" / "minerais.json"


async def _loop_real_time() -> None:
    while True:
        await asyncio.sleep(INTERVALO_DE_CICLO_SEGUNDOS)
        if instancia_do_mundo.motor is not None:
            instancia_do_mundo.motor.avancar_ciclo()


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO_PADRAO)
    instancia_do_mundo.inicializar(ConfiguracaoDaSimulacao(semente=0, duracao_maxima=5000), catalogo)
    tarefa = asyncio.create_task(_loop_real_time())
    yield
    tarefa.cancel()


def criar_app() -> FastAPI:
    from . import missao

    app = FastAPI(title="Mundo — Operação Marciana", lifespan=ciclo_de_vida)
    app.include_router(missao.router)
    return app


app = criar_app()
```

- [ ] **Step 6: Implementar router mínimo `mundo/api/missao.py` (expandido na Task 17)**

```python
# mundo/api/missao.py
from __future__ import annotations

from fastapi import APIRouter

from .dependencias import obter_motor

router = APIRouter(prefix="/missao", tags=["missao"])


@router.get("/estado")
def consultar_estado_global() -> dict:
    motor = obter_motor()
    return {"ciclo_atual": motor.ciclo_atual}
```

- [ ] **Step 7: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_app.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add mundo/api/__init__.py mundo/api/dependencias.py mundo/api/app.py mundo/api/missao.py mundo/testes/test_app.py
git commit -m "feat: add FastAPI app factory with hybrid real-time/manual tick loop"
```

---

### Task 17: API — Router da Central de Missão (completo)

**Files:**
- Modify: `mundo/api/missao.py`
- Test: `mundo/testes/test_api_missao.py`

**Interfaces:**
- Consumes: `obter_motor`, `instancia_do_mundo` (Task 16), `GerenciadorDeEnergia.RESERVA` (Task 4), `CatalogoDeMinerais` (Task 2), `ConfiguracaoDaSimulacao` (Task 13).
- Produces: endpoints `POST /missao/resetar-mundo`, `GET /missao/estado`, `GET /missao/eventos`, `POST /missao/alocar-energia`, `POST /missao/autorizar-missao`, `POST /missao/registrar-webhook`.

- [ ] **Step 1: Escrever o teste falhando**

```python
# mundo/testes/test_api_missao.py
from fastapi.testclient import TestClient

from mundo.api.app import criar_app


def test_resetar_mundo_reinicia_ciclo_para_zero():
    app = criar_app()
    with TestClient(app) as cliente:
        cliente.post("/missao/resetar-mundo", json={"semente": 7, "duracao_maxima": 100})
        resposta = cliente.get("/missao/estado")
        assert resposta.json()["ciclo_atual"] == 0


def test_alocar_energia_da_reserva_para_extracao():
    app = criar_app()
    with TestClient(app) as cliente:
        resposta = cliente.post("/missao/alocar-energia", json={"destino": "extracao", "quantidade": 20})
        assert resposta.status_code == 200
        assert resposta.json()["saldo"] == 30


def test_autorizar_missao_emite_id_autorizacao():
    app = criar_app()
    with TestClient(app) as cliente:
        resposta = cliente.post(
            "/missao/autorizar-missao",
            json={"operacao": "iniciar_viagem", "central_solicitante": "transporte"},
        )
        assert resposta.status_code == 200
        assert resposta.json()["id_autorizacao"].startswith("aut-")


def test_consultar_eventos_retorna_lista_vazia_inicialmente():
    app = criar_app()
    with TestClient(app) as cliente:
        resposta = cliente.get("/missao/eventos")
        assert resposta.json() == []
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_api_missao.py -v`
Expected: FAIL (rotas ainda não existem, 404)

- [ ] **Step 3: Implementar**

```python
# mundo/api/missao.py
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mundo.dominio.energia import GerenciadorDeEnergia
from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.motor.motor_de_simulacao import ConfiguracaoDaSimulacao

from .dependencias import instancia_do_mundo, obter_motor

router = APIRouter(prefix="/missao", tags=["missao"])
CAMINHO_CATALOGO = Path(__file__).parent.parent / "config" / "minerais.json"


class RequisicaoDeResetarMundo(BaseModel):
    semente: int
    duracao_maxima: int


@router.post("/resetar-mundo")
def resetar_mundo(requisicao: RequisicaoDeResetarMundo) -> dict:
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    instancia_do_mundo.inicializar(
        ConfiguracaoDaSimulacao(semente=requisicao.semente, duracao_maxima=requisicao.duracao_maxima), catalogo,
    )
    return {"ciclo_atual": 0}


@router.get("/estado")
def consultar_estado_global() -> dict:
    motor = obter_motor()
    centrais = ["extracao", "armazenagem", "transporte", "pesquisa", "missao", GerenciadorDeEnergia.RESERVA]
    return {
        "ciclo_atual": motor.ciclo_atual,
        "energia": {central: motor.energia.consultar_energia(central) for central in centrais},
        "faturamento_total": motor.faturamento_total,
    }


@router.get("/eventos")
def consultar_eventos(desde_ciclo: int = 0) -> list[dict]:
    motor = obter_motor()
    return [
        {"identificador": e.identificador, "tipo": e.tipo, "ciclo": e.ciclo, "dados": e.dados}
        for e in motor.eventos.consultar_eventos(desde_ciclo)
    ]


class RequisicaoDeAlocacao(BaseModel):
    destino: str
    quantidade: int


@router.post("/alocar-energia")
def alocar_energia(requisicao: RequisicaoDeAlocacao) -> dict:
    motor = obter_motor()
    try:
        motor.energia.alocar_energia(GerenciadorDeEnergia.RESERVA, requisicao.destino, requisicao.quantidade)
    except Exception as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    return {"saldo": motor.energia.consultar_energia(requisicao.destino)}


class RequisicaoDeAutorizacao(BaseModel):
    operacao: str
    central_solicitante: str


@router.post("/autorizar-missao")
def autorizar_missao(requisicao: RequisicaoDeAutorizacao) -> dict:
    motor = obter_motor()
    autorizacao = motor.autorizacoes.emitir(requisicao.operacao, requisicao.central_solicitante)
    return {"id_autorizacao": autorizacao.identificador}


class RequisicaoDeWebhook(BaseModel):
    url: str


@router.post("/registrar-webhook")
def registrar_webhook(requisicao: RequisicaoDeWebhook) -> dict:
    motor = obter_motor()
    from mundo.eventos.webhooks import DispatcherDeWebhooks

    if not hasattr(motor, "_dispatcher_de_webhooks"):
        motor._dispatcher_de_webhooks = DispatcherDeWebhooks()
        motor.eventos.assinar(motor._dispatcher_de_webhooks.notificar)
    motor._dispatcher_de_webhooks.registrar(requisicao.url)
    return {"registrado": True}
```

- [ ] **Step 4: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_api_missao.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add mundo/api/missao.py mundo/testes/test_api_missao.py
git commit -m "feat: complete Central de Missão router — state, events, energy, authorization, webhooks"
```

---

### Task 18: API — Router da Central de Extração

**Files:**
- Create: `mundo/api/extracao.py`
- Modify: `mundo/api/app.py` (registrar novo router)
- Test: `mundo/testes/test_api_extracao.py`

**Interfaces:**
- Consumes: `obter_motor` (Task 16), `Comando` (Task 11), `EstadoDaJazida` (Task 5), `EstadoDoRobo` (Task 6).
- Produces: endpoints `GET /extracao/jazidas`, `GET /extracao/jazidas/{id}`, `POST /extracao/iniciar-extracao`, `POST /extracao/interromper-extracao`, `POST /extracao/retornar-unidade`.

- [ ] **Step 1: Escrever o teste falhando**

```python
# mundo/testes/test_api_extracao.py
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo


def test_consultar_jazidas_retorna_dez_jazidas():
    app = criar_app()
    with TestClient(app) as cliente:
        resposta = cliente.get("/extracao/jazidas")
        assert resposta.status_code == 200
        assert len(resposta.json()) == 10


def test_iniciar_extracao_e_aceita_e_processada_no_proximo_ciclo():
    app = criar_app()
    with TestClient(app) as cliente:
        jazidas = cliente.get("/extracao/jazidas").json()
        jazida_id = jazidas[0]["identificador"]

        resposta = cliente.post(
            "/extracao/iniciar-extracao",
            json={
                "identificador_da_unidade": "mineradora-1",
                "identificador_da_jazida": jazida_id,
                "quantidade": 10.0,
            },
        )
        assert resposta.status_code == 200
        assert resposta.json()["aceito"] is True

        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 20)
        motor.avancar_ciclo(1)
        assert motor.robos["mineradora-1"].estado.value == "executando"
        motor.avancar_ciclo(5)
        assert motor.robos["mineradora-1"].estado.value == "aguardando"


def test_inspecionar_jazida_inexistente_retorna_404():
    app = criar_app()
    with TestClient(app) as cliente:
        resposta = cliente.get("/extracao/jazidas/inexistente")
        assert resposta.status_code == 404
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_api_extracao.py -v`
Expected: FAIL com 404 (router não registrado)

- [ ] **Step 3: Implementar `mundo/api/extracao.py`**

```python
# mundo/api/extracao.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mundo.dominio.jazidas import EstadoDaJazida
from mundo.dominio.robos import EstadoDoRobo
from mundo.motor.comandos import Comando

from .dependencias import obter_motor

router = APIRouter(prefix="/extracao", tags=["extracao"])
CENTRAL = "extracao"
DURACAO_EXTRACAO_EM_CICLOS = 5
CUSTO_ENERGETICO_EXTRACAO = 2


@router.get("/jazidas")
def consultar_jazidas() -> list[dict]:
    motor = obter_motor()
    return [
        {"identificador": j.identificador, "mineral": j.mineral, "estado": j.estado.value,
         "quantidade_disponivel": j.quantidade_disponivel}
        for j in motor.jazidas.values()
    ]


@router.get("/jazidas/{identificador}")
def inspecionar_jazida(identificador: str) -> dict:
    motor = obter_motor()
    jazida = motor.jazidas.get(identificador)
    if jazida is None:
        raise HTTPException(status_code=404, detail="Jazida não encontrada")
    return {
        "identificador": jazida.identificador, "localizacao": jazida.localizacao, "mineral": jazida.mineral,
        "quantidade_disponivel": jazida.quantidade_disponivel, "dificuldade_extracao": jazida.dificuldade_extracao,
        "risco": jazida.risco, "estado": jazida.estado.value,
    }


class RequisicaoDeExtracao(BaseModel):
    identificador_da_unidade: str
    identificador_da_jazida: str
    quantidade: float


@router.post("/iniciar-extracao")
def iniciar_extracao(requisicao: RequisicaoDeExtracao) -> dict:
    motor = obter_motor()
    unidade = motor.robos.get(requisicao.identificador_da_unidade)
    jazida = motor.jazidas.get(requisicao.identificador_da_jazida)
    if unidade is None or jazida is None:
        raise HTTPException(status_code=404, detail="Unidade ou jazida não encontrada")

    def executar() -> None:
        if unidade.estado != EstadoDoRobo.DISPONIVEL:
            raise ValueError("Unidade indisponível")
        if jazida.estado != EstadoDaJazida.DISPONIVEL:
            raise ValueError("Jazida não disponível")
        motor.energia.debitar(CENTRAL, CUSTO_ENERGETICO_EXTRACAO)
        unidade.estado = EstadoDoRobo.EXECUTANDO
        ciclo_conclusao = motor.ciclo_atual + DURACAO_EXTRACAO_EM_CICLOS

        def concluir() -> None:
            jazida.extrair(requisicao.quantidade)
            unidade.estado = EstadoDoRobo.AGUARDANDO
            motor.eventos.publicar("extracao_concluida", motor.ciclo_atual, {
                "unidade": unidade.identificador, "jazida": jazida.identificador, "quantidade": requisicao.quantidade,
            })

        motor.agendar_efeito(ciclo_conclusao, concluir)

    motor.enfileirar_comando(Comando("iniciar_extracao", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeUnidade(BaseModel):
    identificador_da_unidade: str


@router.post("/interromper-extracao")
def interromper_extracao(requisicao: RequisicaoDeUnidade) -> dict:
    motor = obter_motor()
    unidade = motor.robos.get(requisicao.identificador_da_unidade)
    if unidade is None:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")

    def executar() -> None:
        unidade.estado = EstadoDoRobo.RETORNANDO

    motor.enfileirar_comando(Comando("interromper_extracao", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


@router.post("/retornar-unidade")
def retornar_unidade(requisicao: RequisicaoDeUnidade) -> dict:
    motor = obter_motor()
    unidade = motor.robos.get(requisicao.identificador_da_unidade)
    if unidade is None:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")

    def executar() -> None:
        unidade.estado = EstadoDoRobo.DISPONIVEL

    motor.enfileirar_comando(Comando("retornar_unidade", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}
```

- [ ] **Step 4: Registrar o router em `mundo/api/app.py`**

```python
# mundo/api/app.py — dentro de criar_app(), após o import de missao
def criar_app() -> FastAPI:
    from . import extracao, missao

    app = FastAPI(title="Mundo — Operação Marciana", lifespan=ciclo_de_vida)
    app.include_router(missao.router)
    app.include_router(extracao.router)
    return app
```

- [ ] **Step 5: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_api_extracao.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add mundo/api/extracao.py mundo/api/app.py mundo/testes/test_api_extracao.py
git commit -m "feat: add Central de Extração router"
```

---

### Task 19: API — Router da Central de Armazenagem

**Files:**
- Create: `mundo/api/armazenagem.py`
- Modify: `mundo/api/app.py` (registrar novo router)
- Test: `mundo/testes/test_api_armazenagem.py`

**Interfaces:**
- Consumes: `obter_motor` (Task 16), `Comando` (Task 11), `CargaMineral` (Task 7).
- Produces: endpoints `GET /armazenagem/armazens`, `POST /armazenagem/reservar-espaco`, `POST /armazenagem/receber-carga`, `POST /armazenagem/realocar-carga`, `POST /armazenagem/liberar-carga`, `POST /armazenagem/descartar-carga`, `POST /armazenagem/solicitar-transporte`.

- [ ] **Step 1: Escrever o teste falhando**

```python
# mundo/testes/test_api_armazenagem.py
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo


def test_consultar_armazens_retorna_dois_armazens():
    app = criar_app()
    with TestClient(app) as cliente:
        resposta = cliente.get("/armazenagem/armazens")
        assert len(resposta.json()) == 2


def test_receber_carga_ocupa_espaco_no_armazem():
    app = criar_app()
    with TestClient(app) as cliente:
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1", "identificador_da_carga": "carga-1",
            "mineral": "hematita", "quantidade": 20.0, "qualidade": 90.0,
        })
        motor = instancia_do_mundo.obter_motor()
        motor.avancar_ciclo(1)
        assert motor.armazens["armazem-1"].ocupacao == 20.0
        assert "carga-1" in motor.cargas


def test_solicitar_transporte_exige_autorizacao_valida():
    app = criar_app()
    with TestClient(app) as cliente:
        resposta = cliente.post("/missao/autorizar-missao", json={
            "operacao": "solicitar_transporte", "central_solicitante": "armazenagem",
        })
        id_autorizacao = resposta.json()["id_autorizacao"]

        cliente.post("/armazenagem/solicitar-transporte", json={
            "identificador_da_carga": "carga-1", "id_autorizacao": id_autorizacao,
        })
        motor = instancia_do_mundo.obter_motor()
        motor.avancar_ciclo(1)
        assert any(e.tipo == "carga_disponivel" for e in motor.eventos.consultar_eventos())
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_api_armazenagem.py -v`
Expected: FAIL com 404

- [ ] **Step 3: Implementar `mundo/api/armazenagem.py`**

```python
# mundo/api/armazenagem.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mundo.dominio.cargas import CargaMineral
from mundo.motor.comandos import Comando

from .dependencias import obter_motor

router = APIRouter(prefix="/armazenagem", tags=["armazenagem"])
CENTRAL = "armazenagem"
CUSTO_ENERGETICO_OPERACAO = 1


@router.get("/armazens")
def consultar_armazens() -> list[dict]:
    motor = obter_motor()
    return [
        {"identificador": a.identificador, "capacidade": a.capacidade, "ocupacao": a.ocupacao,
         "localizacao": a.localizacao, "condicoes": a.condicoes}
        for a in motor.armazens.values()
    ]


class RequisicaoDeReserva(BaseModel):
    identificador_do_armazem: str
    quantidade: float


@router.post("/reservar-espaco")
def reservar_espaco(requisicao: RequisicaoDeReserva) -> dict:
    motor = obter_motor()
    armazem = motor.armazens.get(requisicao.identificador_do_armazem)
    if armazem is None:
        raise HTTPException(status_code=404, detail="Armazém não encontrado")

    def executar() -> None:
        motor.energia.debitar(CENTRAL, CUSTO_ENERGETICO_OPERACAO)
        armazem.reservar_espaco(requisicao.quantidade)

    motor.enfileirar_comando(Comando("reservar_espaco", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeRecebimento(BaseModel):
    identificador_do_armazem: str
    identificador_da_carga: str
    mineral: str
    quantidade: float
    qualidade: float


@router.post("/receber-carga")
def receber_carga(requisicao: RequisicaoDeRecebimento) -> dict:
    motor = obter_motor()
    armazem = motor.armazens.get(requisicao.identificador_do_armazem)
    if armazem is None:
        raise HTTPException(status_code=404, detail="Armazém não encontrado")

    def executar() -> None:
        if not armazem.compativel_com(requisicao.mineral):
            motor.eventos.publicar("carga_contaminada", motor.ciclo_atual, {
                "carga": requisicao.identificador_da_carga, "armazem": armazem.identificador,
            })
            raise ValueError("Mineral incompatível com o armazém")
        motor.energia.debitar(CENTRAL, CUSTO_ENERGETICO_OPERACAO)
        armazem.reservar_espaco(requisicao.quantidade)
        motor.cargas[requisicao.identificador_da_carga] = CargaMineral(
            requisicao.identificador_da_carga, requisicao.mineral, requisicao.quantidade, requisicao.qualidade,
        )
        if armazem.ocupacao >= armazem.capacidade:
            motor.eventos.publicar("armazem_lotado", motor.ciclo_atual, {"armazem": armazem.identificador})
        elif armazem.ocupacao >= armazem.capacidade * 0.9:
            motor.eventos.publicar(
                "armazem_proximo_da_capacidade", motor.ciclo_atual, {"armazem": armazem.identificador},
            )

    motor.enfileirar_comando(Comando("receber_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeRealocacao(BaseModel):
    identificador_da_carga: str
    identificador_do_armazem_origem: str
    identificador_do_armazem_destino: str


@router.post("/realocar-carga")
def realocar_carga(requisicao: RequisicaoDeRealocacao) -> dict:
    motor = obter_motor()

    def executar() -> None:
        origem = motor.armazens[requisicao.identificador_do_armazem_origem]
        destino = motor.armazens[requisicao.identificador_do_armazem_destino]
        carga = motor.cargas[requisicao.identificador_da_carga]
        destino.reservar_espaco(carga.quantidade)
        origem.liberar_espaco(carga.quantidade)

    motor.enfileirar_comando(Comando("realocar_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeLiberacao(BaseModel):
    identificador_do_armazem: str
    quantidade: float


@router.post("/liberar-carga")
def liberar_carga(requisicao: RequisicaoDeLiberacao) -> dict:
    motor = obter_motor()

    def executar() -> None:
        motor.armazens[requisicao.identificador_do_armazem].liberar_espaco(requisicao.quantidade)

    motor.enfileirar_comando(Comando("liberar_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeDescarte(BaseModel):
    identificador_da_carga: str
    identificador_do_armazem: str


@router.post("/descartar-carga")
def descartar_carga(requisicao: RequisicaoDeDescarte) -> dict:
    motor = obter_motor()

    def executar() -> None:
        carga = motor.cargas.pop(requisicao.identificador_da_carga)
        motor.armazens[requisicao.identificador_do_armazem].liberar_espaco(carga.quantidade)
        motor.eventos.publicar("carga_descartada", motor.ciclo_atual, {"carga": carga.identificador})

    motor.enfileirar_comando(Comando("descartar_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeSolicitacaoDeTransporte(BaseModel):
    identificador_da_carga: str
    id_autorizacao: str


@router.post("/solicitar-transporte")
def solicitar_transporte(requisicao: RequisicaoDeSolicitacaoDeTransporte) -> dict:
    motor = obter_motor()

    def executar() -> None:
        motor.autorizacoes.consumir(requisicao.id_autorizacao, "solicitar_transporte")
        motor.eventos.publicar("carga_disponivel", motor.ciclo_atual, {"carga": requisicao.identificador_da_carga})

    motor.enfileirar_comando(Comando("solicitar_transporte", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}
```

- [ ] **Step 4: Registrar o router em `mundo/api/app.py`**

```python
# mundo/api/app.py — dentro de criar_app()
def criar_app() -> FastAPI:
    from . import armazenagem, extracao, missao

    app = FastAPI(title="Mundo — Operação Marciana", lifespan=ciclo_de_vida)
    app.include_router(missao.router)
    app.include_router(extracao.router)
    app.include_router(armazenagem.router)
    return app
```

- [ ] **Step 5: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_api_armazenagem.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add mundo/api/armazenagem.py mundo/api/app.py mundo/testes/test_api_armazenagem.py
git commit -m "feat: add Central de Armazenagem router with authorization-gated transport request"
```

---

### Task 20: API — Router da Central de Transporte

**Files:**
- Create: `mundo/api/transporte.py`
- Modify: `mundo/api/app.py` (registrar novo router)
- Test: `mundo/testes/test_api_transporte.py`

**Interfaces:**
- Consumes: `obter_motor` (Task 16), `Comando` (Task 11), `EstadoDoRobo` (Task 6), `CondicaoDaRota` (Task 9).
- Produces: endpoints `GET /transporte/rotas`, `GET /transporte/transportadores`, `GET /transporte/cargas-disponiveis`, `GET /transporte/planejar-transporte`, `POST /transporte/carregar`, `POST /transporte/iniciar-viagem`, `POST /transporte/abortar-viagem`, `POST /transporte/descarregar`, `POST /transporte/retornar-unidade`.

- [ ] **Step 1: Escrever o teste falhando**

```python
# mundo/testes/test_api_transporte.py
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.cargas import CargaMineral


def test_consultar_rotas_retorna_duas_rotas():
    app = criar_app()
    with TestClient(app) as cliente:
        resposta = cliente.get("/transporte/rotas")
        assert len(resposta.json()) == 2


def test_iniciar_viagem_exige_autorizacao_e_debita_viagem_disponivel():
    app = criar_app()
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)
        motor.energia.alocar_energia("reserva_estrategica", "transporte", 20)

        resposta_autorizacao = cliente.post("/missao/autorizar-missao", json={
            "operacao": "iniciar_viagem", "central_solicitante": "transporte",
        })
        id_autorizacao = resposta_autorizacao.json()["id_autorizacao"]

        cliente.post("/transporte/iniciar-viagem", json={
            "identificador_da_unidade": "transportadora-1", "identificador_da_rota": "rota-1",
            "identificador_da_carga": "carga-1", "id_autorizacao": id_autorizacao,
        })
        motor.avancar_ciclo(1)
        assert motor.robos["transportadora-1"].viagens_disponiveis == 9
        assert motor.robos["transportadora-1"].estado.value == "executando"


def test_iniciar_viagem_sem_autorizacao_valida_gera_operacao_invalida():
    app = criar_app()
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)

        cliente.post("/transporte/iniciar-viagem", json={
            "identificador_da_unidade": "transportadora-1", "identificador_da_rota": "rota-1",
            "identificador_da_carga": "carga-1", "id_autorizacao": "aut-inexistente",
        })
        motor.avancar_ciclo(1)
        assert any(e.tipo == "operacao_invalida" for e in motor.eventos.consultar_eventos())
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_api_transporte.py -v`
Expected: FAIL com 404

- [ ] **Step 3: Implementar `mundo/api/transporte.py`**

```python
# mundo/api/transporte.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mundo.dominio.robos import EstadoDoRobo
from mundo.dominio.rotas import CondicaoDaRota
from mundo.motor.comandos import Comando

from .dependencias import obter_motor

router = APIRouter(prefix="/transporte", tags=["transporte"])
CENTRAL = "transporte"
CUSTO_ENERGETICO_VIAGEM = 3


@router.get("/rotas")
def consultar_rotas() -> list[dict]:
    motor = obter_motor()
    return [
        {"identificador": r.identificador, "origem": r.origem, "destino": r.destino,
         "distancia": r.distancia, "condicao": r.condicao.value}
        for r in motor.rotas.values()
    ]


@router.get("/transportadores")
def consultar_transportadores() -> list[dict]:
    motor = obter_motor()
    return [
        {"identificador": robo.identificador, "estado": robo.estado.value, "localizacao": robo.localizacao}
        for robo in motor.robos.values() if hasattr(robo, "viagens_disponiveis")
    ]


@router.get("/cargas-disponiveis")
def consultar_cargas_disponiveis() -> list[dict]:
    motor = obter_motor()
    return [
        {"identificador": c.identificador, "mineral": c.mineral, "quantidade": c.quantidade, "qualidade": c.qualidade}
        for c in motor.cargas.values()
    ]


@router.get("/planejar-transporte")
def planejar_transporte(identificador_da_carga: str) -> dict:
    motor = obter_motor()
    carga = motor.cargas.get(identificador_da_carga)
    if carga is None:
        raise HTTPException(status_code=404, detail="Carga não encontrada")
    rotas_livres = [r.identificador for r in motor.rotas.values() if r.condicao == CondicaoDaRota.LIVRE]
    return {"carga": carga.identificador, "rotas_disponiveis": rotas_livres}


class RequisicaoDeCarregamento(BaseModel):
    identificador_da_unidade: str
    identificador_da_carga: str


@router.post("/carregar")
def carregar(requisicao: RequisicaoDeCarregamento) -> dict:
    motor = obter_motor()
    unidade = motor.robos.get(requisicao.identificador_da_unidade)
    if unidade is None:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")

    def executar() -> None:
        if unidade.estado != EstadoDoRobo.DISPONIVEL:
            raise ValueError("Unidade indisponível")
        carga = motor.cargas[requisicao.identificador_da_carga]
        if carga.quantidade > unidade.capacidade:
            raise ValueError("Capacidade da unidade excedida")
        unidade.estado = EstadoDoRobo.AGUARDANDO

    motor.enfileirar_comando(Comando("carregar", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeViagem(BaseModel):
    identificador_da_unidade: str
    identificador_da_rota: str
    identificador_da_carga: str
    id_autorizacao: str


@router.post("/iniciar-viagem")
def iniciar_viagem(requisicao: RequisicaoDeViagem) -> dict:
    motor = obter_motor()
    unidade = motor.robos.get(requisicao.identificador_da_unidade)
    rota = motor.rotas.get(requisicao.identificador_da_rota)
    if unidade is None or rota is None:
        raise HTTPException(status_code=404, detail="Unidade ou rota não encontrada")

    def executar() -> None:
        motor.autorizacoes.consumir(requisicao.id_autorizacao, "iniciar_viagem")
        if rota.condicao != CondicaoDaRota.LIVRE:
            raise ValueError("Rota interditada")
        if unidade.viagens_disponiveis <= 0:
            raise ValueError("Sem viagens disponíveis")
        motor.energia.debitar(CENTRAL, CUSTO_ENERGETICO_VIAGEM)
        unidade.viagens_disponiveis -= 1
        unidade.estado = EstadoDoRobo.EXECUTANDO
        ciclo_chegada = motor.ciclo_atual + rota.tempo_base

        def concluir() -> None:
            carga = motor.cargas[requisicao.identificador_da_carga]
            carga.degradar(taxa_degradacao=rota.risco, fator_contexto=1.0)
            unidade.estado = EstadoDoRobo.RETORNANDO
            motor.eventos.publicar("transporte_concluido", motor.ciclo_atual, {
                "unidade": unidade.identificador, "carga": carga.identificador,
            })

        motor.agendar_efeito(ciclo_chegada, concluir)

    motor.enfileirar_comando(Comando("iniciar_viagem", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeUnidade(BaseModel):
    identificador_da_unidade: str


@router.post("/abortar-viagem")
def abortar_viagem(requisicao: RequisicaoDeUnidade) -> dict:
    motor = obter_motor()
    unidade = motor.robos.get(requisicao.identificador_da_unidade)
    if unidade is None:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")

    def executar() -> None:
        unidade.estado = EstadoDoRobo.RETORNANDO

    motor.enfileirar_comando(Comando("abortar_viagem", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


@router.post("/descarregar")
def descarregar(requisicao: RequisicaoDeCarregamento) -> dict:
    motor = obter_motor()

    def executar() -> None:
        motor.eventos.publicar("carga_disponivel", motor.ciclo_atual, {"carga": requisicao.identificador_da_carga})

    motor.enfileirar_comando(Comando("descarregar", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


@router.post("/retornar-unidade")
def retornar_unidade(requisicao: RequisicaoDeUnidade) -> dict:
    motor = obter_motor()
    unidade = motor.robos.get(requisicao.identificador_da_unidade)
    if unidade is None:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")

    def executar() -> None:
        unidade.estado = EstadoDoRobo.DISPONIVEL

    motor.enfileirar_comando(Comando("retornar_unidade", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}
```

- [ ] **Step 4: Registrar o router em `mundo/api/app.py`**

```python
# mundo/api/app.py — dentro de criar_app()
def criar_app() -> FastAPI:
    from . import armazenagem, extracao, missao, transporte

    app = FastAPI(title="Mundo — Operação Marciana", lifespan=ciclo_de_vida)
    app.include_router(missao.router)
    app.include_router(extracao.router)
    app.include_router(armazenagem.router)
    app.include_router(transporte.router)
    return app
```

- [ ] **Step 5: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_api_transporte.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add mundo/api/transporte.py mundo/api/app.py mundo/testes/test_api_transporte.py
git commit -m "feat: add Central de Transporte router enforcing route/authorization rules"
```

---

### Task 21: API — Router da Central de Pesquisa

**Files:**
- Create: `mundo/api/pesquisa.py`
- Modify: `mundo/motor/motor_de_simulacao.py` (nenhuma mudança de código — `fila_de_pesquisa` e `faturamento_total` já existem desde a Task 13; apenas confirmar)
- Modify: `mundo/api/app.py` (registrar novo router)
- Test: `mundo/testes/test_api_pesquisa.py`

**Interfaces:**
- Consumes: `obter_motor` (Task 16), `Comando` (Task 11), `motor.fila_de_pesquisa`, `motor.faturamento_total`, `motor.catalogo_de_minerais` (Task 13).
- Produces: endpoints `GET /pesquisa/fila`, `POST /pesquisa/iniciar-analise`, `POST /pesquisa/classificar-carga`, `POST /pesquisa/aprovar-carga`, `POST /pesquisa/rejeitar-carga`, `POST /pesquisa/preparar-distribuicao`.

- [ ] **Step 1: Escrever o teste falhando**

```python
# mundo/testes/test_api_pesquisa.py
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.cargas import CargaMineral


def test_iniciar_analise_adiciona_carga_na_fila():
    app = criar_app()
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)
        motor.energia.alocar_energia("reserva_estrategica", "pesquisa", 20)

        cliente.post("/pesquisa/iniciar-analise", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1)
        assert "carga-1" in motor.fila_de_pesquisa


def test_aprovar_carga_com_qualidade_baixa_gera_operacao_invalida():
    app = criar_app()
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 10.0)

        cliente.post("/pesquisa/aprovar-carga", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1)
        assert any(e.tipo == "operacao_invalida" for e in motor.eventos.consultar_eventos())


def test_preparar_distribuicao_soma_faturamento():
    app = criar_app()
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 100.0)

        resposta_autorizacao = cliente.post("/missao/autorizar-missao", json={
            "operacao": "preparar_distribuicao", "central_solicitante": "pesquisa",
        })
        id_autorizacao = resposta_autorizacao.json()["id_autorizacao"]

        cliente.post("/pesquisa/preparar-distribuicao", json={
            "identificador_da_carga": "carga-1", "id_autorizacao": id_autorizacao,
        })
        motor.avancar_ciclo(1)
        assert motor.faturamento_total == 50.0  # 10 * 5.0 (hematita) * (100/100)
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest mundo/testes/test_api_pesquisa.py -v`
Expected: FAIL com 404

- [ ] **Step 3: Implementar `mundo/api/pesquisa.py`**

```python
# mundo/api/pesquisa.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mundo.motor.comandos import Comando

from .dependencias import obter_motor

router = APIRouter(prefix="/pesquisa", tags=["pesquisa"])
CENTRAL = "pesquisa"
DURACAO_ANALISE_EM_CICLOS = 3
CUSTO_ENERGETICO_ANALISE = 2
LIMIAR_QUALIDADE_APROVACAO = 40.0


@router.get("/fila")
def consultar_fila() -> list[str]:
    motor = obter_motor()
    return list(motor.fila_de_pesquisa)


class RequisicaoDeAnalise(BaseModel):
    identificador_da_carga: str


@router.post("/iniciar-analise")
def iniciar_analise(requisicao: RequisicaoDeAnalise) -> dict:
    motor = obter_motor()
    if requisicao.identificador_da_carga not in motor.cargas:
        raise HTTPException(status_code=404, detail="Carga não encontrada")

    def executar() -> None:
        motor.energia.debitar(CENTRAL, CUSTO_ENERGETICO_ANALISE)
        motor.fila_de_pesquisa.append(requisicao.identificador_da_carga)
        ciclo_conclusao = motor.ciclo_atual + DURACAO_ANALISE_EM_CICLOS

        def concluir() -> None:
            motor.eventos.publicar("analise_concluida", motor.ciclo_atual, {
                "carga": requisicao.identificador_da_carga,
            })

        motor.agendar_efeito(ciclo_conclusao, concluir)

    motor.enfileirar_comando(Comando("iniciar_analise", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


@router.post("/classificar-carga")
def classificar_carga(requisicao: RequisicaoDeAnalise) -> dict:
    motor = obter_motor()
    carga = motor.cargas.get(requisicao.identificador_da_carga)
    if carga is None:
        raise HTTPException(status_code=404, detail="Carga não encontrada")
    return {"carga": carga.identificador, "mineral": carga.mineral, "qualidade": carga.qualidade}


@router.post("/aprovar-carga")
def aprovar_carga(requisicao: RequisicaoDeAnalise) -> dict:
    motor = obter_motor()

    def executar() -> None:
        carga = motor.cargas[requisicao.identificador_da_carga]
        if carga.qualidade < LIMIAR_QUALIDADE_APROVACAO:
            raise ValueError("Qualidade insuficiente para aprovação")
        if requisicao.identificador_da_carga in motor.fila_de_pesquisa:
            motor.fila_de_pesquisa.remove(requisicao.identificador_da_carga)
        motor.eventos.publicar("carga_aprovada", motor.ciclo_atual, {"carga": carga.identificador})

    motor.enfileirar_comando(Comando("aprovar_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


@router.post("/rejeitar-carga")
def rejeitar_carga(requisicao: RequisicaoDeAnalise) -> dict:
    motor = obter_motor()

    def executar() -> None:
        if requisicao.identificador_da_carga in motor.fila_de_pesquisa:
            motor.fila_de_pesquisa.remove(requisicao.identificador_da_carga)
        motor.eventos.publicar("carga_rejeitada", motor.ciclo_atual, {"carga": requisicao.identificador_da_carga})

    motor.enfileirar_comando(Comando("rejeitar_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


class RequisicaoDeDistribuicao(BaseModel):
    identificador_da_carga: str
    id_autorizacao: str


@router.post("/preparar-distribuicao")
def preparar_distribuicao(requisicao: RequisicaoDeDistribuicao) -> dict:
    motor = obter_motor()

    def executar() -> None:
        motor.autorizacoes.consumir(requisicao.id_autorizacao, "preparar_distribuicao")
        carga = motor.cargas[requisicao.identificador_da_carga]
        mineral = motor.catalogo_de_minerais.obter(carga.mineral)
        valor_entregue = carga.valor_efetivo(mineral.valor_por_unidade)
        motor.faturamento_total += valor_entregue
        motor.eventos.publicar("carga_entregue", motor.ciclo_atual, {
            "carga": carga.identificador, "valor_entregue": valor_entregue,
        })

    motor.enfileirar_comando(Comando("preparar_distribuicao", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}
```

- [ ] **Step 4: Registrar o router em `mundo/api/app.py`**

```python
# mundo/api/app.py — dentro de criar_app()
def criar_app() -> FastAPI:
    from . import armazenagem, extracao, missao, pesquisa, transporte

    app = FastAPI(title="Mundo — Operação Marciana", lifespan=ciclo_de_vida)
    app.include_router(missao.router)
    app.include_router(extracao.router)
    app.include_router(armazenagem.router)
    app.include_router(transporte.router)
    app.include_router(pesquisa.router)
    return app
```

- [ ] **Step 5: Rodar e confirmar passa**

Run: `pytest mundo/testes/test_api_pesquisa.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Rodar toda a suíte para garantir que nada regrediu**

Run: `pytest mundo/testes -v`
Expected: todos os testes das Tasks 1-21 PASS

- [ ] **Step 7: Commit**

```bash
git add mundo/api/pesquisa.py mundo/api/app.py mundo/testes/test_api_pesquisa.py
git commit -m "feat: add Central de Pesquisa router — analysis, approval, and delivery billing"
```

---

### Task 22: Linguagem do Domínio

**Files:**
- Create: `docs/LINGUAGEM_DO_DOMINIO.md`

**Interfaces:**
- Nenhuma — documento de referência terminológica, fonte de verdade conforme `SPEC_INICIAL.md` §43.

- [ ] **Step 1: Escrever o documento**

```markdown
# Linguagem do Domínio — Operação Marciana

Fonte de verdade terminológica do projeto (`SPEC_INICIAL.md` §43). Todo código de domínio deve usar estes termos.

## Mundo

Simulação completa da operação em Marte. Fonte de verdade sobre todo estado; Centrais não alteram esse estado diretamente, apenas enviam comandos.

## Ciclo

Unidade discreta de tempo simulado (`ciclo_atual`). Avança via `avancar_ciclo`, disparado por um loop em tempo real ou manualmente (testes/Avaliador).

## Comando

Intenção de ação enviada por uma Central via API. Entra em uma `FilaDeComandos` e só é aplicado ao estado no próximo ciclo processado — nunca na hora da chamada HTTP.

## Efeito Agendado

Consequência de um comando que não é instantânea (ex.: extração leva N ciclos). Registrado com um `ciclo_alvo` e disparado quando o motor atinge esse ciclo.

## Evento do Mundo

Alteração relevante do estado do ambiente, publicada pelo `BarramentoDeEventos`. Possui `identificador`, `tipo`, `ciclo`, `dados`. Entregue por polling (`consultar_eventos`) e opcionalmente por webhook (fire-and-forget, sem garantia de entrega).

## Autorização

Permissão emitida pela Central de Missão (`id_autorizacao`) exigida por operações que dependem de coordenação entre Centrais (ex.: `iniciar_viagem`, `preparar_distribuicao`). Uso único.

## Jazida

Local conhecido contendo quantidade finita de um mineral. Estados: `desconhecida → identificada → disponivel → interditada/esgotada`. Jazida esgotada nunca regenera.

## Mineral

Recurso extraível com valor econômico fixo durante toda a simulação (sem flutuação de mercado). Atributos: `valor_por_unidade`, `raridade`, `custo_extracao`, `massa`, `taxa_degradacao`, `sensibilidade_temperatura`, `sensibilidade_transporte`, `sensibilidade_armazenagem`.

## Carga Mineral

Quantidade de material extraído em trânsito entre extração, armazenagem, transporte e pesquisa. Possui `qualidade` (0–100, sempre limitada a esse intervalo) que pode degradar por espera, armazenagem inadequada, transporte ou eventos ambientais.

## Valor Efetivo

Valor econômico realmente entregue por uma carga: `quantidade * valor_por_unidade * (qualidade / 100)`. Só é contabilizado no `faturamento_total` quando a carga passa por `preparar_distribuicao` com autorização válida da Missão.

## Unidade Mineradora

Robô capaz de extrair minerais de jazidas. Não possui estratégia própria — só executa comandos válidos.

## Unidade Transportadora

Robô capaz de transportar cargas entre localizações, com `viagens_disponiveis` finitas.

## Armazém

Estrutura com `capacidade`, `ocupacao` e `compatibilidades` de mineral. Reservar espaço além da capacidade lança `CapacidadeExcedidaError`. Receber mineral incompatível gera evento `carga_contaminada`.

## Rota

Caminho entre localizações com `distancia`, `tempo_base`, `risco` e `condicao` (`livre`/`interditada`).

## Central

Um dos cinco serviços operacionais controlados pelos participantes: Extração, Armazenagem, Transporte, Pesquisa, Missão. Toda comunicação entre Centrais operacionais passa pela Central de Missão — imposta por contrato de autorização, não por isolamento de rede.

## Energia

Recurso global finito (`energia_total = 1000`). Cada Central inicia com 10 unidades; a reserva estratégica (950) é controlada exclusivamente pela Central de Missão. Não há geração de energia durante a simulação — o pool nunca regenera.

## Reserva Estratégica

Saldo de energia controlado pela Central de Missão, origem obrigatória de toda alocação de energia (`alocar_energia`).

## Semente

Valor inteiro (`semente`) que inicializa o gerador de números aleatórios (`random.Random`) do motor. Mesma semente + mesmas ações via ciclo manual produzem o mesmo estado final e a mesma sequência de eventos.

## Faturamento

Soma dos valores efetivos de todas as cargas que passaram por `preparar_distribuicao` com sucesso (`motor.faturamento_total`).
```

- [ ] **Step 2: Commit**

```bash
git add docs/LINGUAGEM_DO_DOMINIO.md
git commit -m "docs: add domain language reference (SPEC_INICIAL §43)"
```
