# Desgaste por Intensidade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer com que operar continuamente desgaste o robô e encareça as operações seguintes, de modo que `agressivo` deixe de dominar por construção e pausar vire uma decisão estratégica real.

**Architecture:** `Robo.desgaste` — campo que já existe no domínio e nunca foi usado — passa a acumular proporcional à energia gasta em cada operação e a recuperar por ciclo enquanto o robô está `DISPONIVEL`. Um `fator_desgaste` derivado dele multiplica o custo das operações no mesmo ponto de composição onde já entram o modo e a escassez.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, pytest.

## Global Constraints

- Todo código de domínio (classes, métodos, variáveis, eventos, comandos, endpoints, docs, mensagens, testes) em português. Identificadores de FastAPI/Pydantic permanecem no idioma da biblioteca.
- Python 3.12+.
- Rotas nunca mutam estado de forma síncrona — toda mutação vive dentro de closures `Comando.executar()`, executadas pelo tick.
- `mundo/dominio/` não importa de `mundo/motor/` nem de `mundo/api/`.
- Nenhuma fonte nova de aleatoriedade — o único `random.Random(semente)` do motor permanece o único.
- O custo de energia deve permanecer estritamente positivo e finito: `GerenciadorDeEnergia.debitar` rejeita `quantidade <= 0`.
- O desgaste nunca fica negativo.
- Não existe teto que leve o robô a `INDISPONIVEL` — o custo cresce, o robô nunca é bloqueado.
- Os fatores de custo compõem por multiplicação num único ponto por rota, para que os eventos ambientais de um sub-projeto futuro possam entrar ali sem refatoração.

---

### Task 1: Fatores de desgaste no catálogo de modos

**Files:**
- Modify: `mundo/config/modos.json`
- Modify: `mundo/dominio/modos.py`
- Test: `mundo/testes/test_modos.py`

**Interfaces:**
- Consumes: `CatalogoDeModos` já expõe `fator_base_de_energia`, `fator_escassez_maximo`, `expoente_escassez` e o método `fator_de_escassez(fracao_restante)`.
- Produces: `CatalogoDeModos` ganha os atributos `taxa_de_desgaste: float`, `recuperacao_de_desgaste_por_ciclo: float`, `sensibilidade_ao_desgaste: float`, e o método `fator_de_desgaste(desgaste: float) -> float`.

- [ ] **Step 1: Acrescentar as três chaves a `mundo/config/modos.json`**

No mesmo nível de `fator_base_de_energia`, acrescentar:

```json
  "taxa_de_desgaste": 0.5,
  "recuperacao_de_desgaste_por_ciclo": 0.4,
  "sensibilidade_ao_desgaste": 0.25,
```

Justificativa dos valores de partida: uma extração normal de 10 unidades de hematita custa `1.0 × 10 × 0.2 × 1.0 = 2.0` de energia, o que gera `2.0 × 0.5 = 1.0` de desgaste, o que encarece a próxima operação em `1 + 1.0 × 0.25 = 1.25×`. Recuperar esse ponto inteiro leva `1.0 / 0.4 = 2.5` ciclos parado. São números plausíveis para o ponto de partida; a Task 5 recalibra com base no comportamento medido.

- [ ] **Step 2: Escrever o teste falhando**

```python
# acrescentar em mundo/testes/test_modos.py
def test_fatores_de_desgaste_disponiveis():
    catalogo = _catalogo()
    assert catalogo.taxa_de_desgaste > 0
    assert catalogo.recuperacao_de_desgaste_por_ciclo > 0
    assert catalogo.sensibilidade_ao_desgaste > 0


def test_fator_de_desgaste_e_neutro_quando_o_robo_esta_descansado():
    assert _catalogo().fator_de_desgaste(0.0) == 1.0


def test_fator_de_desgaste_cresce_com_o_desgaste():
    catalogo = _catalogo()
    assert catalogo.fator_de_desgaste(4.0) > catalogo.fator_de_desgaste(1.0) > 1.0


def test_fator_de_desgaste_e_linear_na_sensibilidade():
    catalogo = _catalogo()
    esperado = 1.0 + 2.0 * catalogo.sensibilidade_ao_desgaste
    assert catalogo.fator_de_desgaste(2.0) == pytest.approx(esperado)
```

