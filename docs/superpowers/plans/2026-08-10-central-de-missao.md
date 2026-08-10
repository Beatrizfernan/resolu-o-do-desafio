# Central de Missão — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer existir custar energia, transformar a alocação numa decisão real, e substituir o limite de ciclos por um fim que emerge do esgotamento.

**Architecture:** Cada central consome do próprio saldo a cada tick. Central sem saldo fica dormente e não opera; a missão pode ressuscitar as outras quatro, mas a si mesma não — e é essa assimetria que cria a única armadilha irrecuperável do mundo. A simulação encerra quando nenhuma central paga o próprio consumo, o que torna `duracao_maxima` desnecessária e garante terminação para o Avaliador.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, pytest. Sem dependências novas.

## Global Constraints

- Linguagem de domínio em **português**: classes, métodos, campos, testes, docstrings e comentários. Identificadores de FastAPI/Pydantic (`app`, `router`, `BaseModel`) permanecem em inglês.
- Mensagens de commit em **inglês**, seguindo o estilo do repositório (`git log --oneline -10`).
- `mundo/dominio/` **não importa** de `mundo/motor/`, `mundo/api/` nem `mundo/eventos/`.
- Rotas **nunca** mutam estado de forma síncrona: toda mutação vive dentro do closure `executar()` de um `Comando`, ou dentro de um efeito agendado.
- **Validar antes de mutar, sempre.** `executar()` roda dentro do `try` do motor, então levantar vira `operacao_invalida` e o tick sobrevive — mas o que já foi mutado continua mutado. Esta única regra foi violada cinco vezes no sub-projeto anterior, sempre por uma porta diferente. Tudo que pode falhar acontece antes de qualquer escrita.
- Determinismo: nenhuma fonte nova de aleatoriedade.
- Rodar a suíte inteira (`.venv/bin/pytest mundo/testes -q`) antes de cada commit. Baseline: **241 passam**.
- Preparar arquivos para commit **por nome**. Nunca `git add -A` nem `git add .`.
- Nenhuma asserção existente pode ser enfraquecida. Se um teste falhar, decidir conscientemente se ele codificava o comportamento antigo e registrar a aritmética no relatório.

---

## Estrutura de arquivos

| arquivo | responsabilidade | tarefa |
|---|---|---|
| `mundo/config/operacao.json` (novo) | os dois custos | 1 |
| `mundo/dominio/operacao.py` (novo) | `CatalogoDeOperacao` | 1 |
| `mundo/dominio/energia.py` | `esta_operante` | 2 |
| `mundo/motor/motor_de_simulacao.py` | consumo no tick, encerramento, fim de `duracao_maxima` | 3, 4 |
| `mundo/api/missao.py` | alocação como comando, autorização paga, `resetar-mundo` | 5 |
| `mundo/api/{extracao,armazenagem,transporte,pesquisa}.py` | exigir central operante | 6 |
| `mundo/testes/test_consumo_das_centrais.py` (novo) | consumo e dormência | 3 |
| `mundo/testes/test_encerramento.py` (novo) | fim por esgotamento e terminação | 4 |
| `mundo/testes/test_deadlock_da_missao.py` (novo) | a armadilha e sua assimetria | 7 |
| `docs/LINGUAGEM_DO_DOMINIO.md` | entradas novas | 8 |

---

### Task 1: Catálogo de operação

**Files:**
- Create: `mundo/config/operacao.json`
- Create: `mundo/dominio/operacao.py`
- Test: `mundo/testes/test_catalogo_de_operacao.py`

**Interfaces:**
- Consumes: nada.
- Produces: `CatalogoDeOperacao.carregar_de_arquivo(caminho: Path) -> CatalogoDeOperacao`, com os atributos `consumo_por_ciclo_da_central: float` e `custo_de_autorizacao: float`.

Segue o padrão de `CatalogoDeArmazenagem` em `mundo/dominio/armazenagem.py` — leia-o primeiro; é o mesmo formato.

- [ ] **Step 1: Escrever o teste que falha**

Criar `mundo/testes/test_catalogo_de_operacao.py`:

