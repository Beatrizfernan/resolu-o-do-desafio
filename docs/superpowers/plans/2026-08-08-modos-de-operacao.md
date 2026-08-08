# Modos de Operação e Degradação por Ciclo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar às ações de extração e transporte um eixo de trade-off real (modos cuidadoso/normal/agressivo e econômico/normal/rápido) e fazer o tempo custar qualidade, via degradação por ciclo sensível ao mineral e ao local da carga.

**Architecture:** Um novo catálogo de perfis em `mundo/dominio/modos.py` (mesmo padrão de `minerais.py`: dataclasses congeladas carregadas de JSON) fornece os multiplicadores. `CargaMineral` passa a rastrear onde está (`local`) e um multiplicador de contexto. O motor ganha um passo de degradação no tick que compõe taxa do mineral × sensibilidade do local × multiplicadores. As rotas de extração e transporte ganham um parâmetro `modo` opcional que resolve o perfil e aplica.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, pytest.

## Global Constraints

- Todo código de domínio (classes, métodos, variáveis, eventos, comandos, endpoints, docs, mensagens, testes) em português. Identificadores de FastAPI/Pydantic permanecem no idioma da biblioteca.
- Python 3.12+.
- Rotas nunca mutam estado de forma síncrona — toda mutação vive dentro de closures `Comando.executar()`, executadas pelo tick.
- Toda aleatoriedade passa pela instância única `random.Random(semente)` do motor. B não introduz nenhuma fonte nova de aleatoriedade.
- `qualidade` sempre limitada a [0, 100] via `clamp_qualidade`.
- Jazida esgotada nunca regenera.
- Retrocompatibilidade obrigatória: `modo` é opcional e o default `NORMAL` deve preservar o comportamento observável dos testes existentes onde isso for possível. Onde o default mudar números (custo de extração passa a derivar de `custo_extracao` do mineral), o plano diz explicitamente qual teste ajustar e por quê.
- Perfis são compostos por multiplicação, nunca embutidos no cálculo — o sub-projeto E precisa poder injetar modificadores no mesmo ponto.

---

### Task 1: Catálogo de modos

**Files:**
- Create: `mundo/config/modos.json`
- Create: `mundo/dominio/modos.py`
- Test: `mundo/testes/test_modos.py`

**Interfaces:**
- Consumes: nada de tarefas anteriores.
- Produces: `ModoDeExtracao` (Enum: `CUIDADOSO`/`NORMAL`/`AGRESSIVO`, valores `"cuidadoso"`/`"normal"`/`"agressivo"`), `ModoDeTransporte` (Enum: `ECONOMICO`/`NORMAL`/`RAPIDO`, valores `"economico"`/`"normal"`/`"rapido"`), `PerfilDeExtracao(mult_energia, mult_duracao, qualidade_inicial, fator_desperdicio)`, `PerfilDeTransporte(mult_energia, mult_duracao, mult_degradacao)`, `CatalogoDeModos` com `.carregar_de_arquivo(caminho: Path)`, `.obter_extracao(modo) -> PerfilDeExtracao`, `.obter_transporte(modo) -> PerfilDeTransporte`, `.mult_do_local(local: str) -> float`, e atributo `.fator_base_de_energia: float`.

- [ ] **Step 1: Criar `mundo/config/modos.json`**

```json
{
  "fator_base_de_energia": 0.2,
  "extracao": {
    "cuidadoso": {"mult_energia": 1.6, "mult_duracao": 1.4, "qualidade_inicial": 100.0, "fator_desperdicio": 1.0},
    "normal": {"mult_energia": 1.0, "mult_duracao": 1.0, "qualidade_inicial": 92.0, "fator_desperdicio": 1.15},
    "agressivo": {"mult_energia": 0.7, "mult_duracao": 0.6, "qualidade_inicial": 78.0, "fator_desperdicio": 1.4}
  },
  "transporte": {
    "economico": {"mult_energia": 0.6, "mult_duracao": 1.5, "mult_degradacao": 1.3},
    "normal": {"mult_energia": 1.0, "mult_duracao": 1.0, "mult_degradacao": 1.0},
    "rapido": {"mult_energia": 1.8, "mult_duracao": 0.6, "mult_degradacao": 0.8}
  },
  "multiplicador_por_local": {
    "em_jazida": 2.0,
    "em_armazem": 1.0,
    "em_transito": 1.0,
    "entregue": 0.0
  }
}
```

- [ ] **Step 2: Escrever o teste falhando**

```python
# mundo/testes/test_modos.py
from pathlib import Path

import pytest

from mundo.dominio.modos import CatalogoDeModos, ModoDeExtracao, ModoDeTransporte

CAMINHO_MODOS = Path(__file__).parent.parent / "config" / "modos.json"


def _catalogo() -> CatalogoDeModos:
    return CatalogoDeModos.carregar_de_arquivo(CAMINHO_MODOS)


def test_carrega_os_tres_modos_de_extracao():
    catalogo = _catalogo()
    for modo in ModoDeExtracao:
        assert catalogo.obter_extracao(modo) is not None


def test_carrega_os_tres_modos_de_transporte():
    catalogo = _catalogo()
    for modo in ModoDeTransporte:
        assert catalogo.obter_transporte(modo) is not None


def test_perfil_de_extracao_agressivo_desperdica_mais_e_gasta_menos():
    catalogo = _catalogo()
    cuidadoso = catalogo.obter_extracao(ModoDeExtracao.CUIDADOSO)
    agressivo = catalogo.obter_extracao(ModoDeExtracao.AGRESSIVO)
    assert agressivo.fator_desperdicio > cuidadoso.fator_desperdicio
    assert agressivo.mult_energia < cuidadoso.mult_energia
    assert agressivo.qualidade_inicial < cuidadoso.qualidade_inicial
    assert agressivo.mult_duracao < cuidadoso.mult_duracao


def test_perfil_de_transporte_rapido_gasta_mais_e_degrada_menos():
    catalogo = _catalogo()
    economico = catalogo.obter_transporte(ModoDeTransporte.ECONOMICO)
    rapido = catalogo.obter_transporte(ModoDeTransporte.RAPIDO)
    assert rapido.mult_energia > economico.mult_energia
    assert rapido.mult_duracao < economico.mult_duracao
    assert rapido.mult_degradacao < economico.mult_degradacao


def test_multiplicador_por_local():
    catalogo = _catalogo()
    assert catalogo.mult_do_local("em_jazida") == 2.0
    assert catalogo.mult_do_local("em_armazem") == 1.0
    assert catalogo.mult_do_local("entregue") == 0.0


def test_fator_base_de_energia_disponivel():
    assert _catalogo().fator_base_de_energia == 0.2


def test_local_desconhecido_lanca_erro():
    with pytest.raises(ValueError):
        _catalogo().mult_do_local("inexistente")
```