Garantir que `import pytest` está no topo do arquivo.

- [ ] **Step 3: Rodar e confirmar falha**

Run: `.venv/bin/pytest mundo/testes/test_modos.py -v`
Expected: FAIL com `AttributeError: 'CatalogoDeModos' object has no attribute 'taxa_de_desgaste'`

- [ ] **Step 4: Implementar em `mundo/dominio/modos.py`**

Acrescentar os três parâmetros ao `__init__` (depois dos existentes, todos com valor obrigatório vindo do JSON), guardá-los como atributos públicos, lê-los em `carregar_de_arquivo` a partir de `dados["taxa_de_desgaste"]`, `dados["recuperacao_de_desgaste_por_ciclo"]` e `dados["sensibilidade_ao_desgaste"]`, e acrescentar o método:

```python
    def fator_de_desgaste(self, desgaste: float) -> float:
        """Quanto o desgaste acumulado encarece a próxima operação.

        Cresce linearmente e sem teto: um robô nunca é bloqueado, só fica
        progressivamente caro de operar até que descanse.
        """
        return 1.0 + max(0.0, desgaste) * self.sensibilidade_ao_desgaste
```

- [ ] **Step 5: Rodar e confirmar passa**

Run: `.venv/bin/pytest mundo/testes/test_modos.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add mundo/config/modos.json mundo/dominio/modos.py mundo/testes/test_modos.py
git commit -m "feat: add wear factors to the mode catalog"
```

---

### Task 2: Acumulação e recuperação de desgaste no motor

**Files:**
- Modify: `mundo/motor/motor_de_simulacao.py`
- Test: `mundo/testes/test_desgaste.py` (criar)

**Interfaces:**
- Consumes: `CatalogoDeModos.recuperacao_de_desgaste_por_ciclo` (Task 1); `Robo.desgaste`, `EstadoDoRobo.DISPONIVEL`.
- Produces: método privado `MotorDeSimulacao._recuperar_desgaste()` chamado a cada tick, junto do passo de degradação de cargas.

- [ ] **Step 1: Escrever o teste falhando**

```python
# mundo/testes/test_desgaste.py
from pathlib import Path

from mundo.dominio.minerais import CatalogoDeMinerais
from mundo.dominio.robos import EstadoDoRobo
from mundo.motor.motor_de_simulacao import ConfiguracaoDaSimulacao, MotorDeSimulacao

CAMINHO_CATALOGO = Path(__file__).parent.parent / "config" / "minerais.json"


def _criar_motor(semente: int = 1) -> MotorDeSimulacao:
    catalogo = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO)
    return MotorDeSimulacao(ConfiguracaoDaSimulacao(semente=semente, duracao_maxima=50), catalogo)


def test_robo_disponivel_recupera_desgaste_a_cada_ciclo():
    motor = _criar_motor()
    unidade = motor.robos["mineradora-1"]
    unidade.estado = EstadoDoRobo.DISPONIVEL
    unidade.desgaste = 2.0
    recuperacao = motor.catalogo_de_modos.recuperacao_de_desgaste_por_ciclo

    motor.avancar_ciclo(1)

    assert unidade.desgaste == 2.0 - recuperacao


def test_robo_executando_nao_recupera_desgaste():
    motor = _criar_motor()
    unidade = motor.robos["mineradora-1"]
    unidade.estado = EstadoDoRobo.EXECUTANDO
    unidade.desgaste = 2.0

    motor.avancar_ciclo(3)

    assert unidade.desgaste == 2.0


def test_desgaste_nunca_fica_negativo():
    motor = _criar_motor()
    unidade = motor.robos["mineradora-1"]
    unidade.estado = EstadoDoRobo.DISPONIVEL
    unidade.desgaste = 0.1

    motor.avancar_ciclo(20)

    assert unidade.desgaste == 0.0


def test_recuperacao_alcanca_todos_os_robos_disponiveis():
    motor = _criar_motor()
    for robo in motor.robos.values():
        robo.estado = EstadoDoRobo.DISPONIVEL
        robo.desgaste = 1.0

    motor.avancar_ciclo(1)

    recuperacao = motor.catalogo_de_modos.recuperacao_de_desgaste_por_ciclo
    assert all(robo.desgaste == 1.0 - recuperacao for robo in motor.robos.values())
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `.venv/bin/pytest mundo/testes/test_desgaste.py -v`
Expected: FAIL — o desgaste permanece 2.0 porque nada o recupera.

- [ ] **Step 3: Implementar em `mundo/motor/motor_de_simulacao.py`**

Em `_processar_um_ciclo`, logo após a chamada a `self._degradar_cargas()`, acrescentar:

```python
        self._recuperar_desgaste()