```python
from pathlib import Path

import pytest

from mundo.dominio.operacao import CatalogoDeOperacao

CAMINHO = Path(__file__).parent.parent / "config" / "operacao.json"


def test_carrega_os_dois_custos_do_arquivo():
    catalogo = CatalogoDeOperacao.carregar_de_arquivo(CAMINHO)

    assert catalogo.consumo_por_ciclo_da_central == 0.05
    assert catalogo.custo_de_autorizacao == 0.2


def test_o_saldo_inicial_de_uma_central_dura_cerca_de_duzentos_ciclos():
    """É esta razão que decide quando a armadilha dispara.

    Uma central começa com 10. Se o consumo faz isso durar muito, a
    armadilha nunca dispara e o mecanismo é decorativo; se durar pouco, o
    mundo vira punitivo. Duzentos ciclos é cerca de metade de uma execução
    típica — tarde o bastante para o participante desatento já ter se
    comprometido, cedo o bastante para ainda restar execução a perder.
    """
    catalogo = CatalogoDeOperacao.carregar_de_arquivo(CAMINHO)

    assert 10.0 / catalogo.consumo_por_ciclo_da_central == pytest.approx(200.0)


def test_autorizacao_custa_alguns_ciclos_de_existencia():
    """A autorização precisa pesar mais que existir, e muito menos que operar.

    Se custasse menos que um ciclo de consumo, agrupar operações não valeria
    a pena. Se custasse como uma extração, autorizar viraria a despesa
    principal e o resto do mundo perderia relevância.
    """
    catalogo = CatalogoDeOperacao.carregar_de_arquivo(CAMINHO)
    ciclos_equivalentes = catalogo.custo_de_autorizacao / catalogo.consumo_por_ciclo_da_central

    assert 2.0 <= ciclos_equivalentes <= 10.0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest mundo/testes/test_catalogo_de_operacao.py -q`
Expected: FAIL com `ModuleNotFoundError: mundo.dominio.operacao`.

- [ ] **Step 3: Implementar**

Criar `mundo/config/operacao.json`:

```json
{
  "consumo_por_ciclo_da_central": 0.05,
  "custo_de_autorizacao": 0.2
}
```

Criar `mundo/dominio/operacao.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CatalogoDeOperacao:
    """O que custa existir e o que custa autorizar.

    Existir por ciclo é o que impede a indecisão de ser gratuita: um robô
    parado ainda consome. Autorizar é o que dá preço a operar em muitas
    chamadas pequenas em vez de agrupar.
    """

    consumo_por_ciclo_da_central: float
    custo_de_autorizacao: float

    @classmethod
    def carregar_de_arquivo(cls, caminho: Path) -> "CatalogoDeOperacao":
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return cls(
            consumo_por_ciclo_da_central=dados["consumo_por_ciclo_da_central"],
            custo_de_autorizacao=dados["custo_de_autorizacao"],
        )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: PASS, 244.

- [ ] **Step 5: Commit**

```bash
git add mundo/config/operacao.json mundo/dominio/operacao.py mundo/testes/test_catalogo_de_operacao.py
git commit -m "feat: add the operating cost catalog"
```

---

### Task 2: Central dormente

**Files:**
- Modify: `mundo/dominio/energia.py`
- Test: `mundo/testes/test_energia.py`

**Interfaces:**
- Consumes: nada.
- Produces: `GerenciadorDeEnergia.esta_operante(central: str) -> bool` e `GerenciadorDeEnergia.debitar_ate_o_saldo(central: str, quantidade: float) -> float`, que devolve quanto foi de fato debitado.

Uma central é operante enquanto tiver saldo estritamente positivo. `debitar_ate_o_saldo` existe porque o consumo por ciclo não pode levantar — uma central que não cobre o consumo simplesmente entrega o que resta e fica dormente. `debitar` continua levantando, porque uma **operação** que não cabe no saldo tem que ser rejeitada.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `mundo/testes/test_energia.py`:

```python
def test_central_com_saldo_esta_operante():
    energia = GerenciadorDeEnergia(["extracao"], energia_inicial_por_central=10)

    assert energia.esta_operante("extracao")


def test_central_sem_saldo_nao_esta_operante():
    energia = GerenciadorDeEnergia(["extracao"], energia_inicial_por_central=10)
    energia.debitar("extracao", 10.0)

    assert not energia.esta_operante("extracao")


def test_debitar_ate_o_saldo_devolve_o_que_conseguiu_debitar():
    """O consumo por ciclo não pode levantar.

    Uma operação que não cabe no saldo é rejeitada, e isso é certo. Mas o
    consumo é involuntário: a central não escolheu existir naquele ciclo.
    Ela entrega o que resta e fica dormente.
    """
    energia = GerenciadorDeEnergia(["extracao"], energia_inicial_por_central=10)
    energia.debitar("extracao", 9.97)

    debitado = energia.debitar_ate_o_saldo("extracao", 0.05)

    assert debitado == pytest.approx(0.03)
    assert energia.consultar_energia("extracao") == pytest.approx(0.0)
    assert not energia.esta_operante("extracao")


def test_debitar_ate_o_saldo_de_central_seca_nao_debita_nada():
    """Central dormente não acumula dívida."""
    energia = GerenciadorDeEnergia(["extracao"], energia_inicial_por_central=10)
    energia.debitar("extracao", 10.0)

    assert energia.debitar_ate_o_saldo("extracao", 0.05) == 0.0
    assert energia.consultar_energia("extracao") == pytest.approx(0.0)