- [ ] **Step 3: Rodar e confirmar falha**

Run: `.venv/bin/pytest mundo/testes/test_modos.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'mundo.dominio.modos'`

- [ ] **Step 4: Implementar `mundo/dominio/modos.py`**

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ModoDeExtracao(str, Enum):
    CUIDADOSO = "cuidadoso"
    NORMAL = "normal"
    AGRESSIVO = "agressivo"


class ModoDeTransporte(str, Enum):
    ECONOMICO = "economico"
    NORMAL = "normal"
    RAPIDO = "rapido"


@dataclass(frozen=True)
class PerfilDeExtracao:
    mult_energia: float
    mult_duracao: float
    qualidade_inicial: float
    fator_desperdicio: float


@dataclass(frozen=True)
class PerfilDeTransporte:
    mult_energia: float
    mult_duracao: float
    mult_degradacao: float


class CatalogoDeModos:
    def __init__(
        self,
        extracao: dict[str, PerfilDeExtracao],
        transporte: dict[str, PerfilDeTransporte],
        fator_base_de_energia: float,
        multiplicador_por_local: dict[str, float],
    ) -> None:
        self._extracao = extracao
        self._transporte = transporte
        self.fator_base_de_energia = fator_base_de_energia
        self._multiplicador_por_local = multiplicador_por_local

    @classmethod
    def carregar_de_arquivo(cls, caminho: Path) -> "CatalogoDeModos":
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        extracao = {nome: PerfilDeExtracao(**valores) for nome, valores in dados["extracao"].items()}
        transporte = {
            nome: PerfilDeTransporte(**valores) for nome, valores in dados["transporte"].items()
        }
        return cls(
            extracao,
            transporte,
            dados["fator_base_de_energia"],
            dados["multiplicador_por_local"],
        )

    def obter_extracao(self, modo: ModoDeExtracao) -> PerfilDeExtracao:
        if modo.value not in self._extracao:
            raise ValueError(f"Modo de extração desconhecido: {modo}")
        return self._extracao[modo.value]

    def obter_transporte(self, modo: ModoDeTransporte) -> PerfilDeTransporte:
        if modo.value not in self._transporte:
            raise ValueError(f"Modo de transporte desconhecido: {modo}")
        return self._transporte[modo.value]

    def mult_do_local(self, local: str) -> float:
        if local not in self._multiplicador_por_local:
            raise ValueError(f"Local desconhecido: {local}")
        return self._multiplicador_por_local[local]
```

- [ ] **Step 5: Rodar e confirmar passa**

Run: `.venv/bin/pytest mundo/testes/test_modos.py -v`
Expected: PASS (7 passed)

- [ ] **Step 6: Commit**

```bash
git add mundo/config/modos.json mundo/dominio/modos.py mundo/testes/test_modos.py
git commit -m "feat: add operation-mode profile catalog"
```

---

### Task 2: Local da carga

**Files:**
- Modify: `mundo/dominio/cargas.py`
- Test: `mundo/testes/test_cargas.py`

**Interfaces:**
- Consumes: nada da Task 1 (independente).
- Produces: `LocalDaCarga` (Enum: `EM_JAZIDA`/`EM_ARMAZEM`/`EM_TRANSITO`/`ENTREGUE`, valores `"em_jazida"`/`"em_armazem"`/`"em_transito"`/`"entregue"`); `CargaMineral` ganha os campos `local: LocalDaCarga = LocalDaCarga.EM_JAZIDA` e `mult_degradacao_local: float = 1.0`, e o método `sensibilidade_aplicavel(mineral: Mineral) -> float`.

- [ ] **Step 1: Escrever o teste falhando (adicionar ao arquivo existente)**

```python
# acrescentar em mundo/testes/test_cargas.py
from pathlib import Path

from mundo.dominio.cargas import CargaMineral, LocalDaCarga
from mundo.dominio.minerais import CatalogoDeMinerais

CAMINHO_CATALOGO = Path(__file__).parent.parent / "config" / "minerais.json"


def _mineral(nome: str):
    return CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO).obter(nome)


def test_carga_nasce_em_jazida_com_multiplicador_neutro():
    carga = CargaMineral(identificador="c1", mineral="hematita", quantidade=10.0)
    assert carga.local == LocalDaCarga.EM_JAZIDA
    assert carga.mult_degradacao_local == 1.0


def test_sensibilidade_aplicavel_em_armazem():
    carga = CargaMineral("c1", "gelo_de_agua", 10.0, local=LocalDaCarga.EM_ARMAZEM)
    mineral = _mineral("gelo_de_agua")
    assert carga.sensibilidade_aplicavel(mineral) == mineral.sensibilidade_armazenagem


def test_sensibilidade_aplicavel_em_transito():
    carga = CargaMineral("c1", "gelo_de_agua", 10.0, local=LocalDaCarga.EM_TRANSITO)
    mineral = _mineral("gelo_de_agua")
    assert carga.sensibilidade_aplicavel(mineral) == mineral.sensibilidade_transporte