```

E o método novo, logo abaixo de `_degradar_cargas`:

```python
    def _recuperar_desgaste(self) -> None:
        recuperacao = self.catalogo_de_modos.recuperacao_de_desgaste_por_ciclo
        for robo in self.robos.values():
            if robo.estado == EstadoDoRobo.DISPONIVEL:
                robo.desgaste = max(0.0, robo.desgaste - recuperacao)
```

Confirmar que `EstadoDoRobo` já está importado no arquivo; ele é usado na geração do mundo inicial.

- [ ] **Step 4: Rodar e confirmar passa**

Run: `.venv/bin/pytest mundo/testes/test_desgaste.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Rodar a suíte completa**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: todos passam. Nenhum teste existente afirma nada sobre `desgaste`, então não deve haver regressão.

- [ ] **Step 6: Commit**

```bash
git add mundo/motor/motor_de_simulacao.py mundo/testes/test_desgaste.py
git commit -m "feat: recover robot wear each cycle while idle"
```

---

### Task 3: Desgaste na extração

**Files:**
- Modify: `mundo/api/extracao.py`
- Test: `mundo/testes/test_desgaste.py`

**Interfaces:**
- Consumes: `CatalogoDeModos.taxa_de_desgaste`, `.fator_de_desgaste(desgaste)` (Task 1).
- Produces: o custo de extração passa a incluir `fator_de_desgaste(unidade.desgaste)`; a unidade acumula desgaste proporcional à energia gasta; o evento `extracao_concluida` ganha o campo `desgaste_da_unidade`.

- [ ] **Step 1: Escrever o teste falhando**

```python
# acrescentar em mundo/testes/test_desgaste.py
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo


def _extrair(cliente, **campos):
    corpo = {
        "identificador_da_unidade": "mineradora-1",
        "identificador_da_jazida": "jazida-1",
        "quantidade": 10.0,
    }
    corpo.update(campos)
    return cliente.post("/extracao/iniciar-extracao", json=corpo)


def test_extracao_acumula_desgaste_proporcional_a_energia_gasta():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 500)
        unidade = motor.robos["mineradora-1"]
        energia_antes = motor.energia.consultar_energia("extracao")

        _extrair(cliente)
        motor.avancar_ciclo(1)

        energia_gasta = energia_antes - motor.energia.consultar_energia("extracao")
        esperado = energia_gasta * motor.catalogo_de_modos.taxa_de_desgaste
        assert unidade.desgaste == pytest.approx(esperado)


def test_unidade_desgastada_paga_mais_pela_mesma_extracao():
    custos = {}
    for desgaste_inicial in (0.0, 4.0):
        app = criar_app(com_loop_real_time=False)
        with TestClient(app) as cliente:
            motor = instancia_do_mundo.obter_motor()
            motor.energia.alocar_energia("reserva_estrategica", "extracao", 500)
            motor.robos["mineradora-1"].desgaste = desgaste_inicial
            antes = motor.energia.consultar_energia("extracao")

            _extrair(cliente)
            motor.avancar_ciclo(1)

            custos[desgaste_inicial] = antes - motor.energia.consultar_energia("extracao")

    assert custos[4.0] > custos[0.0]
```

Garantir `import pytest` no topo do arquivo.

- [ ] **Step 2: Rodar e confirmar falha**

Run: `.venv/bin/pytest mundo/testes/test_desgaste.py -v`
Expected: FAIL — o desgaste permanece 0.0 e os dois custos são iguais.

- [ ] **Step 3: Implementar em `mundo/api/extracao.py`**

Dentro de `executar()`, acrescentar o fator de desgaste ao produto que já existe e passar a acumular desgaste logo após o débito:

```python
        custo = (
            mineral.custo_extracao
            * requisicao.quantidade
            * motor.catalogo_de_modos.fator_base_de_energia
            * perfil.mult_energia
            * motor.catalogo_de_modos.fator_de_escassez(jazida.fracao_restante)
            * motor.catalogo_de_modos.fator_de_desgaste(unidade.desgaste)
        )
        motor.energia.debitar(CENTRAL, custo)
        unidade.desgaste += custo * motor.catalogo_de_modos.taxa_de_desgaste
```

Acrescentar `"desgaste_da_unidade": unidade.desgaste` ao payload do evento `extracao_concluida`, preservando os campos que já existem.

- [ ] **Step 4: Rodar e confirmar passa**

Run: `.venv/bin/pytest mundo/testes/test_desgaste.py -v`
Expected: PASS

- [ ] **Step 5: Rodar a suíte completa**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: os testes de `test_api_extracao.py` que fixam valores exatos de energia vão falhar, porque uma unidade que extrai duas vezes seguidas agora paga mais na segunda. São regressões legítimas de uma mudança intencional. Corrija as asserções recalculando o valor esperado com o fator de desgaste aplicado, com um comentário mostrando a conta, e liste cada uma no relatório. Não desligue o desgaste para fazer asserção antiga passar.

- [ ] **Step 6: Commit**

```bash
git add mundo/api/extracao.py mundo/testes/test_desgaste.py mundo/testes/test_api_extracao.py
git commit -m "feat: extraction wears the unit and pays for accumulated wear"
```

---

### Task 4: Desgaste no transporte

**Files:**
- Modify: `mundo/api/transporte.py`
- Test: `mundo/testes/test_desgaste.py`

**Interfaces:**
- Consumes: `CatalogoDeModos.taxa_de_desgaste`, `.fator_de_desgaste(desgaste)` (Task 1).
- Produces: o custo da viagem passa a incluir `fator_de_desgaste(unidade.desgaste)`; a unidade acumula desgaste proporcional à energia gasta; o evento `transporte_concluido` ganha o campo `desgaste_da_unidade`.

- [ ] **Step 1: Escrever o teste falhando**

```python
# acrescentar em mundo/testes/test_desgaste.py
from mundo.dominio.cargas import CargaMineral


def _autorizar(cliente) -> str:
    resposta = cliente.post(
        "/missao/autorizar-missao",
        json={"operacao": "iniciar_viagem", "central_solicitante": "transporte"},
    )
    return resposta.json()["id_autorizacao"]


def test_transportadora_desgastada_paga_mais_pela_mesma_viagem():
    custos = {}
    for desgaste_inicial in (0.0, 4.0):
        app = criar_app(com_loop_real_time=False)
        with TestClient(app) as cliente:
            motor = instancia_do_mundo.obter_motor()
            motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)
            motor.energia.alocar_energia("reserva_estrategica", "transporte", 500)
            motor.robos["transportadora-1"].desgaste = desgaste_inicial
            antes = motor.energia.consultar_energia("transporte")

            cliente.post(
                "/transporte/iniciar-viagem",
                json={
                    "identificador_da_unidade": "transportadora-1",
                    "identificador_da_rota": "rota-1",
                    "identificador_da_carga": "carga-1",
                    "id_autorizacao": _autorizar(cliente),
                },
            )
            motor.avancar_ciclo(1)

            custos[desgaste_inicial] = antes - motor.energia.consultar_energia("transporte")

    assert custos[4.0] > custos[0.0]


def test_viagem_acumula_desgaste_na_transportadora():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0)
        motor.energia.alocar_energia("reserva_estrategica", "transporte", 500)
        unidade = motor.robos["transportadora-1"]
        antes = motor.energia.consultar_energia("transporte")

        cliente.post(
            "/transporte/iniciar-viagem",
            json={
                "identificador_da_unidade": "transportadora-1",
                "identificador_da_rota": "rota-1",
                "identificador_da_carga": "carga-1",
                "id_autorizacao": _autorizar(cliente),
            },
        )
        motor.avancar_ciclo(1)

        energia_gasta = antes - motor.energia.consultar_energia("transporte")
        esperado = energia_gasta * motor.catalogo_de_modos.taxa_de_desgaste
        assert unidade.desgaste == pytest.approx(esperado)
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `.venv/bin/pytest mundo/testes/test_desgaste.py -v`
Expected: FAIL — custos iguais e desgaste zerado.

- [ ] **Step 3: Implementar em `mundo/api/transporte.py`**

Substituir o débito atual por um custo composto e a acumulação de desgaste:

```python
        custo = (
            CUSTO_ENERGETICO_VIAGEM
            * perfil.mult_energia
            * motor.catalogo_de_modos.fator_de_desgaste(unidade.desgaste)
        )
        motor.energia.debitar(CENTRAL, custo)
        unidade.desgaste += custo * motor.catalogo_de_modos.taxa_de_desgaste