def test_alocar_ressuscita_central_dormente():
    energia = GerenciadorDeEnergia(["extracao"], energia_inicial_por_central=10)
    energia.debitar("extracao", 10.0)

    energia.alocar_energia(GerenciadorDeEnergia.RESERVA, "extracao", 5.0)

    assert energia.esta_operante("extracao")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest mundo/testes/test_energia.py -q`
Expected: FAIL com `AttributeError: 'GerenciadorDeEnergia' object has no attribute 'esta_operante'`.

- [ ] **Step 3: Implementar**

Em `mundo/dominio/energia.py`, acrescentar à classe:

```python
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
        debitado = min(max(0.0, quantidade), self._saldos[central])
        self._saldos[central] -= debitado
        return debitado
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: PASS, 249.

- [ ] **Step 5: Commit**

```bash
git add mundo/dominio/energia.py mundo/testes/test_energia.py
git commit -m "feat: a central with no balance goes dormant"
```

---

### Task 3: Consumo por ciclo no tick

**Files:**
- Modify: `mundo/motor/motor_de_simulacao.py`
- Test: `mundo/testes/test_consumo_das_centrais.py` (novo)

**Interfaces:**
- Consumes: `CatalogoDeOperacao` (Task 1), `debitar_ate_o_saldo` e `esta_operante` (Task 2).
- Produces: `motor.catalogo_de_operacao`, e o passo `_cobrar_consumo_das_centrais()` no tick.

O catálogo é construído como `catalogo_de_armazenagem` já é: parâmetro opcional no `__init__` com fallback para `CatalogoDeOperacao.carregar_de_arquivo(Path(__file__).parent.parent / "config" / "operacao.json")`. Leia o construtor antes de escrever, e siga o formato exato que está lá.

- [ ] **Step 1: Escrever os testes que falham**

Criar `mundo/testes/test_consumo_das_centrais.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.operacao import CatalogoDeOperacao

CAMINHO_OPERACAO = Path(__file__).parent.parent / "config" / "operacao.json"
CUSTOS = CatalogoDeOperacao.carregar_de_arquivo(CAMINHO_OPERACAO)
CENTRAIS = ("extracao", "armazenagem", "transporte", "pesquisa", "missao")


def test_cada_central_paga_o_proprio_consumo_a_cada_ciclo():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        antes = {c: motor.energia.consultar_energia(c) for c in CENTRAIS}

        motor.avancar_ciclo(1)

        for central in CENTRAIS:
            gasto = antes[central] - motor.energia.consultar_energia(central)
            assert gasto == pytest.approx(CUSTOS.consumo_por_ciclo_da_central), central


def test_a_reserva_nao_paga_consumo():
    """A reserva só guarda.

    É isso que garante o encerramento: as cinco centrais drenam e a execução
    acaba mesmo com a reserva cheia, que é exatamente o desfecho do deadlock.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        reserva = motor.energia.RESERVA
        antes = motor.energia.consultar_energia(reserva)

        motor.avancar_ciclo(5)

        assert motor.energia.consultar_energia(reserva) == pytest.approx(antes)


def test_central_dormente_nao_acumula_divida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        motor.energia.debitar("extracao", motor.energia.consultar_energia("extracao"))

        motor.avancar_ciclo(10)

        assert motor.energia.consultar_energia("extracao") == pytest.approx(0.0)


def test_central_seca_no_ciclo_esperado_sem_nenhuma_alocacao():
    """Duzentos ciclos é onde a armadilha foi calibrada para disparar."""
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        ciclos_ate_secar = int(10.0 / CUSTOS.consumo_por_ciclo_da_central)

        motor.avancar_ciclo(ciclos_ate_secar - 1)
        assert motor.energia.esta_operante("missao")

        motor.avancar_ciclo(1)
        assert not motor.energia.esta_operante("missao")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest mundo/testes/test_consumo_das_centrais.py -q`
Expected: FAIL — nenhuma energia é debitada, o primeiro teste falha na comparação.

- [ ] **Step 3: Implementar**

Em `mundo/motor/motor_de_simulacao.py`, importar junto dos demais imports de domínio:

```python
from mundo.dominio.operacao import CatalogoDeOperacao
```

Acrescentar `catalogo_de_operacao: CatalogoDeOperacao | None = None` à assinatura do `__init__`, e no corpo, ao lado de `self.catalogo_de_armazenagem`:

```python
        self.catalogo_de_operacao = catalogo_de_operacao or CatalogoDeOperacao.carregar_de_arquivo(
            Path(__file__).parent.parent / "config" / "operacao.json"
        )
```

Em `_processar_um_ciclo`, acrescentar a chamada depois de `self._cobrar_manutencao_dos_armazens()`:

```python
        self._cobrar_consumo_das_centrais()
```

E o método:

