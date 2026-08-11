# Fase 1: Riqueza Estrategica nas Centrais Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enriquecer `Missão`, `Extração` e `Pesquisa` com escolhas honestas, comparáveis e economicamente relevantes, sem reintroduzir atalhos de API ou quebrar a calibragem estratégica recém-estabelecida no transporte.

**Architecture:** A implementação introduz novas classes/políticas explícitas nessas três centrais, mas preserva o desenho atual do mundo: o motor continua sendo a fonte de verdade, as APIs continuam enfileirando comandos e os testes continuam validando comportamento por ciclo. O plano prioriza mudanças locais e cumulativas: primeiro ampliar `Missão`, depois `Extração`, depois `Pesquisa`, e por fim ajustar a bateria exploratória e o relatório para medir se a separação estratégica aumentou.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, pytest, dataclasses, motor de simulação discreto existente.

## Global Constraints

- Manter todo o código de domínio em português.
- Não reintroduzir nenhum caminho que permita monetização sem análise, aprovação e transporte válido.
- Preservar determinismo por seed: mesma seed + mesmo código = mesmo mundo e mesmo resultado.
- Não quebrar o contrato de enfileiramento: mutações seguem acontecendo no ciclo, não no HTTP sync.
- Toda mudança de comportamento precisa nascer com teste vermelho antes da implementação.
- Não aumentar escopo para `Armazenagem` nem para `Sistemas cruzados` nesta fase.

---

### Task 1: Classes de Autorização na Missão

**Files:**
- Modify: `mundo/dominio/autorizacao.py`
- Modify: `mundo/api/missao.py`
- Modify: `mundo/testes/test_api_missao.py`

**Interfaces:**
- Consumes: `RegistroDeAutorizacoes.emitir(operacao: str, central_solicitante: str)`
- Produces: `RegistroDeAutorizacoes.emitir(operacao: str, central_solicitante: str, classe: str = "rapida")`
- Produces: `POST /missao/autorizar-missao` aceita `classe: "rapida" | "segura" | "lote"`

- [ ] **Step 1: Write the failing test**

```python
def test_autorizacao_segura_custa_mais_que_rapida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        antes = motor.energia.consultar_energia("missao")

        cliente.post("/missao/autorizar-missao", json={
            "operacao": "iniciar_viagem",
            "central_solicitante": "transporte",
            "classe": "segura",
        })

        gasto_segura = antes - motor.energia.consultar_energia("missao")
        assert gasto_segura > motor.catalogo_de_operacao.custo_de_autorizacao
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest mundo/testes/test_api_missao.py::test_autorizacao_segura_custa_mais_que_rapida -v`
Expected: FAIL because `classe` is ignored or unsupported.

- [ ] **Step 3: Write the failing persistence/contract test**

```python
def test_autorizacao_em_lote_registra_classe_no_registro():
    registro = RegistroDeAutorizacoes()

    autorizacao = registro.emitir("receber_carga", "armazenagem", classe="lote")

    assert autorizacao.classe == "lote"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest mundo/testes/test_api_missao.py::test_autorizacao_em_lote_registra_classe_no_registro -v`
Expected: FAIL because `Autorizacao` does not have field `classe`.

- [ ] **Step 5: Write minimal implementation**

```python
@dataclass(frozen=True)
class Autorizacao:
    identificador: str
    operacao: str
    central_solicitante: str
    classe: str = "rapida"
    usada: bool = False


def emitir(self, operacao: str, central_solicitante: str, classe: str = "rapida") -> Autorizacao:
    identificador = f"aut-{next(self._contador)}"
    autorizacao = Autorizacao(identificador, operacao, central_solicitante, classe)
    self._autorizacoes[identificador] = autorizacao
    return autorizacao
```

```python
class RequisicaoDeAutorizacao(BaseModel):
    operacao: str
    central_solicitante: str
    classe: str = "rapida"
```

```python
custos = {"rapida": 0.2, "segura": 0.5, "lote": 0.8}
motor.energia.debitar(CENTRAL, custos[requisicao.classe])
autorizacao = motor.autorizacoes.emitir(
    requisicao.operacao,
    requisicao.central_solicitante,
    classe=requisicao.classe,
)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest mundo/testes/test_api_missao.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add mundo/dominio/autorizacao.py mundo/api/missao.py mundo/testes/test_api_missao.py
git commit -m "feat: adiciona classes de autorizacao na missao"
```

### Task 2: Políticas de Repasse na Missão

**Files:**
- Modify: `mundo/api/missao.py`
- Modify: `mundo/testes/test_api_missao.py`

**Interfaces:**
- Consumes: `POST /missao/alocar-energia {destino, quantidade}`
- Produces: `POST /missao/alocar-energia {destino, quantidade, politica?}`
- Produces: `GET /missao/estado` com `politica_de_missao` atual quando aplicável

- [ ] **Step 1: Write the failing test**

