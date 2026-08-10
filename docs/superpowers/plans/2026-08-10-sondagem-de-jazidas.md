# Sondagem De Jazidas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar sondagem de jazidas na Central de Pesquisa, persistir estimativas de composicao em faixas e documentar as responsabilidades de cada central para os participantes.

**Architecture:** A mudanca expande o dominio de `Jazida` com composicao real e estimada, reaproveita o gargalo existente da Central de Pesquisa para sondagens e expoe uma consulta especifica para a estimativa ja descoberta. A documentacao sera atualizada no `README.md` raiz e em `centrais/*/README.md` sem introduzir arquitetura interna nas centrais dos participantes.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, pytest

## Global Constraints

- Todo codigo pertencente ao dominio deve utilizar portugues.
- O Mundo e a fonte de verdade.
- As Centrais nao podem alterar diretamente seu estado.
- Toda aleatoriedade deve utilizar a semente.
- A mesma semente e o mesmo codigo das Centrais devem produzir resultados reproduziveis.
- Nao superarquitetar.
- Preferir codigo legivel e dominio explicito.
- Nao implementar estrategia para os participantes.
- Nao criar arquitetura interna nesses diretorios das centrais.

---

### Task 1: Expandir o dominio de jazidas com composicao

**Files:**
- Modify: `mundo/dominio/jazidas.py`
- Modify: `mundo/motor/motor_de_simulacao.py`
- Test: `mundo/testes/test_jazidas.py`

**Interfaces:**
- Consumes: `Jazida`, `MotorDeSimulacao._gerar_mundo_inicial()`
- Produces: `Jazida.composicao_real: dict[str, float]`, `Jazida.composicao_estimada: dict[str, str] | None`, `Jazida.estimar_composicao() -> dict[str, str]`

- [ ] **Step 1: Write the failing tests**

```python
def test_estimar_composicao_converte_fracoes_em_faixas():
    jazida = Jazida(
        identificador="j1",
        localizacao="setor-1",
        mineral="hematita",
        quantidade_disponivel=100.0,
        dificuldade_extracao=1.0,
        risco=0.1,
        estado=EstadoDaJazida.DISPONIVEL,
        composicao_real={"hematita": 0.72, "jarosita": 0.18, "cristal_raro": 0.03},
    )

    assert jazida.estimar_composicao() == {
        "hematita": "alta",
        "jarosita": "baixa",
        "cristal_raro": "tracos",
    }


def test_jazida_pode_guardar_estimativa_persistida():
    jazida = _criar_jazida()
    jazida.composicao_estimada = {"hematita": "alta"}

    assert jazida.composicao_estimada == {"hematita": "alta"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest mundo/testes/test_jazidas.py -v`
Expected: FAIL because `Jazida` does not accept `composicao_real` or define `estimar_composicao`

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass
class Jazida:
    composicao_real: dict[str, float] | None = None
    composicao_estimada: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.quantidade_inicial is None:
            self.quantidade_inicial = self.quantidade_disponivel
        if self.composicao_real is None:
            self.composicao_real = {self.mineral: 1.0}

    def estimar_composicao(self) -> dict[str, str]:
        estimativa: dict[str, str] = {}
        for mineral, fracao in self.composicao_real.items():
            if fracao <= 0.0:
                continue
            if fracao <= 0.05:
                estimativa[mineral] = "tracos"
            elif fracao <= 0.20:
                estimativa[mineral] = "baixa"
            elif fracao <= 0.50:
                estimativa[mineral] = "media"
            else:
                estimativa[mineral] = "alta"
        return estimativa
```

- [ ] **Step 4: Seed deterministic real composition in world generation**

```python
composicao = {mineral.nome: 0.7}
outros = [m.nome for m in self.catalogo_de_minerais.todos() if m.nome != mineral.nome]
if outros:
    secundario = self.rng.choice(outros)
    composicao[secundario] = 0.2
restante = 0.1
for nome in outros:
    if nome != secundario:
        composicao[nome] = round(restante / max(1, len(outros) - 1), 4)

self.jazidas[identificador] = Jazida(
    ...,
    composicao_real=composicao,
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest mundo/testes/test_jazidas.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add mundo/dominio/jazidas.py mundo/motor/motor_de_simulacao.py mundo/testes/test_jazidas.py
git commit -m "feat: adiciona composicao nas jazidas"
```

### Task 2: Adicionar sondagem de jazidas na API de pesquisa

**Files:**
- Modify: `mundo/api/pesquisa.py`
- Test: `mundo/testes/test_api_pesquisa.py`

**Interfaces:**
- Consumes: `Jazida.estimar_composicao() -> dict[str, str]`, `motor.catalogo_de_pesquisa`, `motor.analises_em_andamento`
- Produces: `POST /pesquisa/sondar-jazida`, `GET /pesquisa/jazidas/{identificador}/estimativa`, evento `sondagem_de_jazida_concluida`

- [ ] **Step 1: Write the failing tests**

```python
def test_sondar_jazida_conclui_e_persiste_estimativa():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "pesquisa", 20)

        resposta = cliente.post("/pesquisa/sondar-jazida", json={"identificador_da_jazida": "jazida-1"})
        assert resposta.status_code == 200

        motor.avancar_ciclo(1)
        motor.avancar_ciclo(1)

        consulta = cliente.get("/pesquisa/jazidas/jazida-1/estimativa")
        assert consulta.status_code == 200
        assert consulta.json()["estimativa_de_composicao"]