```

Acrescentar `"desgaste_da_unidade": unidade.desgaste` ao payload do evento `transporte_concluido`, preservando os campos existentes.

- [ ] **Step 4: Rodar e confirmar passa**

Run: `.venv/bin/pytest mundo/testes/test_desgaste.py -v`
Expected: PASS

- [ ] **Step 5: Rodar a suíte completa**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: testes de `test_api_transporte.py` que fixam custo exato de viagem podem falhar quando a mesma unidade viaja duas vezes. Regressão legítima — recalcule a asserção com o fator de desgaste, comentando a conta, e liste cada uma no relatório.

- [ ] **Step 6: Commit**

```bash
git add mundo/api/transporte.py mundo/testes/test_desgaste.py mundo/testes/test_api_transporte.py
git commit -m "feat: transport wears the unit and pays for accumulated wear"
```

---

### Task 5: Provar a inversão e recalibrar

**Files:**
- Test: `mundo/testes/test_desgaste.py`
- Modify: `mundo/config/modos.json` (se a calibração exigir)

**Interfaces:**
- Consumes: tudo das Tasks 1–4.
- Produces: nenhuma assinatura nova — é a prova de que o mecanismo cumpre seu propósito.

Esta é a tarefa que justifica o sub-projeto. As anteriores implementam o desgaste; esta prova que ele resolve a dominância que motivou tudo.

- [ ] **Step 1: Escrever os testes de inversão e de refúgio**

```python
# acrescentar em mundo/testes/test_desgaste.py
from mundo.dominio.modos import ModoDeExtracao

CICLOS_DE_OPERACAO_CONTINUA = 60


def _operar_continuamente(modo: str) -> tuple[float, float]:
    """Extrai sem pausas por uma janela fixa de ciclos.

    Devolve (unidades entregues, energia gasta) para o modo dado, ponderando
    a entrega pela qualidade inicial do modo — o que interessa é valor útil,
    não massa bruta.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 900)
        unidade = motor.robos["mineradora-1"]
        perfil = motor.catalogo_de_modos.obter_extracao(ModoDeExtracao(modo))
        energia_antes = motor.energia.consultar_energia("extracao")
        entregue = 0.0

        for _ in range(CICLOS_DE_OPERACAO_CONTINUA):
            if unidade.estado.value == "disponivel":
                resposta = _extrair(cliente, modo=modo, quantidade=2.0)
                if resposta.status_code == 200:
                    entregue += 2.0 * (perfil.qualidade_inicial / 100)
            elif unidade.estado.value == "aguardando":
                unidade.estado = EstadoDoRobo.DISPONIVEL
            motor.avancar_ciclo(1)

        return entregue, energia_antes - motor.energia.consultar_energia("extracao")


def test_agressivo_deixa_de_dominar_sob_operacao_continua():
    """O ponto do sub-projeto inteiro.

    Sem desgaste, agressivo vence por 1,88x em qualquer cenário estático.
    Sob uso contínuo ele executa mais operações por ciclo, acumula desgaste
    mais rápido e o custo por unidade entregue passa a subir.
    """
    entregue_agressivo, energia_agressivo = _operar_continuamente("agressivo")
    entregue_cuidadoso, energia_cuidadoso = _operar_continuamente("cuidadoso")

    custo_agressivo = energia_agressivo / entregue_agressivo
    custo_cuidadoso = energia_cuidadoso / entregue_cuidadoso

    assert custo_agressivo > custo_cuidadoso, (
        f"agressivo ainda domina sob uso contínuo: "
        f"{custo_agressivo:.2f} vs {custo_cuidadoso:.2f} de energia por unidade entregue"
    )


def test_normal_tambem_acumula_desgaste_e_nao_tem_refugio():
    """Impede a dominância invertida.

    Se o desgaste punisse só os extremos, `normal` viraria a escolha
    universal — o mesmo defeito com outro nome.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 500)
        unidade = motor.robos["mineradora-1"]

        _extrair(cliente, modo="normal")
        motor.avancar_ciclo(1)

        assert unidade.desgaste > 0.0