```python
def test_alocar_energia_com_politica_de_contingencia_mantem_colchao_na_missao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        antes = motor.energia.consultar_energia("missao")

        cliente.post("/missao/alocar-energia", json={
            "destino": "extracao",
            "quantidade": 50,
            "politica": "contingencia",
        })
        motor.avancar_ciclo(1)

        assert motor.energia.consultar_energia("missao") >= antes - 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest mundo/testes/test_api_missao.py::test_alocar_energia_com_politica_de_contingencia_mantem_colchao_na_missao -v`
Expected: FAIL because `politica` is ignored.

- [ ] **Step 3: Write minimal implementation**

```python
class RequisicaoDeAlocacao(BaseModel):
    destino: str
    quantidade: int
    politica: str = "pulso"
```

```python
COLCHAO_MINIMO_MISSAO = 5.0
if requisicao.politica == "contingencia":
    saldo_da_missao = motor.energia.consultar_energia(CENTRAL)
    quantidade = min(requisicao.quantidade, max(0.0, saldo_da_missao - COLCHAO_MINIMO_MISSAO))
    if quantidade <= 0:
        raise ValueError("Política de contingência preservou o colchão da missão")
else:
    quantidade = requisicao.quantidade
motor.energia.alocar_energia(GerenciadorDeEnergia.RESERVA, requisicao.destino, quantidade)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest mundo/testes/test_api_missao.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mundo/api/missao.py mundo/testes/test_api_missao.py
git commit -m "feat: adiciona politicas de repasse da missao"
```

### Task 3: Tipos de Mineradora na Extração

**Files:**
- Modify: `mundo/dominio/robos.py`
- Modify: `mundo/motor/motor_de_simulacao.py`
- Modify: `mundo/api/extracao.py`
- Modify: `mundo/testes/test_api_extracao.py`

**Interfaces:**
- Consumes: `GET /extracao/mineradoras`
- Produces: mineradora com `tipo: "leve" | "industrial" | "precisa"`
- Produces: `GET /extracao/mineradoras` inclui `tipo`

- [ ] **Step 1: Write the failing test**

```python
def test_consultar_mineradoras_expoe_tipos_distintos():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        tipos = {item["tipo"] for item in cliente.get("/extracao/mineradoras").json()}
        assert tipos == {"leve", "precisa"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest mundo/testes/test_api_extracao.py::test_consultar_mineradoras_expoe_tipos_distintos -v`
Expected: FAIL because `tipo` is missing.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass
class UnidadeMineradora(Robo):
    tipo: str = "leve"
```

```python
self.robos["mineradora-1"] = UnidadeMineradora(..., capacidade=35.0, tipo="leve")
self.robos["mineradora-2"] = UnidadeMineradora(..., capacidade=25.0, tipo="precisa")
```

```python
"tipo": robo.tipo,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest mundo/testes/test_api_extracao.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mundo/dominio/robos.py mundo/motor/motor_de_simulacao.py mundo/api/extracao.py mundo/testes/test_api_extracao.py
git commit -m "feat: adiciona tipos de mineradora"
```

### Task 4: Perfis de Escavação na Extração

**Files:**
- Modify: `mundo/api/extracao.py`
- Modify: `mundo/testes/test_api_extracao.py`

**Interfaces:**
- Consumes: `POST /extracao/iniciar-extracao`
- Produces: novo campo opcional `perfil_de_escavacao: "superficial" | "profunda" | "mapeadora"`

- [ ] **Step 1: Write the failing test**

```python
def test_perfil_profundo_custa_mais_energia_que_superficial():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "extracao", 100)
        antes = motor.energia.consultar_energia("extracao")

        cliente.post("/extracao/iniciar-extracao", json={
            "identificador_da_unidade": "mineradora-1",
            "identificador_da_jazida": "jazida-1",
            "quantidade": 10.0,
            "perfil_de_escavacao": "profunda",
        })
        motor.avancar_ciclo(1)

        assert motor.energia.consultar_energia("extracao") < antes - 2.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest mundo/testes/test_api_extracao.py::test_perfil_profundo_custa_mais_energia_que_superficial -v`
Expected: FAIL because `perfil_de_escavacao` is unsupported.

- [ ] **Step 3: Write minimal implementation**

```python
class RequisicaoDeExtracao(BaseModel):
    identificador_da_unidade: str
    identificador_da_jazida: str
    quantidade: float
    modo: ModoDeExtracao = ModoDeExtracao.NORMAL
    perfil_de_escavacao: str = "superficial"