def test_sondar_jazida_compete_com_analise_de_carga():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        motor.cargas["carga-1"] = CargaMineral("carga-1", "hematita", 10.0, 90.0, local=LocalDaCarga.NA_MAO)
        motor.energia.alocar_energia("reserva_estrategica", "pesquisa", 20)

        cliente.post("/pesquisa/iniciar-analise", json={"identificador_da_carga": "carga-1"})
        motor.avancar_ciclo(1)
        cliente.post("/pesquisa/sondar-jazida", json={"identificador_da_jazida": "jazida-1"})
        motor.avancar_ciclo(1)

        eventos = motor.eventos.consultar_eventos()
        assert any(e.tipo == "operacao_invalida" and "ocupado" in e.dados["motivo"] for e in eventos)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest mundo/testes/test_api_pesquisa.py -v`
Expected: FAIL because the new endpoints do not exist

- [ ] **Step 3: Write minimal implementation**

```python
class RequisicaoDeSondagem(BaseModel):
    identificador_da_jazida: str


@router.post("/sondar-jazida")
async def sondar_jazida(requisicao: RequisicaoDeSondagem) -> dict:
    motor = obter_motor()
    jazida = motor.jazidas.get(requisicao.identificador_da_jazida)
    if jazida is None:
        raise HTTPException(status_code=404, detail="Jazida nao encontrada")

    def executar() -> None:
        if not motor.energia.esta_operante(CENTRAL):
            raise ValueError(f"Central {CENTRAL} dormente")
        if len(motor.analises_em_andamento) >= motor.catalogo_de_pesquisa.capacidade_paralela:
            raise ValueError("Centro de pesquisa ocupado")
        if jazida.composicao_estimada is not None:
            raise ValueError("Jazida ja sondada")

        motor.energia.debitar(CENTRAL, motor.catalogo_de_pesquisa.custo_base_de_analise)
        chave = f"jazida:{jazida.identificador}"
        motor.analises_em_andamento.append(chave)

        def concluir() -> None:
            jazida.composicao_estimada = jazida.estimar_composicao()
            if chave in motor.analises_em_andamento:
                motor.analises_em_andamento.remove(chave)
            motor.eventos.publicar(
                "sondagem_de_jazida_concluida",
                motor.ciclo_atual,
                {"jazida": jazida.identificador, "estimativa_de_composicao": jazida.composicao_estimada},
            )

        motor.agendar_efeito(motor.ciclo_atual + 2, concluir)

    motor.enfileirar_comando(Comando("sondar_jazida", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}


@router.get("/jazidas/{identificador}/estimativa")
async def consultar_estimativa_da_jazida(identificador: str) -> dict:
    motor = obter_motor()
    jazida = motor.jazidas.get(identificador)
    if jazida is None:
        raise HTTPException(status_code=404, detail="Jazida nao encontrada")
    if jazida.composicao_estimada is None:
        raise HTTPException(status_code=404, detail="Jazida ainda nao sondada")
    return {
        "jazida": jazida.identificador,
        "mineral_predominante": jazida.mineral,
        "estimativa_de_composicao": jazida.composicao_estimada,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest mundo/testes/test_api_pesquisa.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mundo/api/pesquisa.py mundo/testes/test_api_pesquisa.py
git commit -m "feat: adiciona sondagem de jazidas"
```

### Task 3: Atualizar documentacao geral e das centrais

**Files:**
- Modify: `README.md`
- Create: `centrais/extracao/README.md`
- Create: `centrais/transporte/README.md`
- Create: `centrais/armazenagem/README.md`
- Create: `centrais/pesquisa/README.md`
- Create: `centrais/missao/README.md`

**Interfaces:**
- Consumes: comportamento da Pesquisa e regras descritas no `README.md`
- Produces: orientacao detalhada para participantes por central

- [ ] **Step 1: Add the new mechanics to the root README**

```markdown
### Central de Pesquisa

* **O que permite:** Iniciar analises de carga, classificar qualidade, aprovar distribuicao e sondar jazidas para revelar estimativas de composicao em faixas.
* **Mecanica a contornar:** A Pesquisa continua sendo um gargalo unico. Sondar cedo demais pode atrasar faturamento; sondar tarde demais pode fazer o Transporte operar no escuro.
```

- [ ] **Step 2: Create `centrais/extracao/README.md`**

```markdown
# Central de Extracao

Sua responsabilidade e transformar jazidas em cargas.

Voce sabe:
- jazidas disponiveis;
- mineral predominante da jazida;
- quantidade restante;
- risco e dificuldade.

Voce nao sabe:
- qualidade final da carga antes da Pesquisa;
- composicao estimada da jazida antes de a Pesquisa sondar.
```

- [ ] **Step 3: Create `centrais/transporte/README.md`**

```markdown
# Central de Transporte

Sua responsabilidade e decidir como mover carga sem destruir valor no caminho.

Use a estimativa de composicao da Pesquisa para inferir se a carga originada numa jazida tende a conter material valioso o bastante para justificar modo urgente.
```

- [ ] **Step 4: Create the remaining central READMEs**

```markdown
# Central de Pesquisa

Sua responsabilidade e reduzir a assimetria de informacao do sistema.

Voce escolhe entre duas filas concorrentes:
- analisar carga para liberar faturamento;
- sondar jazida para melhorar decisoes futuras.
```

- [ ] **Step 5: Verify docs exist and read cleanly**

Run: `pytest mundo/testes/test_scaffolding.py -v`
Expected: PASS if there are repository structure checks; otherwise manually inspect the created files

- [ ] **Step 6: Commit**

```bash
git add README.md centrais/extracao/README.md centrais/transporte/README.md centrais/armazenagem/README.md centrais/pesquisa/README.md centrais/missao/README.md
git commit -m "docs: detalha as centrais e a sondagem"
```