```

- [ ] **Step 2: Rodar e observar**

Run: `.venv/bin/pytest mundo/testes/test_desgaste.py -v`

O teste de refúgio deve passar de imediato. O teste de inversão pode falhar — e é aí que está o trabalho desta tarefa.

- [ ] **Step 3: Recalibrar até a inversão acontecer**

Se `test_agressivo_deixa_de_dominar_sob_operacao_continua` falhar, a mensagem de erro traz os dois custos por unidade entregue. Ajuste `mundo/config/modos.json` até que a inversão ocorra:

- `taxa_de_desgaste` mais alta faz o desgaste acumular mais rápido em qualquer modo, e penaliza mais quem opera mais vezes — é a alavanca principal.
- `sensibilidade_ao_desgaste` mais alta faz cada ponto de desgaste doer mais.
- `recuperacao_de_desgaste_por_ciclo` mais baixa faz o desgaste persistir, o que penaliza operação contínua sem penalizar quem pausa.

**A configuração é o que muda, nunca a asserção.** Se nenhuma combinação razoável produzir a inversão, pare e reporte BLOCKED com os números que tentou — isso significaria que o mecanismo não resolve o problema, o que é um achado de design legítimo e mais valioso que um teste forçado a passar.

- [ ] **Step 4: Confirmar que a suíte de dominância continua válida**

Run: `.venv/bin/pytest mundo/testes/test_dominancia_de_modos.py -v`
Expected: PASS. Se a recalibração quebrou a dominância (algum modo deixou de vencer em qualquer cenário), ajuste os perfis até satisfazer os dois critérios simultaneamente: cada modo vence em algum mineral, e agressivo não domina sob uso contínuo.

- [ ] **Step 5: Rodar a suíte completa**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: todos passam. Recalibrar pode quebrar asserções que fixam custos exatos — corrija-as recalculando, comentando a conta, e liste cada uma no relatório.

- [ ] **Step 6: Commit**

```bash
git add mundo/testes/test_desgaste.py mundo/config/modos.json
git commit -m "test: prove wear inverts aggressive dominance under continuous operation"
```

---

### Task 6: Documentar o desgaste

**Files:**
- Modify: `docs/LINGUAGEM_DO_DOMINIO.md`

**Interfaces:**
- Consumes: terminologia das Tasks 1–5.
- Produces: nenhuma.

- [ ] **Step 1: Acrescentar as entradas ao final de `docs/LINGUAGEM_DO_DOMINIO.md`**

Preservar o estilo do arquivo: cabeçalho `## Termo` e prosa curta. Antes de escrever os números, confirmar os valores finais em `mundo/config/modos.json` — a Task 5 pode tê-los recalibrado.

```markdown
## Desgaste

Acúmulo de fadiga de um robô, proporcional à energia gasta em cada operação que ele executa. Não bloqueia o robô: encarece progressivamente as operações seguintes, até que ele descanse.

## Recuperação

Queda do desgaste a cada ciclo em que o robô está `disponivel`. Não existe ação de manutenção — pausar é a única forma de recuperar, e o custo de pausar é o tempo ocioso.

## Fator de Desgaste

Multiplicador aplicado ao custo de energia de uma operação, derivado do desgaste acumulado da unidade que a executa. Compõe com o modo e com a escassez da jazida no mesmo produto, e nunca tem teto: um robô muito desgastado fica caro, jamais indisponível.
```

Acrescentar também, ao final da entrada **Modo de Operação** que já existe, uma frase explicando por que o desgaste incide sobre todos os modos: um modo isento viraria a escolha universal, e a decisão deixaria de existir. O ponto estratégico é que operar continuamente custa caro em qualquer modo, então a pergunta real não é qual modo usar, e sim que sequência de operação e pausa sustentar ao longo da missão.

- [ ] **Step 2: Commit**

```bash
git add docs/LINGUAGEM_DO_DOMINIO.md
git commit -m "docs: document wear, recovery and the wear factor"
```
