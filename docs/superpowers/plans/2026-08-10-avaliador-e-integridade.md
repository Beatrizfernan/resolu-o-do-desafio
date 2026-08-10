# Avaliador e Integridade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline evaluator that verifies platform integrity, runs multiple seeded simulations against `centrais/avaliacao.py`, and writes a local Markdown report.

**Architecture:** `integridade/` owns a deterministic manifest of protected files and blocks evaluation on divergence. `avaliador/` loads the participant entry point, drives the world through a controlled client facade, collects per-seed metrics from the world state and event stream, aggregates results, and renders a deterministic Markdown report.

**Tech Stack:** Python 3.12+, stdlib (`argparse`, `hashlib`, `importlib`, `json`, `statistics`, `traceback`, `pathlib`), FastAPI test client, Pydantic, pytest.

## Global Constraints

- Todo codigo pertencente ao dominio deve utilizar portugues.
- `avaliador/` deve ser offline; nao criar API HTTP para ele.
- `integridade/` protege `mundo/**`, `avaliador/**` e `pyproject.toml`; `centrais/**` fica fora do manifesto.
- O ponto de entrada obrigatorio do participante e `centrais/avaliacao.py:executar_avaliacao(cliente, limite_de_ciclos)`.
- O relatorio principal e Markdown local, deterministicamente renderizado.
- Nao criar score composto opaco na primeira versao; medir e reportar metricas auditaveis.
- Nao fazer commits neste plano sem pedido explicito do usuario.

---

## Estrutura de arquivos

- Create: `integridade/__init__.py` - exportacoes publicas do subsistema.
- Create: `integridade/manifesto.py` - descoberta de arquivos protegidos e geracao do manifesto JSON.
- Create: `integridade/verificador.py` - comparacao de manifesto vs workspace e tipos de divergencia.
- Create: `integridade/testes/test_integridade.py` - testes do manifesto e da verificacao.
- Create: `avaliador/__init__.py` - exportacoes publicas do subsistema.
- Create: `avaliador/dominio/status_de_avaliacao.py` - enumeracao de status por seed/execucao.
- Create: `avaliador/dominio/resultado_da_seed.py` - dataclass da seed, agregados e erro resumido.
- Create: `avaliador/dominio/relatorio_de_avaliacao.py` - dataclass do relatorio agregado e status de integridade.
- Create: `avaliador/aplicacao/carregador_de_centrais.py` - import dinamico de `centrais/avaliacao.py`.
- Create: `avaliador/aplicacao/cliente_de_avaliacao.py` - fachada controlada sobre o mundo e suas rotas.
- Create: `avaliador/aplicacao/coletor_de_metricas.py` - leitura do motor/eventos e agregacao estatistica.
- Create: `avaliador/aplicacao/renderizador_markdown.py` - serializacao deterministica do relatorio.
- Create: `avaliador/aplicacao/avaliador_offline.py` - orquestracao de integridade, seeds e relatorio.
- Create: `avaliador/cli.py` - CLI offline.
- Create: `avaliador/testes/test_carregador_e_cliente.py` - contrato do runner e do cliente.
- Create: `avaliador/testes/test_avaliador_offline.py` - fluxo por seed, falhas e agregados.
- Create: `avaliador/testes/test_cli.py` - cobertura da CLI e do arquivo Markdown.
- Create: `centrais/avaliacao.py` - ponto de entrada padrao minimo para manter a avaliacao executavel.
- Modify: `pyproject.toml` - incluir os novos pacotes em `tool.setuptools.packages.find.include` e adicionar `avaliador/testes` e `integridade/testes` ao pytest.

### Task 1: Subsistema de Integridade

**Files:**
- Create: `integridade/__init__.py`
- Create: `integridade/manifesto.py`
- Create: `integridade/verificador.py`
- Create: `integridade/testes/test_integridade.py`