def test_sensibilidade_aplicavel_exposta_na_jazida_e_total():
    carga = CargaMineral("c1", "gelo_de_agua", 10.0, local=LocalDaCarga.EM_JAZIDA)
    assert carga.sensibilidade_aplicavel(_mineral("gelo_de_agua")) == 1.0
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `.venv/bin/pytest mundo/testes/test_cargas.py -v`
Expected: FAIL com `ImportError: cannot import name 'LocalDaCarga'`

- [ ] **Step 3: Implementar em `mundo/dominio/cargas.py`**

Substituir o conteúdo do arquivo por:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mundo.dominio.minerais import Mineral


class LocalDaCarga(str, Enum):
    EM_JAZIDA = "em_jazida"
    EM_ARMAZEM = "em_armazem"
    EM_TRANSITO = "em_transito"
    ENTREGUE = "entregue"


def clamp_qualidade(valor: float) -> float:
    return max(0.0, min(100.0, valor))


@dataclass
class CargaMineral:
    identificador: str
    mineral: str
    quantidade: float
    qualidade: float = 100.0
    local: LocalDaCarga = LocalDaCarga.EM_JAZIDA
    mult_degradacao_local: float = 1.0

    def __post_init__(self) -> None:
        self.qualidade = clamp_qualidade(self.qualidade)

    def degradar(self, taxa_degradacao: float, fator_contexto: float = 1.0) -> None:
        perda = taxa_degradacao * fator_contexto
        self.qualidade = clamp_qualidade(self.qualidade - perda)

    def valor_efetivo(self, valor_por_unidade: float) -> float:
        return self.quantidade * valor_por_unidade * (self.qualidade / 100)

    def sensibilidade_aplicavel(self, mineral: Mineral) -> float:
        if self.local == LocalDaCarga.EM_ARMAZEM:
            return mineral.sensibilidade_armazenagem
        if self.local == LocalDaCarga.EM_TRANSITO:
            return mineral.sensibilidade_transporte
        return 1.0
```

- [ ] **Step 4: Rodar e confirmar passa**

Run: `.venv/bin/pytest mundo/testes/test_cargas.py -v`
Expected: PASS (todos, incluindo os 6 testes pré-existentes)

- [ ] **Step 5: Commit**

```bash
git add mundo/dominio/cargas.py mundo/testes/test_cargas.py
git commit -m "feat: track cargo location and context multiplier"
```

---

### Task 3: Degradação por ciclo no motor

**Files:**
- Modify: `mundo/motor/motor_de_simulacao.py`
- Test: `mundo/testes/test_degradacao.py` (criar)

**Interfaces:**
- Consumes: `CatalogoDeModos.carregar_de_arquivo`, `.mult_do_local(local: str)` (Task 1); `LocalDaCarga`, `CargaMineral.sensibilidade_aplicavel`, `.mult_degradacao_local` (Task 2).
- Produces: `MotorDeSimulacao.__init__` ganha terceiro parâmetro **opcional** `catalogo_de_modos: CatalogoDeModos | None = None` (quando `None`, carrega de `mundo/config/modos.json`); atributo público `motor.catalogo_de_modos`; método privado `_degradar_cargas()` chamado a cada tick após os efeitos agendados.

- [ ] **Step 1: Escrever o teste falhando**

```python
# mundo/testes/test_degradacao.py
from pathlib import Path

from mundo.dominio.cargas import CargaMineral, LocalDaCarga
from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.motor.motor_de_simulacao import ConfiguracaoDaSimulacao, MotorDeSimulacao

CAMINHO_CATALOGO = Path(__file__).parent.parent / "config" / "minerais.json"


def _criar_motor(semente: int = 1) -> MotorDeSimulacao:
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    return MotorDeSimulacao(ConfiguracaoDaSimulacao(semente=semente, duracao_maxima=50), catalogo)


def test_carga_em_armazem_degrada_conforme_sensibilidade_de_armazenagem():
    motor = _criar_motor()
    motor.cargas["c1"] = CargaMineral(
        "c1", "gelo_de_agua", 10.0, 100.0, local=LocalDaCarga.EM_ARMAZEM,
    )
    mineral = motor.catalogo_de_minerais.obter("gelo_de_agua")
    esperado = 100.0 - mineral.taxa_degradacao * mineral.sensibilidade_armazenagem * 1.0

    motor.avancar_ciclo(1)

    assert motor.cargas["c1"].qualidade == esperado


def test_carga_exposta_na_jazida_degrada_mais_que_em_armazem():
    motor = _criar_motor()
    motor.cargas["exposta"] = CargaMineral(
        "exposta", "gelo_de_agua", 10.0, 100.0, local=LocalDaCarga.EM_JAZIDA,
    )
    motor.cargas["guardada"] = CargaMineral(
        "guardada", "gelo_de_agua", 10.0, 100.0, local=LocalDaCarga.EM_ARMAZEM,
    )

    motor.avancar_ciclo(1)

    assert motor.cargas["exposta"].qualidade < motor.cargas["guardada"].qualidade


def test_mineral_estavel_degrada_muito_menos_que_mineral_sensivel():
    motor = _criar_motor()
    motor.cargas["estavel"] = CargaMineral(
        "estavel", "hematita", 10.0, 100.0, local=LocalDaCarga.EM_ARMAZEM,
    )
    motor.cargas["sensivel"] = CargaMineral(
        "sensivel", "gelo_de_agua", 10.0, 100.0, local=LocalDaCarga.EM_ARMAZEM,
    )

    motor.avancar_ciclo(10)

    assert motor.cargas["estavel"].qualidade > 99.0
    assert motor.cargas["sensivel"].qualidade < 95.0


def test_multiplicador_de_contexto_amplifica_a_perda():
    motor = _criar_motor()
    motor.cargas["neutra"] = CargaMineral(
        "neutra", "jarosita", 10.0, 100.0, local=LocalDaCarga.EM_TRANSITO,
    )
    motor.cargas["penalizada"] = CargaMineral(
        "penalizada", "jarosita", 10.0, 100.0,
        local=LocalDaCarga.EM_TRANSITO, mult_degradacao_local=2.0,
    )

    motor.avancar_ciclo(1)

    perda_neutra = 100.0 - motor.cargas["neutra"].qualidade
    perda_penalizada = 100.0 - motor.cargas["penalizada"].qualidade
    assert perda_penalizada == perda_neutra * 2.0