```python
    def _cobrar_consumo_das_centrais(self) -> None:
        """Existir custa: cada central paga do próprio saldo, todo ciclo.

        É o que impede a indecisão de ser gratuita — um robô parado ainda
        consome, então adiar a alocação tem preço sem precisar de nenhuma
        regra que proíba adiar.

        Cobra com `debitar_ate_o_saldo` porque o consumo é involuntário: a
        central não escolheu existir naquele ciclo, então não pode ser
        rejeitada por não poder pagar. Quem não cobre entrega o que resta e
        fica dormente, sem acumular dívida.
        """
        consumo = self.catalogo_de_operacao.consumo_por_ciclo_da_central
        for central in CENTRAIS:
            self.energia.debitar_ate_o_saldo(central, consumo)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: PASS, 253. Testes existentes que avançam muitos ciclos podem começar a falhar por energia — se acontecer, verificar se o teste depende de saldo e ajustar a **alocação do setup**, nunca a asserção. Registrar no relatório quais foram tocados.

- [ ] **Step 5: Commit**

```bash
git add mundo/motor/motor_de_simulacao.py mundo/testes/test_consumo_das_centrais.py
git commit -m "feat: existing costs energy every cycle"
```

---

### Task 4: Encerramento por esgotamento

**Files:**
- Modify: `mundo/motor/motor_de_simulacao.py`
- Modify: `mundo/api/missao.py`
- Modify: `mundo/api/app.py`
- Test: `mundo/testes/test_encerramento.py` (novo)

**Interfaces:**
- Consumes: `esta_operante` (Task 2), `_cobrar_consumo_das_centrais` (Task 3).
- Produces: `motor.encerrada: bool`, o evento `simulacao_encerrada`, e `ConfiguracaoDaSimulacao` **sem** `duracao_maxima`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `mundo/testes/test_encerramento.py`:

```python
import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo


def test_simulacao_encerra_quando_nenhuma_central_paga_o_consumo():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        encerramentos = []
        motor.eventos.assinar(
            lambda e: encerramentos.append(e) if e.tipo == "simulacao_encerrada" else None
        )

        motor.avancar_ciclo(500)

        assert motor.encerrada
        assert encerramentos, "encerrar precisa publicar simulacao_encerrada"


def test_avancar_ciclo_e_no_op_depois_de_encerrada():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        motor.avancar_ciclo(500)
        ciclo_no_fim = motor.ciclo_atual

        motor.avancar_ciclo(50)

        assert motor.ciclo_atual == ciclo_no_fim


def test_toda_execucao_termina():
    """O Avaliador depende disto para rodar cem simulações.

    Sem alocação nenhuma, as cinco centrais drenam os 10 iniciais e a
    execução morre. Com alocação, morre depois. Em nenhum caso roda para
    sempre — a energia total só diminui.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()

        motor.avancar_ciclo(10_000)

        assert motor.encerrada


def test_o_evento_de_encerramento_relata_o_que_sobrou():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        capturados = []
        motor.eventos.assinar(
            lambda e: capturados.append(e) if e.tipo == "simulacao_encerrada" else None
        )

        motor.avancar_ciclo(500)

        dados = capturados[0].dados
        assert dados["ciclo"] == motor.ciclo_atual
        assert dados["faturamento_total"] == pytest.approx(motor.faturamento_total)
        # Ninguém alocou nada, então a reserva inteira ficou encalhada.
        assert dados["energia_encalhada"] > 900.0


def test_resetar_mundo_aceita_pedido_sem_duracao_maxima():
    """O campo sai do contrato sem quebrar quem já o enviava.

    `duracao_maxima` esteve no corpo desde o início e nunca fez nada.
    Removê-lo não pode derrubar cliente de participante, então o pedido é
    aceito com ou sem ele.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        assert cliente.post("/missao/resetar-mundo", json={"semente": 7}).status_code == 200
        resposta = cliente.post(
            "/missao/resetar-mundo", json={"semente": 7, "duracao_maxima": 100},
        )
        assert resposta.status_code == 200
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest mundo/testes/test_encerramento.py -q`
Expected: FAIL com `AttributeError: 'MotorDeSimulacao' object has no attribute 'encerrada'`.

- [ ] **Step 3: Implementar**

Em `mundo/motor/motor_de_simulacao.py`:

Remover `duracao_maxima: int` de `ConfiguracaoDaSimulacao`.

No `__init__`, acrescentar:

```python
        self.encerrada: bool = False
```

Em `avancar_ciclo`, parar cedo se já encerrou:

```python
    def avancar_ciclo(self, quantidade: int = 1) -> None:
        for _ in range(quantidade):
            if self.encerrada:
                return
            self._processar_um_ciclo()
```

Ao final de `_processar_um_ciclo`, depois de `_cobrar_consumo_das_centrais()`:

```python
        self._verificar_encerramento()