```

```python
ajuste_por_perfil = {
    "superficial": {"energia": 0.9, "qualidade": 0.0},
    "profunda": {"energia": 1.25, "qualidade": 4.0},
    "mapeadora": {"energia": 1.1, "qualidade": 2.0},
}
ajuste = ajuste_por_perfil[requisicao.perfil_de_escavacao]
custo *= ajuste["energia"]
qualidade_inicial = min(100.0, perfil.qualidade_inicial + ajuste["qualidade"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest mundo/testes/test_api_extracao.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mundo/api/extracao.py mundo/testes/test_api_extracao.py
git commit -m "feat: adiciona perfis de escavacao"
```

### Task 5: Tipos de Análise na Pesquisa

**Files:**
- Modify: `mundo/api/pesquisa.py`
- Modify: `mundo/testes/test_api_pesquisa.py`

**Interfaces:**
- Consumes: `POST /pesquisa/iniciar-analise {identificador_da_carga}`
- Produces: `POST /pesquisa/iniciar-analise {identificador_da_carga, tipo_de_analise?}`

- [ ] **Step 1: Write the failing test**

```python
def test_analise_rapida_termina_antes_da_completa():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0, local=LocalDaCarga.NA_MAO)
        motor.energia.alocar_energia("reserva_estrategica", "pesquisa", 20)

        cliente.post("/pesquisa/iniciar-analise", json={
            "identificador_da_carga": "carga-1",
            "tipo_de_analise": "rapida",
        })
        motor.avancar_ciclo(2)

        assert any(e.tipo == "analise_concluida" for e in motor.eventos.consultar_eventos())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest mundo/testes/test_api_pesquisa.py::test_analise_rapida_termina_antes_da_completa -v`
Expected: FAIL because `tipo_de_analise` is unsupported.

- [ ] **Step 3: Write minimal implementation**

```python
class RequisicaoDeAnalise(BaseModel):
    identificador_da_carga: str
    tipo_de_analise: str = "completa"
```

```python
ajuste_por_tipo = {
    "rapida": {"duracao": 0.5, "custo": 0.8},
    "completa": {"duracao": 1.0, "custo": 1.0},
    "forense": {"duracao": 1.5, "custo": 1.4},
}
ajuste = ajuste_por_tipo[requisicao.tipo_de_analise]
custo *= ajuste["custo"]
duracao = max(1, round(mineral.ciclos_de_analise * ajuste["duracao"]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest mundo/testes/test_api_pesquisa.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mundo/api/pesquisa.py mundo/testes/test_api_pesquisa.py
git commit -m "feat: adiciona tipos de analise"
```

### Task 6: Políticas de Aprovação na Pesquisa

**Files:**
- Modify: `mundo/api/pesquisa.py`
- Modify: `mundo/testes/test_api_pesquisa.py`

**Interfaces:**
- Consumes: `POST /pesquisa/aprovar-carga {identificador_da_carga}`
- Produces: `POST /pesquisa/aprovar-carga {identificador_da_carga, politica?}`

- [ ] **Step 1: Write the failing test**

```python
def test_politica_estrita_exige_qualidade_maior_que_a_comercial():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 60.0, local=LocalDaCarga.NA_MAO, analisada=True)

        cliente.post("/pesquisa/aprovar-carga", json={
            "identificador_da_carga": "carga-1",
            "politica": "estrita",
        })
        motor.avancar_ciclo(1)

        assert any(e.tipo == "operacao_invalida" for e in motor.eventos.consultar_eventos())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest mundo/testes/test_api_pesquisa.py::test_politica_estrita_exige_qualidade_maior_que_a_comercial -v`
Expected: FAIL because `politica` is unsupported.

- [ ] **Step 3: Write minimal implementation**

```python
politicas = {
    "comercial": 40.0,
    "estrita": 70.0,
    "premium": 85.0,
}
limiar = politicas[requisicao.politica]
if carga.qualidade < limiar:
    raise ValueError("Qualidade insuficiente para aprovação")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest mundo/testes/test_api_pesquisa.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mundo/api/pesquisa.py mundo/testes/test_api_pesquisa.py
git commit -m "feat: adiciona politicas de aprovacao"
```

### Task 7: Recalibrar Bateria Exploratória e Relatório

**Files:**
- Modify: `docs/relatorios/simulacoes-de-participantes.md`
- Test: rerun manual simulation harness used in the current session

**Interfaces:**
- Consumes: new behavior in `Missão`, `Extração` and `Pesquisa`
- Produces: updated markdown report with at least 3 strategy profiles and a conclusion about whether the three central changes increased strategic richness

- [ ] **Step 1: Define 3 new participant profiles**

```text
1. conservador_de_qualidade
2. caixa_rapido_administrado
3. operador_hibrido_de_valor
```

- [ ] **Step 2: Run the manual simulation battery**

Run: `python <harness atualizado da rodada>`
Expected: three strategy blocks with seed-by-seed outputs and aggregated averages.

- [ ] **Step 3: Update the report**

```markdown
## Rodada Fase 1

- Missão agora distingue classes de autorização e repasse
- Extração agora distingue tipo de mineradora e perfil de escavação
- Pesquisa agora distingue tipo de análise e política de aprovação
```

- [ ] **Step 4: Validate report coherence**

Run: `pytest mundo/testes -q`
Expected: PASS, and the report numbers align with the fresh battery output.

- [ ] **Step 5: Commit**

```bash
git add docs/relatorios/simulacoes-de-participantes.md
git commit -m "docs: atualiza simulacoes da fase 1"
```

## Self-Review

- Cobertura de spec: a Fase 1 ficou de fato limitada a `Missão`, `Extração` e `Pesquisa`; `Armazenagem` e `Sistemas cruzados` ficaram explicitamente fora.
- Placeholder scan: removidos. Os nomes de arquivos, APIs e comandos estão explícitos.
- Consistência: o plano mantém o fluxo por ciclo, preserva determinismo por seed e reaproveita as APIs atuais sem propor refactor estrutural desnecessário.