def test_carga_entregue_nao_degrada():
    motor = _criar_motor()
    motor.cargas["c1"] = CargaMineral(
        "c1", "gelo_de_agua", 10.0, 100.0, local=LocalDaCarga.ENTREGUE,
    )

    motor.avancar_ciclo(20)

    assert motor.cargas["c1"].qualidade == 100.0


def test_qualidade_nunca_fica_negativa():
    motor = _criar_motor()
    motor.cargas["c1"] = CargaMineral(
        "c1", "gelo_de_agua", 10.0, 1.0, local=LocalDaCarga.EM_JAZIDA,
    )

    motor.avancar_ciclo(50)

    assert motor.cargas["c1"].qualidade == 0.0
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `.venv/bin/pytest mundo/testes/test_degradacao.py -v`
Expected: FAIL — `AttributeError: 'MotorDeSimulacao' object has no attribute 'catalogo_de_modos'`

- [ ] **Step 3: Alterar o construtor do motor**

Em `mundo/motor/motor_de_simulacao.py`, acrescentar aos imports do topo:

```python
from mundo.dominio.modos import CatalogoDeModos
```

Acrescentar a constante logo abaixo de `CENTRAIS`:

```python
CAMINHO_MODOS_PADRAO = Path(__file__).parent.parent / "config" / "modos.json"
```

(e `from pathlib import Path` nos imports, se ainda não existir)

Alterar a assinatura e o corpo do `__init__`:

```python
    def __init__(
        self,
        configuracao: ConfiguracaoDaSimulacao,
        catalogo_de_minerais: CatalogoDeMinerais,
        catalogo_de_modos: CatalogoDeModos | None = None,
    ) -> None:
        self.configuracao = configuracao
        self.catalogo_de_minerais = catalogo_de_minerais
        self.catalogo_de_modos = catalogo_de_modos or CatalogoDeModos.carregar_de_arquivo(
            CAMINHO_MODOS_PADRAO,
        )
```

O restante do `__init__` permanece inalterado.

- [ ] **Step 4: Acrescentar o passo de degradação ao tick**

Em `_processar_um_ciclo`, após o laço que publica falhas de efeitos agendados, acrescentar a chamada:

```python
        self._degradar_cargas()
```

E o método novo, logo abaixo de `_processar_um_ciclo`:

```python
    def _degradar_cargas(self) -> None:
        for carga in self.cargas.values():
            mineral = self.catalogo_de_minerais.obter(carga.mineral)
            perda = (
                mineral.taxa_degradacao
                * carga.sensibilidade_aplicavel(mineral)
                * self.catalogo_de_modos.mult_do_local(carga.local.value)
                * carga.mult_degradacao_local
            )
            carga.degradar(taxa_degradacao=perda)
```

- [ ] **Step 5: Rodar e confirmar passa**

Run: `.venv/bin/pytest mundo/testes/test_degradacao.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Rodar a suíte completa**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: todos passam. Se algum teste de API falhar por qualidade agora menor que a esperada, é regressão legítima a corrigir aqui: ajuste a asserção para comparar contra o valor degradado, não para desligar a degradação.

- [ ] **Step 7: Commit**

```bash
git add mundo/motor/motor_de_simulacao.py mundo/testes/test_degradacao.py
git commit -m "feat: degrade cargo quality every cycle by mineral and location"
```

---

### Task 4: Modo na extração

**Files:**
- Modify: `mundo/api/extracao.py`
- Test: `mundo/testes/test_api_extracao.py`

**Interfaces:**
- Consumes: `ModoDeExtracao`, `CatalogoDeModos.obter_extracao`, `.fator_base_de_energia` (Task 1); `LocalDaCarga` (Task 2); `motor.catalogo_de_modos` (Task 3).
- Produces: `RequisicaoDeExtracao` ganha `modo: ModoDeExtracao = ModoDeExtracao.NORMAL`; o evento `extracao_concluida` ganha os campos `modo` e `quantidade_consumida_da_jazida`.

- [ ] **Step 1: Escrever o teste falhando**

```python
# acrescentar em mundo/testes/test_api_extracao.py
def _extrair(cliente, **campos):
    corpo = {
        "identificador_da_unidade": "mineradora-1",
        "identificador_da_jazida": "jazida-1",
        "quantidade": 10.0,
    }
    corpo.update(campos)
    return cliente.post("/extracao/iniciar-extracao", json=corpo)


def test_modo_agressivo_desperdica_mais_da_jazida_que_o_cuidadoso():
    from mundo.api.dependencias import instancia_do_mundo

    for modo, esperado_consumido in (("cuidadoso", 10.0), ("agressivo", 14.0)):
        app = criar_app(com_loop_real_time=False)
        with TestClient(app) as cliente:
            motor = instancia_do_mundo.obter_motor()
            motor.energia.alocar_energia("reserva_estrategica", "extracao", 100)
            restante_antes = motor.jazidas["jazida-1"].quantidade_disponivel

            _extrair(cliente, modo=modo)
            motor.avancar_ciclo(10)

            consumido = restante_antes - motor.jazidas["jazida-1"].quantidade_disponivel
            assert consumido == esperado_consumido


def test_modo_define_a_qualidade_inicial_da_carga():
    from mundo.api.dependencias import instancia_do_mundo

    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 100)

        _extrair(cliente, modo="agressivo")
        motor.avancar_ciclo(1)
        carga = next(iter(motor.cargas.values()))

        assert carga.qualidade == 78.0
        assert carga.local.value == "em_jazida"


def test_modo_agressivo_conclui_antes_do_cuidadoso():
    from mundo.api.dependencias import instancia_do_mundo

    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 100)

        _extrair(cliente, identificador_da_unidade="mineradora-1", modo="agressivo")
        _extrair(cliente, identificador_da_unidade="mineradora-2", modo="cuidadoso")
        motor.avancar_ciclo(4)

        assert motor.robos["mineradora-1"].estado.value == "aguardando"
        assert motor.robos["mineradora-2"].estado.value == "executando"