```

E o método:

```python
    def _verificar_encerramento(self) -> None:
        """O fim é consequência do esgotamento, não constante escolhida.

        Quando nenhuma central paga o próprio consumo, não há mais nada que o
        mundo possa fazer: as dormentes não operam, e sem a missão ninguém
        pode ser ressuscitado. Encerrar aqui também é o que garante que toda
        execução termina, do que o Avaliador depende.

        A energia encalhada é relatada porque é o placar do erro: quem
        deixou a missão secar morre com a reserva quase intacta.
        """
        if self.encerrada:
            return
        consumo = self.catalogo_de_operacao.consumo_por_ciclo_da_central
        if any(self.energia.consultar_energia(central) >= consumo for central in CENTRAIS):
            return
        self.encerrada = True
        encalhada = sum(
            self.energia.consultar_energia(central)
            for central in (*CENTRAIS, self.energia.RESERVA)
        )
        self.eventos.publicar(
            tipo="simulacao_encerrada",
            ciclo=self.ciclo_atual,
            dados={
                "ciclo": self.ciclo_atual,
                "faturamento_total": self.faturamento_total,
                "energia_encalhada": encalhada,
            },
        )
```

Em `mundo/api/missao.py`, tornar o campo opcional e parar de repassá-lo:

```python
class RequisicaoDeResetarMundo(BaseModel):
    semente: int
    duracao_maxima: int | None = None
```

e a construção passa a ser `ConfiguracaoDaSimulacao(semente=requisicao.semente)`.

Em `mundo/api/app.py`, remover `duracao_maxima=5000` da construção.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: PASS. Os testes que constroem `ConfiguracaoDaSimulacao(semente=..., duracao_maxima=50)` vão quebrar — são `test_desgaste.py`, `test_degradacao.py`, `test_motor_de_simulacao.py` e `test_determinismo.py`. Remover o argumento é mudança de chamada, não de asserção.

**Atenção:** testes que avançam centenas de ciclos podem agora encerrar no meio. Se algum falhar por isso, o setup precisa alocar energia — e isso é correção legítima de preparação. Não afrouxar asserção alguma; registrar cada caso no relatório com o motivo.

- [ ] **Step 5: Commit**

```bash
git add mundo/motor/motor_de_simulacao.py mundo/api/missao.py mundo/api/app.py mundo/testes/
git commit -m "feat: the simulation ends when energy runs out"
```

---

### Task 5: Missão paga para autorizar, e aloca por comando

**Files:**
- Modify: `mundo/api/missao.py`
- Test: `mundo/testes/test_api_missao.py`

**Interfaces:**
- Consumes: `esta_operante` (Task 2), `motor.catalogo_de_operacao` (Task 3).
- Produces: nenhuma assinatura nova; muda o comportamento de `alocar-energia` e `autorizar-missao`.

Duas mudanças no mesmo arquivo:

`alocar-energia` hoje muta de forma síncrona, fora de qualquer `Comando.executar()`, violando o invariante que o resto do projeto mantém. Passa a ser comando enfileirado.

`autorizar-missao` passa a debitar `custo_de_autorizacao` da missão, e a recusar se ela estiver dormente.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `mundo/testes/test_api_missao.py`:

```python
def test_autorizar_debita_o_custo_da_missao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        antes = motor.energia.consultar_energia("missao")

        cliente.post("/missao/autorizar-missao", json={
            "operacao": "receber_carga", "central_solicitante": "armazenagem",
        })

        gasto = antes - motor.energia.consultar_energia("missao")
        assert gasto == pytest.approx(motor.catalogo_de_operacao.custo_de_autorizacao)


def test_missao_dormente_nao_emite_autorizacao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.debitar("missao", motor.energia.consultar_energia("missao"))

        resposta = cliente.post("/missao/autorizar-missao", json={
            "operacao": "receber_carga", "central_solicitante": "armazenagem",
        })

        assert resposta.status_code == 400