**Interfaces:**
- Produces: `gerar_manifesto(raiz_do_projeto: Path, caminho_do_manifesto: Path) -> dict`
- Produces: `verificar_integridade(raiz_do_projeto: Path, caminho_do_manifesto: Path) -> ResultadoDaIntegridade`
- Produces: `ResultadoDaIntegridade(aprovada: bool, divergencias: list[str], manifesto_lido: dict | None)`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from integridade.manifesto import gerar_manifesto
from integridade.verificador import verificar_integridade


def test_gera_e_verifica_manifesto_sem_alteracoes(tmp_path: Path):
    (tmp_path / "mundo").mkdir()
    (tmp_path / "mundo" / "arquivo.py").write_text("print('ok')\n")
    (tmp_path / "avaliador").mkdir()
    (tmp_path / "avaliador" / "cli.py").write_text("print('cli')\n")
    (tmp_path / "centrais").mkdir()
    (tmp_path / "centrais" / "avaliacao.py").write_text("# livre\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    manifesto = tmp_path / "integridade" / "manifesto.sha256.json"
    manifesto.parent.mkdir()

    gerar_manifesto(tmp_path, manifesto)
    resultado = verificar_integridade(tmp_path, manifesto)

    assert resultado.aprovada is True
    assert resultado.divergencias == []


def test_detecta_arquivo_protegido_alterado_e_ignora_centrais(tmp_path: Path):
    (tmp_path / "mundo").mkdir()
    arquivo_protegido = tmp_path / "mundo" / "arquivo.py"
    arquivo_protegido.write_text("print('a')\n")
    (tmp_path / "avaliador").mkdir()
    (tmp_path / "avaliador" / "cli.py").write_text("print('cli')\n")
    (tmp_path / "centrais").mkdir()
    arquivo_livre = tmp_path / "centrais" / "avaliacao.py"
    arquivo_livre.write_text("print('livre')\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    manifesto = tmp_path / "integridade" / "manifesto.sha256.json"
    manifesto.parent.mkdir()

    gerar_manifesto(tmp_path, manifesto)
    arquivo_protegido.write_text("print('b')\n")
    arquivo_livre.write_text("print('mudou mas pode')\n")

    resultado = verificar_integridade(tmp_path, manifesto)

    assert resultado.aprovada is False
    assert any("mundo/arquivo.py" in item for item in resultado.divergencias)
    assert all("centrais/avaliacao.py" not in item for item in resultado.divergencias)


def test_detecta_arquivo_protegido_ausente_ou_novo(tmp_path: Path):
    (tmp_path / "mundo").mkdir()
    arquivo = tmp_path / "mundo" / "arquivo.py"
    arquivo.write_text("print('a')\n")
    (tmp_path / "avaliador").mkdir()
    (tmp_path / "avaliador" / "cli.py").write_text("print('cli')\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    manifesto = tmp_path / "integridade" / "manifesto.sha256.json"
    manifesto.parent.mkdir()

    gerar_manifesto(tmp_path, manifesto)
    arquivo.unlink()
    (tmp_path / "mundo" / "novo.py").write_text("print('novo')\n")

    resultado = verificar_integridade(tmp_path, manifesto)

    assert resultado.aprovada is False
    assert any("ausente" in item for item in resultado.divergencias)
    assert any("novo" in item for item in resultado.divergencias)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest integridade/testes/test_integridade.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing symbol errors for `integridade`.

- [ ] **Step 3: Write the minimal implementation**

```python
# integridade/manifesto.py
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


ESCOPOS_PROTEGIDOS = ("mundo", "avaliador")
ARQUIVOS_RAIZ = ("pyproject.toml",)
IGNORADOS = {"__pycache__", ".pytest_cache"}


def _iterar_arquivos_protegidos(raiz_do_projeto: Path) -> list[Path]:
    encontrados: list[Path] = []
    for nome in ESCOPOS_PROTEGIDOS:
        base = raiz_do_projeto / nome
        if not base.exists():
            continue
        for caminho in sorted(base.rglob("*")):
            if caminho.is_dir() or caminho.suffix == ".pyc":
                continue
            if any(parte in IGNORADOS for parte in caminho.parts):
                continue
            encontrados.append(caminho)
    for nome in ARQUIVOS_RAIZ:
        caminho = raiz_do_projeto / nome
        if caminho.exists():
            encontrados.append(caminho)
    return sorted(encontrados)


def _hash_do_arquivo(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def gerar_manifesto(raiz_do_projeto: Path, caminho_do_manifesto: Path) -> dict:
    arquivos = {
        str(caminho.relative_to(raiz_do_projeto)): _hash_do_arquivo(caminho)
        for caminho in _iterar_arquivos_protegidos(raiz_do_projeto)
    }
    manifesto = {"versao": 1, "algoritmo": "sha256", "arquivos": arquivos}
    caminho_do_manifesto.parent.mkdir(parents=True, exist_ok=True)
    caminho_do_manifesto.write_text(json.dumps(manifesto, indent=2, sort_keys=True) + "\n")
    return manifesto


# integridade/verificador.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .manifesto import _hash_do_arquivo, _iterar_arquivos_protegidos


@dataclass(frozen=True)
class ResultadoDaIntegridade:
    aprovada: bool
    divergencias: list[str]
    manifesto_lido: dict | None


def verificar_integridade(raiz_do_projeto: Path, caminho_do_manifesto: Path) -> ResultadoDaIntegridade:
    if not caminho_do_manifesto.exists():
        return ResultadoDaIntegridade(False, [f"Manifesto ausente: {caminho_do_manifesto}"], None)
    manifesto = json.loads(caminho_do_manifesto.read_text())
    esperados = manifesto.get("arquivos", {})
    atuais = {
        str(caminho.relative_to(raiz_do_projeto)): _hash_do_arquivo(caminho)
        for caminho in _iterar_arquivos_protegidos(raiz_do_projeto)
    }
    divergencias: list[str] = []
    for caminho_relativo, hash_esperado in esperados.items():
        hash_atual = atuais.get(caminho_relativo)
        if hash_atual is None:
            divergencias.append(f"Arquivo protegido ausente: {caminho_relativo}")
        elif hash_atual != hash_esperado:
            divergencias.append(f"Hash divergente: {caminho_relativo}")
    for caminho_relativo in atuais:
        if caminho_relativo not in esperados:
            divergencias.append(f"Arquivo protegido novo nao manifestado: {caminho_relativo}")
    return ResultadoDaIntegridade(not divergencias, divergencias, manifesto)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest integridade/testes/test_integridade.py -v`
Expected: PASS.

### Task 2: Contrato do Runner e Cliente de Avaliacao

**Files:**
- Create: `avaliador/__init__.py`
- Create: `avaliador/aplicacao/carregador_de_centrais.py`
- Create: `avaliador/aplicacao/cliente_de_avaliacao.py`
- Create: `avaliador/testes/test_carregador_e_cliente.py`
- Create: `centrais/avaliacao.py`

**Interfaces:**
- Consumes: `mundo.api.app.criar_app(com_loop_real_time: bool = True) -> FastAPI`
- Produces: `carregar_executor(raiz_do_projeto: Path) -> Callable[[ClienteDeAvaliacao, int], None]`
- Produces: `ClienteDeAvaliacao.resetar(semente: int) -> None`
- Produces: `ClienteDeAvaliacao.consultar_estado() -> dict`
- Produces: `ClienteDeAvaliacao.consultar_eventos(desde_ciclo: int = 0) -> list[dict]`
- Produces: `ClienteDeAvaliacao.chamar(metodo: str, rota: str, json: dict | None = None) -> dict | list[dict]`
- Produces: `ClienteDeAvaliacao.avancar_ciclo(quantidade: int = 1) -> None`
- Produces: `ClienteDeAvaliacao.simulacao_encerrada() -> bool`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

import pytest

from avaliador.aplicacao.carregador_de_centrais import carregar_executor
from avaliador.aplicacao.cliente_de_avaliacao import ClienteDeAvaliacao


def test_carrega_executor_valido(tmp_path: Path):
    pasta = tmp_path / "centrais"
    pasta.mkdir()
    (pasta / "avaliacao.py").write_text(
        "def executar_avaliacao(cliente, limite_de_ciclos):\n"
        "    cliente.avancar_ciclo()\n"
    )

    executor = carregar_executor(tmp_path)

    assert callable(executor)


def test_falha_quando_executar_avaliacao_nao_existe(tmp_path: Path):
    pasta = tmp_path / "centrais"
    pasta.mkdir()
    (pasta / "avaliacao.py").write_text("x = 1\n")

    with pytest.raises(RuntimeError, match="executar_avaliacao"):
        carregar_executor(tmp_path)


def test_cliente_controla_o_mundo_e_expande_rotas_existentes():
    cliente = ClienteDeAvaliacao()
    cliente.resetar(semente=7)

    estado = cliente.consultar_estado()
    jazidas = cliente.chamar("GET", "/extracao/jazidas")
    cliente.avancar_ciclo(2)
    eventos = cliente.consultar_eventos(0)

    assert estado["ciclo_atual"] == 0
    assert isinstance(jazidas, list)
    assert cliente.consultar_estado()["ciclo_atual"] == 2
    assert isinstance(eventos, list)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest avaliador/testes/test_carregador_e_cliente.py -v`
Expected: FAIL with missing `avaliador` package or symbols.

- [ ] **Step 3: Write the minimal implementation**

```python
# avaliador/aplicacao/carregador_de_centrais.py
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Callable


def carregar_executor(raiz_do_projeto: Path) -> Callable:
    caminho = raiz_do_projeto / "centrais" / "avaliacao.py"
    if not caminho.exists():
        raise RuntimeError(f"Arquivo de avaliacao ausente: {caminho}")
    spec = importlib.util.spec_from_file_location("centrais.avaliacao", caminho)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nao foi possivel carregar: {caminho}")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    executor = getattr(modulo, "executar_avaliacao", None)
    if not callable(executor):
        raise RuntimeError("centrais/avaliacao.py deve expor executar_avaliacao(cliente, limite_de_ciclos)")
    return executor


# avaliador/aplicacao/cliente_de_avaliacao.py
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from mundo.api.app import criar_app


class ClienteDeAvaliacao:
    def __init__(self) -> None:
        self._app = criar_app(com_loop_real_time=False)
        self._cliente_http = TestClient(self._app)

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
        with self._app.router.lifespan_context(self._app):
            pass
        from mundo.api.dependencias import obter_motor

        obter_motor().avancar_ciclo(quantidade)

    def simulacao_encerrada(self) -> bool:
        from mundo.api.dependencias import obter_motor

        return obter_motor().encerrada


# centrais/avaliacao.py
def executar_avaliacao(cliente, limite_de_ciclos: int) -> None:
    for _ in range(min(limite_de_ciclos, 1)):
        if cliente.simulacao_encerrada():
            return
        cliente.avancar_ciclo()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest avaliador/testes/test_carregador_e_cliente.py -v`
Expected: PASS.

### Task 3: Coleta, Agregacao e Markdown

**Files:**
- Create: `avaliador/dominio/status_de_avaliacao.py`
- Create: `avaliador/dominio/resultado_da_seed.py`
- Create: `avaliador/dominio/relatorio_de_avaliacao.py`
- Create: `avaliador/aplicacao/coletor_de_metricas.py`
- Create: `avaliador/aplicacao/renderizador_markdown.py`
- Create: `avaliador/testes/test_avaliador_offline.py`

**Interfaces:**
- Produces: `StatusDeAvaliacao(Enum)` com `OK`, `FALHA_OPERACIONAL`, `LIMITE_EXCEDIDO`, `ERRO_DE_CONFIGURACAO`, `INTEGRIDADE_REPROVADA`
- Produces: `ResultadoDaSeed(...)`
- Produces: `RelatorioDeAvaliacao(...)`
- Produces: `coletar_resultado_da_seed(seed: int, cliente: ClienteDeAvaliacao, status: StatusDeAvaliacao, erro_operacional: str | None = None) -> ResultadoDaSeed`
- Produces: `agregar_resultados(resultados: list[ResultadoDaSeed], integridade_aprovada: bool, divergencias: list[str], configuracao: dict) -> RelatorioDeAvaliacao`
- Produces: `renderizar_relatorio_markdown(relatorio: RelatorioDeAvaliacao) -> str`

- [ ] **Step 1: Write the failing tests**

```python
from avaliador.aplicacao.cliente_de_avaliacao import ClienteDeAvaliacao
from avaliador.aplicacao.coletor_de_metricas import agregar_resultados, coletar_resultado_da_seed
from avaliador.aplicacao.renderizador_markdown import renderizar_relatorio_markdown
from avaliador.dominio.status_de_avaliacao import StatusDeAvaliacao


def test_coleta_metricas_basicas_da_seed():
    cliente = ClienteDeAvaliacao()
    cliente.resetar(semente=11)
    cliente.avancar_ciclo(1)

    resultado = coletar_resultado_da_seed(11, cliente, StatusDeAvaliacao.OK)

    assert resultado.seed == 11
    assert resultado.ciclo_final == 1
    assert resultado.faturamento_total >= 0.0
    assert resultado.energia_encalhada >= 0.0


def test_renderiza_relatorio_markdown_deterministico():
    cliente = ClienteDeAvaliacao()
    cliente.resetar(semente=12)
    resultado = coletar_resultado_da_seed(12, cliente, StatusDeAvaliacao.OK)
    relatorio = agregar_resultados([resultado], True, [], {"seeds": [12], "limite_de_ciclos": 5})

    markdown = renderizar_relatorio_markdown(relatorio)

    assert "# Relatorio de Avaliacao" in markdown
    assert "## Status" in markdown
    assert "## Resultados por seed" in markdown
    assert "12" in markdown


def test_renderiza_bloqueio_por_integridade_sem_placar():
    relatorio = agregar_resultados([], False, ["Hash divergente: mundo/x.py"], {"seeds": [1]})

    markdown = renderizar_relatorio_markdown(relatorio)

    assert "Integridade: reprovada" in markdown
    assert "avaliacao foi abortada" in markdown.lower()
    assert "## Resultados por seed" not in markdown
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest avaliador/testes/test_avaliador_offline.py -v`
Expected: FAIL with missing domain models or collector functions.

- [ ] **Step 3: Write the minimal implementation**

```python
# avaliador/dominio/status_de_avaliacao.py
from __future__ import annotations

from enum import Enum


class StatusDeAvaliacao(str, Enum):
    OK = "ok"
    FALHA_OPERACIONAL = "falha_operacional"
    LIMITE_EXCEDIDO = "limite_excedido"
    ERRO_DE_CONFIGURACAO = "erro_de_configuracao"
    INTEGRIDADE_REPROVADA = "integridade_reprovada"


# avaliador/dominio/resultado_da_seed.py
from __future__ import annotations

from dataclasses import dataclass, field

from .status_de_avaliacao import StatusDeAvaliacao


@dataclass(frozen=True)
class ResultadoDaSeed:
    seed: int
    status: StatusDeAvaliacao
    ciclo_final: int
    faturamento_total: float
    energia_encalhada: float
    operacoes_invalidas: int = 0
    autorizacoes_emitidas: int = 0
    cargas_entregues: int = 0
    cargas_analisadas: int = 0
    jazidas_esgotadas: int = 0
    erro_operacional: str | None = None


# avaliador/dominio/relatorio_de_avaliacao.py
from __future__ import annotations

from dataclasses import dataclass

from .resultado_da_seed import ResultadoDaSeed


@dataclass(frozen=True)
class RelatorioDeAvaliacao:
    integridade_aprovada: bool
    divergencias_de_integridade: list[str]
    configuracao: dict
    resultados: list[ResultadoDaSeed]
    faturamento_medio: float
    faturamento_mediano: float
    ciclo_medio_de_encerramento: float
    energia_encalhada_media: float
    taxa_de_falha_operacional: float


# avaliador/aplicacao/coletor_de_metricas.py
from __future__ import annotations

from statistics import median

from mundo.api.dependencias import obter_motor

from avaliador.dominio.relatorio_de_avaliacao import RelatorioDeAvaliacao
from avaliador.dominio.resultado_da_seed import ResultadoDaSeed
from avaliador.dominio.status_de_avaliacao import StatusDeAvaliacao


def coletar_resultado_da_seed(seed: int, cliente, status: StatusDeAvaliacao, erro_operacional: str | None = None) -> ResultadoDaSeed:
    motor = obter_motor()
    eventos = motor.eventos.consultar_eventos(0)
    energia_encalhada = sum(motor.energia.saldos.values())
    return ResultadoDaSeed(
        seed=seed,
        status=status,
        ciclo_final=motor.ciclo_atual,
        faturamento_total=motor.faturamento_total,
        energia_encalhada=energia_encalhada,
        operacoes_invalidas=sum(1 for e in eventos if e.tipo == "operacao_invalida"),
        autorizacoes_emitidas=len(motor.autorizacoes._autorizacoes),
        cargas_entregues=sum(1 for e in eventos if e.tipo == "distribuicao_preparada"),
        cargas_analisadas=sum(1 for e in eventos if e.tipo == "analise_concluida"),
        jazidas_esgotadas=sum(1 for jazida in motor.jazidas.values() if jazida.estado.value == "esgotada"),
        erro_operacional=erro_operacional,
    )


def agregar_resultados(resultados: list[ResultadoDaSeed], integridade_aprovada: bool, divergencias: list[str], configuracao: dict) -> RelatorioDeAvaliacao:
    faturamentos = [item.faturamento_total for item in resultados] or [0.0]
    ciclos = [item.ciclo_final for item in resultados] or [0.0]
    energias = [item.energia_encalhada for item in resultados] or [0.0]
    falhas = [item for item in resultados if item.status == StatusDeAvaliacao.FALHA_OPERACIONAL]
    return RelatorioDeAvaliacao(
        integridade_aprovada=integridade_aprovada,
        divergencias_de_integridade=divergencias,
        configuracao=configuracao,
        resultados=sorted(resultados, key=lambda item: item.seed),
        faturamento_medio=sum(faturamentos) / len(faturamentos),
        faturamento_mediano=median(faturamentos),
        ciclo_medio_de_encerramento=sum(ciclos) / len(ciclos),
        energia_encalhada_media=sum(energias) / len(energias),
        taxa_de_falha_operacional=len(falhas) / len(resultados) if resultados else 0.0,
    )


# avaliador/aplicacao/renderizador_markdown.py
from __future__ import annotations

from avaliador.dominio.relatorio_de_avaliacao import RelatorioDeAvaliacao


def renderizar_relatorio_markdown(relatorio: RelatorioDeAvaliacao) -> str:
    linhas = ["# Relatorio de Avaliacao", "", "## Status"]
    linhas.append(f"- Integridade: {'aprovada' if relatorio.integridade_aprovada else 'reprovada'}")
    if not relatorio.integridade_aprovada:
        linhas.append("- A avaliacao foi abortada por falha de integridade.")
        linhas.append("")
        linhas.append("## Divergencias")
        linhas.extend(f"- {item}" for item in relatorio.divergencias_de_integridade)
        return "\n".join(linhas) + "\n"
    linhas.extend([
        f"- Seeds executadas: {len(relatorio.resultados)}",
        f"- Falhas operacionais: {sum(1 for item in relatorio.resultados if item.erro_operacional)}",
        "",
        "## Resultado agregado",
        f"- Faturamento medio: {relatorio.faturamento_medio:.2f}",
        f"- Faturamento mediano: {relatorio.faturamento_mediano:.2f}",
        f"- Ciclo medio de encerramento: {relatorio.ciclo_medio_de_encerramento:.2f}",
        f"- Energia encalhada media: {relatorio.energia_encalhada_media:.2f}",
        "",
        "## Resultados por seed",
        "| Seed | Status | Faturamento | Ciclo final | Energia encalhada |",
        "|---|---|---:|---:|---:|",
    ])
    for item in relatorio.resultados:
        linhas.append(
            f"| {item.seed} | {item.status.value} | {item.faturamento_total:.2f} | {item.ciclo_final} | {item.energia_encalhada:.2f} |"
        )
    return "\n".join(linhas) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest avaliador/testes/test_avaliador_offline.py -v`
Expected: PASS.

### Task 4: Orquestrador Offline, CLI e Empacotamento

**Files:**
- Create: `avaliador/aplicacao/avaliador_offline.py`
- Create: `avaliador/cli.py`
- Create: `avaliador/testes/test_cli.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `verificar_integridade(...) -> ResultadoDaIntegridade`
- Consumes: `carregar_executor(...) -> Callable`
- Consumes: `coletar_resultado_da_seed(...) -> ResultadoDaSeed`
- Consumes: `agregar_resultados(...) -> RelatorioDeAvaliacao`
- Consumes: `renderizar_relatorio_markdown(...) -> str`
- Produces: `AvaliadorOffline.avaliar(seeds: list[int], limite_de_ciclos: int, caminho_do_manifesto: Path, caminho_de_saida: Path) -> RelatorioDeAvaliacao`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from avaliador.aplicacao.avaliador_offline import AvaliadorOffline


def test_avaliador_gera_relatorio_markdown_e_continua_apos_falha(tmp_path: Path):
    projeto = tmp_path / "projeto"
    projeto.mkdir()
    (projeto / "mundo").mkdir()
    (projeto / "mundo" / "arquivo.py").write_text("print('ok')\n")
    (projeto / "avaliador").mkdir()
    (projeto / "avaliador" / "cli.py").write_text("print('ok')\n")
    (projeto / "centrais").mkdir()
    (projeto / "centrais" / "avaliacao.py").write_text(
        "def executar_avaliacao(cliente, limite_de_ciclos):\n"
        "    cliente.avancar_ciclo(1)\n"
    )
    (projeto / "pyproject.toml").write_text("[project]\nname='x'\n")

    avaliador = AvaliadorOffline(raiz_do_projeto=Path.cwd())
    manifesto = Path("integridade/manifesto.sha256.json")
    saida = tmp_path / "relatorio.md"

    relatorio = avaliador.avaliar([1, 2], 5, manifesto, saida)

    assert saida.exists()
    assert len(relatorio.resultados) == 2
    assert "# Relatorio de Avaliacao" in saida.read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest avaliador/testes/test_cli.py -v`
Expected: FAIL with missing `AvaliadorOffline` or CLI entry point.

- [ ] **Step 3: Write the minimal implementation**

```python
# avaliador/aplicacao/avaliador_offline.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import traceback

from avaliador.aplicacao.carregador_de_centrais import carregar_executor
from avaliador.aplicacao.cliente_de_avaliacao import ClienteDeAvaliacao
from avaliador.aplicacao.coletor_de_metricas import agregar_resultados, coletar_resultado_da_seed
from avaliador.aplicacao.renderizador_markdown import renderizar_relatorio_markdown
from avaliador.dominio.status_de_avaliacao import StatusDeAvaliacao
from integridade.verificador import verificar_integridade


@dataclass
class AvaliadorOffline:
    raiz_do_projeto: Path

    def avaliar(self, seeds: list[int], limite_de_ciclos: int, caminho_do_manifesto: Path, caminho_de_saida: Path):
        integridade = verificar_integridade(self.raiz_do_projeto, caminho_do_manifesto)
        if not integridade.aprovada:
            relatorio = agregar_resultados([], False, integridade.divergencias, {"seeds": seeds, "limite_de_ciclos": limite_de_ciclos})
            caminho_de_saida.parent.mkdir(parents=True, exist_ok=True)
            caminho_de_saida.write_text(renderizar_relatorio_markdown(relatorio))
            return relatorio
        executor = carregar_executor(self.raiz_do_projeto)
        resultados = []
        for seed in seeds:
            cliente = ClienteDeAvaliacao()
            cliente.resetar(seed)
            status = StatusDeAvaliacao.OK
            erro_operacional = None
            try:
                executor(cliente, limite_de_ciclos)
                if not cliente.simulacao_encerrada() and cliente.consultar_estado()["ciclo_atual"] >= limite_de_ciclos:
                    status = StatusDeAvaliacao.LIMITE_EXCEDIDO
            except Exception:
                status = StatusDeAvaliacao.FALHA_OPERACIONAL
                erro_operacional = traceback.format_exc(limit=5)
            resultados.append(coletar_resultado_da_seed(seed, cliente, status, erro_operacional))
        relatorio = agregar_resultados(resultados, True, [], {"seeds": seeds, "limite_de_ciclos": limite_de_ciclos})
        caminho_de_saida.parent.mkdir(parents=True, exist_ok=True)
        caminho_de_saida.write_text(renderizar_relatorio_markdown(relatorio))
        return relatorio


# avaliador/cli.py
from __future__ import annotations

import argparse
from pathlib import Path

from avaliador.aplicacao.avaliador_offline import AvaliadorOffline


def _parsear_seeds(args) -> list[int]:
    if args.seeds:
        return [int(item) for item in args.seeds.split(",") if item]
    return [args.seed_inicial + deslocamento for deslocamento in range(args.quantidade_seeds)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds")
    parser.add_argument("--quantidade-seeds", type=int, default=5)
    parser.add_argument("--seed-inicial", type=int, default=1000)
    parser.add_argument("--saida", default="docs/relatorios/avaliacao.md")
    parser.add_argument("--limite-de-ciclos", type=int, default=5000)
    parser.add_argument("--manifesto", default="integridade/manifesto.sha256.json")
    args = parser.parse_args()

    avaliador = AvaliadorOffline(raiz_do_projeto=Path.cwd())
    relatorio = avaliador.avaliar(_parsear_seeds(args), args.limite_de_ciclos, Path(args.manifesto), Path(args.saida))
    return 0 if relatorio.integridade_aprovada else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["mundo/testes", "avaliador/testes", "integridade/testes"]

[tool.setuptools.packages.find]
include = ["mundo*", "avaliador*", "integridade*"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest avaliador/testes/test_carregador_e_cliente.py avaliador/testes/test_avaliador_offline.py integridade/testes/test_integridade.py -v`
Expected: PASS.

## Auto-revisao do plano

- **Cobertura da spec:** Task 1 cobre manifesto e verificacao; Task 2 cobre contrato `centrais/avaliacao.py` e cliente controlado; Task 3 cobre metricas, agregacao e Markdown; Task 4 cobre orquestracao, CLI e configuracao de pacote/testes.
- **Sem placeholders:** todos os arquivos, comandos e assinaturas principais estao nomeados; nao ha `TODO`/`TBD`.
- **Consistencia de tipos:** `ResultadoDaIntegridade`, `StatusDeAvaliacao`, `ResultadoDaSeed`, `RelatorioDeAvaliacao`, `ClienteDeAvaliacao` e `AvaliadorOffline` mantem nomes consistentes entre tarefas.