def test_custo_energetico_deriva_do_mineral_e_do_modo():
    from mundo.api.dependencias import instancia_do_mundo

    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 100)
        mineral = motor.catalogo_de_minerais.obter(motor.jazidas["jazida-1"].mineral)
        antes = motor.energia.consultar_energia("extracao")

        _extrair(cliente, modo="normal")
        motor.avancar_ciclo(1)

        esperado = mineral.custo_extracao * 10.0 * 0.2 * 1.0
        assert antes - motor.energia.consultar_energia("extracao") == pytest.approx(esperado)


def test_modo_invalido_retorna_422():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        assert _extrair(cliente, modo="turbo").status_code == 422
```

Acrescentar `import pytest` ao topo do arquivo de teste, caso ainda não exista.

- [ ] **Step 2: Rodar e confirmar falha**

Run: `.venv/bin/pytest mundo/testes/test_api_extracao.py -v`
Expected: FAIL — o campo `modo` é ignorado, o desperdício não acontece e a qualidade continua 100.

- [ ] **Step 3: Implementar em `mundo/api/extracao.py`**

Acrescentar aos imports:

```python
from mundo.dominio.cargas import CargaMineral, LocalDaCarga
from mundo.dominio.modos import ModoDeExtracao
```

Acrescentar o campo ao modelo de requisição:

```python
class RequisicaoDeExtracao(BaseModel):
    identificador_da_unidade: str
    identificador_da_jazida: str
    quantidade: float
    modo: ModoDeExtracao = ModoDeExtracao.NORMAL
```

Substituir o corpo de `executar()`/`concluir()` dentro de `iniciar_extracao` por:

```python
    def executar() -> None:
        if unidade.estado != EstadoDoRobo.DISPONIVEL:
            raise ValueError("Unidade indisponível")
        if jazida.estado != EstadoDaJazida.DISPONIVEL:
            raise ValueError("Jazida não disponível")
        perfil = motor.catalogo_de_modos.obter_extracao(requisicao.modo)
        mineral = motor.catalogo_de_minerais.obter(jazida.mineral)
        custo = (
            mineral.custo_extracao
            * requisicao.quantidade
            * motor.catalogo_de_modos.fator_base_de_energia
            * perfil.mult_energia
        )
        motor.energia.debitar(CENTRAL, custo)
        unidade.estado = EstadoDoRobo.EXECUTANDO
        duracao = max(1, round(DURACAO_EXTRACAO_EM_CICLOS * perfil.mult_duracao))
        ciclo_conclusao = motor.ciclo_atual + duracao

        def concluir() -> None:
            consumido = requisicao.quantidade * perfil.fator_desperdicio
            jazida.extrair(consumido)
            unidade.estado = EstadoDoRobo.AGUARDANDO
            carga = CargaMineral(
                f"carga-{jazida.identificador}-{unidade.identificador}-{motor.ciclo_atual}",
                jazida.mineral,
                requisicao.quantidade,
                perfil.qualidade_inicial,
                local=LocalDaCarga.EM_JAZIDA,
            )
            motor.cargas[carga.identificador] = carga
            motor.eventos.publicar(
                "extracao_concluida",
                motor.ciclo_atual,
                {
                    "unidade": unidade.identificador,
                    "jazida": jazida.identificador,
                    "quantidade": requisicao.quantidade,
                    "quantidade_consumida_da_jazida": consumido,
                    "modo": requisicao.modo.value,
                    "carga": carga.identificador,
                },
            )

        motor.agendar_efeito(ciclo_conclusao, concluir)
```

Remover a constante `QUALIDADE_INICIAL_DA_CARGA` e a constante `CUSTO_ENERGETICO_EXTRACAO`, que deixam de ser usadas.

**Atenção — o custo passa a ser fracionário.** `GerenciadorDeEnergia` foi escrito com saldos inteiros (`dict[str, int]`) e agora vai receber floats. Isso funciona em Python e as comparações existentes seguem válidas (`30.0 == 30` é verdadeiro), mas há duas coisas a verificar antes de seguir:

1. `_validar_quantidade` rejeita `quantidade <= 0`. Um custo fracionário pequeno continua positivo, então passa — mas confirme que nenhuma combinação de mineral barato com quantidade pequena chega a zero. Com `fator_base_de_energia = 0.2` e o mineral mais barato (`custo_extracao` 1.0), extrair 0.1 unidade custaria 0.02, ainda positivo.
2. Rode `.venv/bin/pytest mundo/testes/test_energia.py -v` após a mudança para confirmar que nada no gerenciador assumia inteiros de forma dura.

Se algum teste de energia quebrar por causa disso, a correção é atualizar as anotações de tipo de `GerenciadorDeEnergia` para `float` — não arredondar o custo, o que destruiria a granularidade do trade-off entre modos.

- [ ] **Step 4: Rodar e confirmar passa**

Run: `.venv/bin/pytest mundo/testes/test_api_extracao.py -v`
Expected: PASS. O teste pré-existente que afirma qualidade 100 na extração precisa mudar para `92.0` — o default `NORMAL` não é mais qualidade máxima, e isso é a mudança de comportamento pretendida. Ajuste a asserção, não o default.

- [ ] **Step 5: Commit**

```bash
git add mundo/api/extracao.py mundo/testes/test_api_extracao.py
git commit -m "feat: add extraction modes trading energy, speed, quality and waste"
```

---

### Task 5: Modo no transporte

**Files:**
- Modify: `mundo/api/transporte.py`
- Test: `mundo/testes/test_api_transporte.py`

**Interfaces:**
- Consumes: `ModoDeTransporte`, `CatalogoDeModos.obter_transporte` (Task 1); `LocalDaCarga` (Task 2); `motor.catalogo_de_modos` (Task 3).
- Produces: `RequisicaoDeViagem` ganha `modo: ModoDeTransporte = ModoDeTransporte.NORMAL`; o evento `transporte_concluido` ganha o campo `modo`.

- [ ] **Step 1: Escrever o teste falhando**

```python
# acrescentar em mundo/testes/test_api_transporte.py
def test_modo_rapido_chega_antes_e_gasta_mais_energia_que_o_economico():
    from mundo.api.dependencias import instancia_do_mundo

    duracoes = {}
    custos = {}
    for modo in ("economico", "rapido"):
        app = criar_app(com_loop_real_time=False)
        with TestClient(app) as cliente:
            motor = instancia_do_mundo.obter_motor()
            motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)
            motor.energia.alocar_energia("reserva_estrategica", "transporte", 100)
            energia_antes = motor.energia.consultar_energia("transporte")

            id_autorizacao = _autorizar(cliente)
            _iniciar_viagem(cliente, id_autorizacao=id_autorizacao, modo=modo)
            motor.avancar_ciclo(1)

            custos[modo] = energia_antes - motor.energia.consultar_energia("transporte")
            ciclos = 0
            while motor.robos["transportadora-1"].estado.value == "executando" and ciclos < 40:
                motor.avancar_ciclo(1)
                ciclos += 1
            duracoes[modo] = ciclos

    assert duracoes["rapido"] < duracoes["economico"]
    assert custos["rapido"] > custos["economico"]