def test_alocar_energia_so_muta_no_ciclo():
    """Nenhuma rota muta estado de forma síncrona — nem esta.

    Era a única exceção no projeto inteiro. Enfileirada como comando, a
    alocação passa a valer no tick, como todo o resto.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        antes = motor.energia.consultar_energia("extracao")

        cliente.post("/missao/alocar-energia", json={"destino": "extracao", "quantidade": 50})
        assert motor.energia.consultar_energia("extracao") == pytest.approx(antes)

        motor.avancar_ciclo(1)
        consumo = motor.catalogo_de_operacao.consumo_por_ciclo_da_central
        assert motor.energia.consultar_energia("extracao") == pytest.approx(antes + 50 - consumo)


def test_missao_dormente_nao_aloca():
    """Esta linha é o mecanismo inteiro do deadlock."""
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.debitar("missao", motor.energia.consultar_energia("missao"))
        antes = motor.energia.consultar_energia("extracao")

        cliente.post("/missao/alocar-energia", json={"destino": "extracao", "quantidade": 50})
        motor.avancar_ciclo(1)

        assert motor.energia.consultar_energia("extracao") < antes + 50
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest mundo/testes/test_api_missao.py -q`
Expected: FAIL — nada é debitado ao autorizar, e a alocação já vale antes do tick.

- [ ] **Step 3: Implementar**

Em `mundo/api/missao.py`, substituir `alocar_energia`:

```python
@router.post("/alocar-energia")
async def alocar_energia(requisicao: RequisicaoDeAlocacao) -> dict:
    motor = obter_motor()

    def executar() -> None:
        if not motor.energia.esta_operante(CENTRAL):
            raise ValueError("Central de missão dormente: não há quem aloque")
        motor.energia.alocar_energia(
            GerenciadorDeEnergia.RESERVA, requisicao.destino, requisicao.quantidade,
        )

    motor.enfileirar_comando(Comando("alocar_energia", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}
```

Acrescentar `CENTRAL = "missao"` no topo do arquivo e importar `Comando` de `mundo.motor.comandos`.

**Atenção:** a resposta muda de `{"saldo": ...}` para `{"aceito": True}`, porque o saldo ainda não mudou quando a rota responde. É consequência necessária de enfileirar; os testes existentes que leem `saldo` precisam ler o saldo do motor depois de avançar o ciclo.

E `autorizar_missao`:

```python
@router.post("/autorizar-missao")
async def autorizar_missao(requisicao: RequisicaoDeAutorizacao) -> dict:
    motor = obter_motor()
    if not motor.energia.esta_operante(CENTRAL):
        raise HTTPException(status_code=400, detail="Central de missão dormente")
    try:
        motor.energia.debitar(CENTRAL, motor.catalogo_de_operacao.custo_de_autorizacao)
    except Exception as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    autorizacao = motor.autorizacoes.emitir(requisicao.operacao, requisicao.central_solicitante)
    return {"id_autorizacao": autorizacao.identificador}
```

**Atenção:** esta rota permanece síncrona de propósito — ela devolve o identificador que o chamador usa imediatamente, então não pode ser enfileirada sem quebrar todo o resto do projeto. Registrar como exceção conhecida no relatório, e não estendê-la a mais nada.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: PASS. Toda a suíte pede autorizações, então o consumo delas passa a drenar a missão em muitos testes. Se algum falhar por saldo, alocar mais no setup é correção legítima. Nenhuma asserção muda.

- [ ] **Step 5: Commit**

```bash
git add mundo/api/missao.py mundo/testes/
git commit -m "feat: authorising costs energy and allocating goes through the tick"
```

---

### Task 6: Central dormente não opera

**Files:**
- Modify: `mundo/api/extracao.py`, `mundo/api/armazenagem.py`, `mundo/api/transporte.py`, `mundo/api/pesquisa.py`
- Test: `mundo/testes/test_consumo_das_centrais.py`

**Interfaces:**
- Consumes: `esta_operante` (Task 2).
- Produces: nenhuma assinatura nova; muda a pré-condição de toda rota que executa operação.

Cada arquivo já tem `CENTRAL` no topo. Em cada `executar()` que debita energia, acrescentar como **primeira** verificação:

```python
        if not motor.energia.esta_operante(CENTRAL):
            raise ValueError(f"Central {CENTRAL} dormente")
```

Antes de qualquer mutação e antes do débito — a regra que o sub-projeto anterior teve que aprender cinco vezes.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar a `mundo/testes/test_consumo_das_centrais.py`:

```python
def test_central_dormente_nao_executa_operacao():
    """Sem saldo não se opera, e a recusa vem antes de qualquer mutação."""
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.debitar("extracao", motor.energia.consultar_energia("extracao"))
        jazida = next(iter(motor.jazidas.values()))
        antes = jazida.quantidade_disponivel
        invalidas = []
        motor.eventos.assinar(
            lambda e: invalidas.append(e) if e.tipo == "operacao_invalida" else None
        )

        cliente.post("/extracao/iniciar-extracao", json={
            "identificador_da_unidade": "mineradora-1",
            "identificador_da_jazida": jazida.identificador,
            "quantidade": 2.0,
        })
        motor.avancar_ciclo(8)

        assert invalidas, "central dormente deveria recusar"
        motivos = [e.dados["motivo"] for e in invalidas]
        assert any("dormente" in m for m in motivos), motivos
        assert jazida.quantidade_disponivel == pytest.approx(antes)


def test_alocar_ressuscita_e_a_central_volta_a_operar():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.debitar("extracao", motor.energia.consultar_energia("extracao"))
        assert not motor.energia.esta_operante("extracao")

        cliente.post("/missao/alocar-energia", json={"destino": "extracao", "quantidade": 50})
        motor.avancar_ciclo(1)

        assert motor.energia.esta_operante("extracao")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest mundo/testes/test_consumo_das_centrais.py -q`
Expected: FAIL — a extração acontece mesmo com a central seca, porque `debitar` levanta só quando a quantidade excede o saldo, e a jazida já foi debitada antes disso em alguns caminhos.

- [ ] **Step 3: Implementar**

Acrescentar a verificação nos quatro arquivos, como primeira linha de cada `executar()` que debita energia. As rotas que só leem estado não mudam.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mundo/api/ mundo/testes/test_consumo_das_centrais.py
git commit -m "feat: a dormant central refuses to operate"
```

---

### Task 7: A armadilha e sua assimetria

**Files:**
- Create: `mundo/testes/test_deadlock_da_missao.py`
- Modify: `mundo/config/operacao.json` (só se a calibração falhar)

**Interfaces:**
- Consumes: tudo das tarefas 1 a 6.
- Produces: nada.

Esta é a tarefa que prova que o mecanismo faz o que o desenho promete. **Se um teste falhar, o que muda é `operacao.json`, nunca a asserção.**

- [ ] **Step 1: Escrever os testes**

Criar `mundo/testes/test_deadlock_da_missao.py`:

```python
"""A missão é a única armadilha irrecuperável do mundo — e é barata de evitar.