def test_carga_fica_em_transito_durante_a_viagem_e_volta_ao_armazem():
    from mundo.api.dependencias import instancia_do_mundo

    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral(
            "carga-1", "hematita", 10.0, 90.0, local=LocalDaCarga.EM_ARMAZEM,
        )
        motor.energia.alocar_energia("reserva_estrategica", "transporte", 100)

        id_autorizacao = _autorizar(cliente)
        _iniciar_viagem(cliente, id_autorizacao=id_autorizacao, modo="normal")
        motor.avancar_ciclo(1)
        assert motor.cargas["carga-1"].local == LocalDaCarga.EM_TRANSITO

        motor.avancar_ciclo(10)
        assert motor.cargas["carga-1"].local == LocalDaCarga.EM_ARMAZEM


def test_transporte_economico_degrada_mais_a_carga_que_o_rapido():
    from mundo.api.dependencias import instancia_do_mundo

    qualidades = {}
    for modo in ("economico", "rapido"):
        app = criar_app(com_loop_real_time=False)
        with TestClient(app) as cliente:
            motor = instancia_do_mundo.obter_motor()
            motor.cargas["carga-1"] = CargaMineral(
                "carga-1", "jarosita", 10.0, 100.0, local=LocalDaCarga.EM_ARMAZEM,
            )
            motor.energia.alocar_energia("reserva_estrategica", "transporte", 100)

            id_autorizacao = _autorizar(cliente)
            _iniciar_viagem(cliente, id_autorizacao=id_autorizacao, modo=modo)
            for _ in range(20):
                motor.avancar_ciclo(1)
            qualidades[modo] = motor.cargas["carga-1"].qualidade

    assert qualidades["rapido"] > qualidades["economico"]
```

Garantir que o topo do arquivo importa `CargaMineral` e `LocalDaCarga` de `mundo.dominio.cargas`, e que o helper `_iniciar_viagem` repassa `**campos` para o corpo do POST (ele já aceita overrides).

- [ ] **Step 2: Rodar e confirmar falha**

Run: `.venv/bin/pytest mundo/testes/test_api_transporte.py -v`
Expected: FAIL — duração e custo idênticos entre os modos, e `local` nunca muda.

- [ ] **Step 3: Implementar em `mundo/api/transporte.py`**

Acrescentar aos imports:

```python
from mundo.dominio.cargas import LocalDaCarga
from mundo.dominio.modos import ModoDeTransporte
```

Acrescentar o campo ao modelo:

```python
class RequisicaoDeViagem(BaseModel):
    identificador_da_unidade: str
    identificador_da_rota: str
    identificador_da_carga: str
    id_autorizacao: str
    modo: ModoDeTransporte = ModoDeTransporte.NORMAL
```

Substituir o corpo de `executar()`/`concluir()` dentro de `iniciar_viagem` por:

```python
    def executar() -> None:
        motor.autorizacoes.consumir(requisicao.id_autorizacao, "iniciar_viagem")
        if rota.condicao != CondicaoDaRota.LIVRE:
            raise ValueError("Rota interditada")
        if unidade.viagens_disponiveis <= 0:
            raise ValueError("Sem viagens disponíveis")
        perfil = motor.catalogo_de_modos.obter_transporte(requisicao.modo)
        motor.energia.debitar(CENTRAL, CUSTO_ENERGETICO_VIAGEM * perfil.mult_energia)
        unidade.viagens_disponiveis -= 1
        unidade.estado = EstadoDoRobo.EXECUTANDO
        carga = motor.cargas[requisicao.identificador_da_carga]
        carga.local = LocalDaCarga.EM_TRANSITO
        carga.mult_degradacao_local = perfil.mult_degradacao
        duracao = max(1, round(rota.tempo_base * perfil.mult_duracao))
        ciclo_chegada = motor.ciclo_atual + duracao

        def concluir() -> None:
            carga_em_transito = motor.cargas[requisicao.identificador_da_carga]
            carga_em_transito.local = LocalDaCarga.EM_ARMAZEM
            carga_em_transito.mult_degradacao_local = 1.0
            unidade.estado = EstadoDoRobo.RETORNANDO
            motor.eventos.publicar(
                "transporte_concluido",
                motor.ciclo_atual,
                {
                    "unidade": unidade.identificador,
                    "carga": carga_em_transito.identificador,
                    "modo": requisicao.modo.value,
                },
            )

        motor.agendar_efeito(ciclo_chegada, concluir)
```

A chamada `carga.degradar(taxa_degradacao=rota.risco, fator_contexto=1.0)` desaparece: a degradação agora é contínua e vive no tick.

- [ ] **Step 4: Rodar e confirmar passa**

Run: `.venv/bin/pytest mundo/testes/test_api_transporte.py -v`
Expected: PASS. O teste pré-existente que afirma `qualidade == 90.0 - rota.risco` após a viagem precisa mudar: a degradação pontual não existe mais. Substitua a asserção por `motor.cargas["carga-1"].qualidade < 90.0` mais a verificação de que `local` voltou a `EM_ARMAZEM`.

- [ ] **Step 5: Commit**

```bash
git add mundo/api/transporte.py mundo/testes/test_api_transporte.py
git commit -m "feat: add transport modes trading energy, duration and degradation"
```

---

### Task 6: Transições de local em armazenagem e pesquisa

**Files:**
- Modify: `mundo/api/armazenagem.py`
- Modify: `mundo/api/pesquisa.py`
- Test: `mundo/testes/test_api_armazenagem.py`
- Test: `mundo/testes/test_api_pesquisa.py`

**Interfaces:**
- Consumes: `LocalDaCarga` (Task 2).
- Produces: nenhuma assinatura nova; `receber_carga` passa a mover a carga para `EM_ARMAZEM` e `preparar_distribuicao` para `ENTREGUE` antes de removê-la.

- [ ] **Step 1: Escrever os testes falhando**

```python
# acrescentar em mundo/testes/test_api_armazenagem.py
def test_receber_carga_move_a_carga_para_o_armazem():
    from mundo.dominio.cargas import LocalDaCarga

    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        _receber_carga(cliente)
        motor.avancar_ciclo(1)

        assert motor.cargas["carga-1"].local == LocalDaCarga.EM_ARMAZEM
```

```python
# acrescentar em mundo/testes/test_api_pesquisa.py
def test_preparar_distribuicao_marca_a_carga_como_entregue_antes_de_remove_la():
    from mundo.dominio.cargas import LocalDaCarga

    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 100.0)
        locais_publicados = []
        motor.eventos.assinar(
            lambda evento: locais_publicados.append(motor.cargas["carga-1"].local)
            if evento.tipo == "carga_entregue"
            else None,
        )

        _preparar_distribuicao(cliente, id_autorizacao=_autorizar(cliente))
        motor.avancar_ciclo(1)

        assert locais_publicados == [LocalDaCarga.ENTREGUE]
        assert "carga-1" not in motor.cargas
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `.venv/bin/pytest mundo/testes/test_api_armazenagem.py mundo/testes/test_api_pesquisa.py -v`
Expected: FAIL — a carga permanece `EM_JAZIDA` nos dois casos.

- [ ] **Step 3: Implementar em `mundo/api/armazenagem.py`**

Acrescentar ao import: `from mundo.dominio.cargas import LocalDaCarga`

Dentro do `executar()` de `receber_carga`, após `armazem.reservar_espaco(carga.quantidade)`, acrescentar:

```python
        carga.local = LocalDaCarga.EM_ARMAZEM
```

- [ ] **Step 4: Implementar em `mundo/api/pesquisa.py`**

Acrescentar ao import: `from mundo.dominio.cargas import LocalDaCarga`

Dentro do `executar()` de `preparar_distribuicao`, imediatamente antes de `motor.eventos.publicar("carga_entregue", ...)`, acrescentar:

```python
        carga.local = LocalDaCarga.ENTREGUE
```

A remoção `del motor.cargas[...]` continua sendo a última instrução do closure.

- [ ] **Step 5: Rodar e confirmar passa**

Run: `.venv/bin/pytest mundo/testes/test_api_armazenagem.py mundo/testes/test_api_pesquisa.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add mundo/api/armazenagem.py mundo/api/pesquisa.py mundo/testes/test_api_armazenagem.py mundo/testes/test_api_pesquisa.py
git commit -m "feat: move cargo location on storage receipt and delivery"
```

---

### Task 7: Suíte de dominância

**Files:**
- Test: `mundo/testes/test_dominancia_de_modos.py` (criar)

**Interfaces:**
- Consumes: todas as tarefas anteriores.
- Produces: nenhuma — é uma suíte de proteção da calibração.

Esta suíte responde à regra fundamental da spec: se um modo nunca é a melhor escolha em cenário nenhum, ele é burocracia e a calibração está errada. Os testes trabalham direto no domínio, sem HTTP, e comparam **valor entregue por energia gasta**.

- [ ] **Step 1: Escrever a suíte**