Estes testes provam três coisas: que ignorar a missão mata a execução no meio,
que alocar um pouco para ela evita isso por completo, e que só ela é fatal —
as outras quatro centrais são ressuscitáveis.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.operacao import CatalogoDeOperacao

CAMINHO_OPERACAO = Path(__file__).parent.parent / "config" / "operacao.json"
CUSTOS = CatalogoDeOperacao.carregar_de_arquivo(CAMINHO_OPERACAO)
CICLOS_ATE_SECAR = int(10.0 / CUSTOS.consumo_por_ciclo_da_central)


def test_quem_ignora_a_missao_perde_a_cauda_da_execucao():
    """A armadilha existe, e dispara no meio.

    Sem nenhuma alocação a missão seca, a reserva congela, e a execução morre
    com quase toda a energia do mundo por gastar. É o piso do desafio.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()

        motor.avancar_ciclo(10_000)

        assert motor.encerrada
        assert motor.ciclo_atual < CICLOS_ATE_SECAR * 2, (
            f"a execução durou {motor.ciclo_atual} ciclos: a armadilha não disparou"
        )
        assert motor.energia.consultar_energia(motor.energia.RESERVA) > 900.0, (
            "a reserva deveria ficar encalhada"
        )


def test_alocar_para_a_missao_evita_a_armadilha_por_completo():
    """E é barata de evitar: uma alocação modesta, cedo, basta."""
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()

        cliente.post("/missao/alocar-energia", json={"destino": "missao", "quantidade": 40})
        motor.avancar_ciclo(1)
        motor.avancar_ciclo(CICLOS_ATE_SECAR * 2)

        assert motor.energia.esta_operante("missao"), (
            "quarenta de energia deveria sustentar a missão bem além do ponto da armadilha"
        )


def test_so_a_missao_e_fatal():
    """Uma armadilha, não cinco.

    Extração seca é erro recuperável: a missão a traz de volta. Missão seca
    não volta de jeito nenhum, porque não existe quem a ressuscite.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()

        motor.energia.debitar("extracao", motor.energia.consultar_energia("extracao"))
        cliente.post("/missao/alocar-energia", json={"destino": "extracao", "quantidade": 30})
        motor.avancar_ciclo(1)
        assert motor.energia.esta_operante("extracao"), "extração deveria ser ressuscitável"

        motor.energia.debitar("missao", motor.energia.consultar_energia("missao"))
        cliente.post("/missao/alocar-energia", json={"destino": "missao", "quantidade": 30})
        motor.avancar_ciclo(1)
        assert not motor.energia.esta_operante("missao"), (
            "a missão não pode ressuscitar a si mesma"
        )