```python
# mundo/testes/test_dominancia_de_modos.py
"""Cada modo precisa vencer em pelo menos um cenário.

Se um destes testes falhar após uma recalibração de `modos.json`, o modo
citado deixou de ter razão de existir: nenhuma estratégia o escolheria.
"""
from pathlib import Path

from mundo.dominio.cargas import CargaMineral, LocalDaCarga
from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.dominio.modos import CatalogoDeModos, ModoDeExtracao, ModoDeTransporte

CAMINHO_MINERAIS = Path(__file__).parent.parent / "config" / "minerais.json"
CAMINHO_MODOS = Path(__file__).parent.parent / "config" / "modos.json"

MINERAIS = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_MINERAIS)
MODOS = CatalogoDeModos.carregar_de_arquivo(CAMINHO_MODOS)

QUANTIDADE = 10.0


def _retorno_da_extracao(nome_do_mineral: str, modo: ModoDeExtracao) -> float:
    """Valor entregue por energia gasta, penalizado pelo minério destruído."""
    mineral = MINERAIS.obter(nome_do_mineral)
    perfil = MODOS.obter_extracao(modo)
    energia = (
        mineral.custo_extracao * QUANTIDADE * MODOS.fator_base_de_energia * perfil.mult_energia
    )
    carga = CargaMineral("c", nome_do_mineral, QUANTIDADE, perfil.qualidade_inicial)
    valor = carga.valor_efetivo(mineral.valor_por_unidade)
    desperdicado = QUANTIDADE * (perfil.fator_desperdicio - 1.0)
    valor_perdido = desperdicado * mineral.valor_por_unidade
    return (valor - valor_perdido) / energia


def _melhor_modo_de_extracao(nome_do_mineral: str) -> ModoDeExtracao:
    return max(ModoDeExtracao, key=lambda modo: _retorno_da_extracao(nome_do_mineral, modo))


def _qualidade_apos_viagem(
    nome_do_mineral: str, modo: ModoDeTransporte, tempo_base: int,
) -> float:
    mineral = MINERAIS.obter(nome_do_mineral)
    perfil = MODOS.obter_transporte(modo)
    carga = CargaMineral(
        "c", nome_do_mineral, QUANTIDADE, 100.0, local=LocalDaCarga.EM_TRANSITO,
    )
    ciclos = max(1, round(tempo_base * perfil.mult_duracao))
    perda_por_ciclo = (
        mineral.taxa_degradacao
        * carga.sensibilidade_aplicavel(mineral)
        * MODOS.mult_do_local("em_transito")
        * perfil.mult_degradacao
    )
    for _ in range(ciclos):
        carga.degradar(taxa_degradacao=perda_por_ciclo)
    return carga.qualidade


def _retorno_do_transporte(
    nome_do_mineral: str, modo: ModoDeTransporte, tempo_base: int, custo_base: float,
) -> float:
    mineral = MINERAIS.obter(nome_do_mineral)
    perfil = MODOS.obter_transporte(modo)
    qualidade = _qualidade_apos_viagem(nome_do_mineral, modo, tempo_base)
    valor = QUANTIDADE * mineral.valor_por_unidade * (qualidade / 100)
    return valor / (custo_base * perfil.mult_energia)


def _melhor_modo_de_transporte(
    nome_do_mineral: str, tempo_base: int, custo_base: float = 3.0,
) -> ModoDeTransporte:
    return max(
        ModoDeTransporte,
        key=lambda modo: _retorno_do_transporte(nome_do_mineral, modo, tempo_base, custo_base),
    )


def test_cuidadoso_vence_em_mineral_caro_e_escasso():
    assert _melhor_modo_de_extracao("cristal_marciano_raro") == ModoDeExtracao.CUIDADOSO


def test_agressivo_vence_em_mineral_barato():
    assert _melhor_modo_de_extracao("hematita") == ModoDeExtracao.AGRESSIVO


def test_todo_modo_de_extracao_vence_em_algum_mineral_do_catalogo():
    vencedores = {_melhor_modo_de_extracao(m.nome) for m in MINERAIS.todos()}
    ausentes = set(ModoDeExtracao) - vencedores
    assert not ausentes, f"modos de extração que nunca vencem: {ausentes}"


def test_rapido_vence_transportando_mineral_sensivel_em_rota_longa():
    assert _melhor_modo_de_transporte("gelo_de_agua", tempo_base=20) == ModoDeTransporte.RAPIDO


def test_economico_vence_transportando_mineral_estavel():
    assert _melhor_modo_de_transporte("hematita", tempo_base=5) == ModoDeTransporte.ECONOMICO


def test_todo_modo_de_transporte_vence_em_alguma_combinacao():
    vencedores = set()
    for mineral in MINERAIS.todos():
        for tempo_base in (3, 5, 8, 12, 20, 30):
            vencedores.add(_melhor_modo_de_transporte(mineral.nome, tempo_base))
    ausentes = set(ModoDeTransporte) - vencedores
    assert not ausentes, f"modos de transporte que nunca vencem: {ausentes}"
```

- [ ] **Step 2: Rodar a suíte**

Run: `.venv/bin/pytest mundo/testes/test_dominancia_de_modos.py -v`
Expected: PASS (6 passed).

Se algum modo aparecer como "nunca vence", a calibração de `mundo/config/modos.json` está errada e é ela que deve mudar — **não** o teste. Ajuste os multiplicadores do modo perdedor até ele vencer em pelo menos um cenário, e rode de novo. Registre no relatório quais números mudaram e por quê.

- [ ] **Step 3: Rodar a suíte completa**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: todos passam.

- [ ] **Step 4: Commit**

```bash
git add mundo/testes/test_dominancia_de_modos.py
git commit -m "test: prove every operation mode wins in some scenario"
```

---

### Task 8: Documentar os modos na linguagem do domínio

**Files:**
- Modify: `docs/LINGUAGEM_DO_DOMINIO.md`

**Interfaces:**
- Consumes: terminologia das tarefas 1–7.
- Produces: nenhuma.

- [ ] **Step 1: Acrescentar as entradas ao final de `docs/LINGUAGEM_DO_DOMINIO.md`**

```markdown
## Modo de Operação

Parâmetro opcional de uma ação que escolhe um ponto no trade-off entre energia, tempo, qualidade e desperdício. Extração aceita `cuidadoso`, `normal` e `agressivo`; transporte aceita `economico`, `normal` e `rapido`. O default é sempre `normal`. Nenhum modo é globalmente superior: cada um vence em algum cenário, e a suíte de dominância existe para garantir isso.

## Perfil de Modo

Conjunto de multiplicadores que define um modo, carregado de `mundo/config/modos.json`. Multiplicam os valores base da ação — nunca os substituem — para que modificadores futuros possam compor sobre eles.

## Desperdício

Minério consumido da jazida além do que a carga recebe. Extração agressiva debita `quantidade × fator_desperdicio` da jazida e entrega apenas `quantidade`. A diferença some do mundo permanentemente: é o custo global de uma otimização local.

## Local da Carga

Onde a carga está: `em_jazida` (exposta, sem proteção), `em_armazem`, `em_transito` ou `entregue`. Determina qual sensibilidade do mineral governa a degradação e qual multiplicador de contexto se aplica.

## Degradação por Ciclo

Perda de qualidade aplicada a toda carga a cada ciclo:

`taxa_degradacao do mineral × sensibilidade do local × multiplicador do local × multiplicador de contexto`

Minerais estáveis como a hematita quase não perdem qualidade parados; o gelo de água perde rápido. Urgência é propriedade do mineral, não regra especial.
```

- [ ] **Step 2: Commit**

```bash
git add docs/LINGUAGEM_DO_DOMINIO.md
git commit -m "docs: document operation modes, waste and per-cycle degradation"
```