def test_alocar_tudo_no_ciclo_um_continua_viavel():
    """Alocar bem não pode ser obrigatório para produzir qualquer coisa.

    Uma estratégia ingênua — distribuir tudo no início e nunca mais mexer —
    precisa continuar operando. Se ela morrer, o mecanismo virou pedágio e a
    calibração é que está errada, não o teste.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        for central in ("extracao", "armazenagem", "transporte", "pesquisa", "missao"):
            cliente.post("/missao/alocar-energia", json={"destino": central, "quantidade": 150})
        motor.avancar_ciclo(1)

        motor.avancar_ciclo(CICLOS_ATE_SECAR * 2)

        assert not motor.encerrada, (
            "distribuir tudo no início deveria continuar sendo uma estratégia viável"
        )
```

- [ ] **Step 2: Rodar**

Run: `.venv/bin/pytest mundo/testes/test_deadlock_da_missao.py -q`

- [ ] **Step 3: Se algum falhar, recalibrar `operacao.json`**

**Nunca ajustar a asserção.** Diagnóstico:

- Se `test_quem_ignora_a_missao...` falha porque a execução durou demais, `consumo_por_ciclo_da_central` está baixo demais — a armadilha não dispara e o mecanismo é decorativo.
- Se `test_alocar_tudo_no_ciclo_um...` falha, o consumo está alto demais e o mundo virou punitivo. Baixar.
- Se não houver valor que satisfaça os dois, reportar BLOCKED com os números e a faixa varrida. É achado legítimo: significaria que um consumo único não serve para as duas propriedades.

- [ ] **Step 4: Mutation-check**

Zerar `consumo_por_ciclo_da_central` na cópia de trabalho e confirmar que `test_quem_ignora_a_missao...` falha. Restaurar e confirmar `git diff mundo/config/operacao.json` vazio. Registrar no relatório.

- [ ] **Step 5: Commit**

```bash
git add mundo/testes/test_deadlock_da_missao.py mundo/config/operacao.json
git commit -m "test: prove the mission trap fires, is cheap to avoid, and is the only fatal one"
```

---

### Task 8: Documentação no glossário

**Files:**
- Modify: `docs/LINGUAGEM_DO_DOMINIO.md`

**Interfaces:**
- Consumes: valores finais de `mundo/config/operacao.json`.
- Produces: nada.

- [ ] **Step 1: Confirmar os números**

A Task 7 pode ter recalibrado. Ler `mundo/config/operacao.json` e usar o que está lá.

Run: `cat mundo/config/operacao.json`

- [ ] **Step 2: Escrever as entradas**

Acrescentar ao final de `docs/LINGUAGEM_DO_DOMINIO.md`, seguindo o estilo das entradas existentes:

- **Consumo por Ciclo** — cada central paga do próprio saldo, todo ciclo, o valor de `consumo_por_ciclo_da_central`. A reserva não paga. Existir custa, e é isso que impede a indecisão de ser gratuita: um robô parado ainda consome, então adiar tem preço sem nenhuma regra proibindo adiar.
- **Central Dormente** — central sem saldo não executa operação nem paga consumo, e não acumula dívida. Alocar a traz de volta.
- **Armadilha da Missão** — a missão pode ressuscitar as outras quatro, mas não a si mesma: sem saldo ela não aloca, e sem alocação ninguém recebe energia. Uma armadilha, não cinco. Detectável antes de disparar em `/missao/estado`, e barata de evitar. Citar em quantos ciclos os 10 iniciais secam.
- **Encerramento** — a simulação acaba quando nenhuma central paga o próprio consumo, e publica `simulacao_encerrada` com ciclo, faturamento e energia encalhada. O fim é consequência, não constante: `duracao_maxima` foi removida por ser campo que nunca foi lido. Isso garante terminação, do que o Avaliador depende.
- **Custo de Autorização** — autorizar debita `custo_de_autorizacao` da missão. Como `receber-carga` aceita uma lista de cargas, agrupar operações numa chamada passa a valer a pena — o que devolve relevância ao tamanho do lote, que o sub-projeto da armazenagem tinha registrado como decisão morta.

Acrescentar também, à entrada existente que registra que o tamanho do lote deixou de ser decisão, uma frase apontando para essa reversão parcial.

- [ ] **Step 3: Commit**

```bash
git add docs/LINGUAGEM_DO_DOMINIO.md
git commit -m "docs: document per-cycle upkeep, dormancy and the mission trap"
```

---

## Auto-revisão do plano

**Cobertura da spec:**

| seção da spec | tarefa |
|---|---|
| §2 existir custa | 3 |
| §2 central dormente, ressuscitável | 2, 6 |
| §2 missão irrecuperável | 5, 7 |
| §2 fim por esgotamento | 4 |
| §3 sem janela, sem limite de ciclos | 4 |
| §3 autorizações custam energia | 5 |
| §3 consumo do próprio saldo, reserva não paga | 2, 3 |
| §3 reversão do tamanho do lote | 8 (documentado) |
| §4 `esta_operante`, `CatalogoDeOperacao`, `encerrada` | 1, 2, 4 |
| §5 os dois valores | 1 |
| §6 passo no tick, rotas exigem operante, alocação como comando | 3, 5, 6 |
| §7 os cinco testes | 4 (terminação), 7 (os outros quatro) |

Sem lacunas.

**Consistência de tipos:** `esta_operante(central) -> bool` e `debitar_ate_o_saldo(central, quantidade) -> float` definidos na Task 2, usados nas 3, 4, 5 e 6. `catalogo_de_operacao` criado na Task 3, usado na 4 e 5. `encerrada` criado na Task 4, usado na 7. `CENTRAIS` já existe em `motor_de_simulacao.py:22`.

**Sem placeholders:** todos os passos de código têm código. O único ponto sem valores fixos é a recalibração da Task 7, deliberadamente — o passo diz qual alavanca mexer para cada falha e quando reportar BLOCKED.

**Risco conhecido:** as Tasks 3, 5 e 6 mexem em algo que toda a suíte exercita — consumo de energia e autorizações. Espera-se quebra ampla de testes existentes por saldo insuficiente no setup. Ajustar alocação de setup é legítimo; enfraquecer asserção não é. Cada arquivo tocado precisa aparecer no relatório da tarefa com o motivo.
