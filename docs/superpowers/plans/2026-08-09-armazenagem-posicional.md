# Armazenagem Posicional — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar cada armazém numa pilha ordenada, onde guardar, manter, reordenar e desenterrar custam energia, e a ordem escolhida vira a decisão estratégica central.

**Architecture:** `Armazem` ganha uma pilha de identificadores mantida em sincronia com `ocupacao`. `receber-carga` passa a aceitar a ordem completa desejada e vira a única porta de entrada da pilha; `retirar-carga` é destrutivo e devolve o alvo com tudo acima. Um passo novo no tick cobra manutenção por unidade armazenada. Três endpoints incoerentes com a pilha são removidos.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, pytest. Sem dependências novas.

## Global Constraints

- Linguagem de domínio em **português**: nomes de classes, métodos, campos, testes, docstrings e comentários. Identificadores de FastAPI/Pydantic (`app`, `router`, `BaseModel`) permanecem em inglês.
- Mensagens de commit em **inglês**, seguindo o estilo do repositório (`git log --oneline -10`).
- `mundo/dominio/` **não importa** de `mundo/motor/`, `mundo/api/` nem `mundo/eventos/`.
- Rotas **nunca** mutam estado de forma síncrona: toda mutação vive dentro do closure `executar()` de um `Comando`, ou dentro de um efeito agendado.
- Determinismo: nenhuma nova fonte de aleatoriedade. O único `random.Random(semente)` do projeto fica em `motor_de_simulacao.py:46`.
- Qualidade de carga permanece limitada a `[0, 100]` por `clamp_qualidade`.
- Nenhuma asserção existente pode ser enfraquecida para acomodar mudança de comportamento. Se um teste existente falhar, decidir conscientemente se ele codificava o comportamento antigo e registrar a decisão no relatório com a aritmética nova.
- Rodar a suíte inteira (`.venv/bin/pytest mundo/testes -q`) antes de cada commit. Baseline: **199 passam**.
- Preparar arquivos para commit **por nome**. Nunca `git add -A` nem `git add .` — a worktree é compartilhada.

---

## Estrutura de arquivos

| arquivo | responsabilidade | tarefa |
|---|---|---|
| `mundo/dominio/armazens.py` | pilha + ocupação em sincronia | 1 |
| `mundo/dominio/cargas.py` | local `NA_MAO` | 2 |
| `mundo/config/armazenagem.json` | os quatro custos | 3 |
| `mundo/dominio/armazenagem.py` (novo) | `CatalogoDeArmazenagem` | 3 |
| `mundo/motor/motor_de_simulacao.py` | custo de manutenção no tick | 4 |
| `mundo/api/armazenagem.py` | `receber-carga` com ordem, `retirar-carga`, remoções | 5, 6 |
| `mundo/api/transporte.py` | exigir `NA_MAO`, chegar em `NA_MAO` | 7 |
| `mundo/api/pesquisa.py` | exigir `NA_MAO` na distribuição | 7 |
| `mundo/testes/test_armazens.py` | domínio da pilha | 1 |
| `mundo/testes/test_armazenagem_posicional.py` (novo) | custos e fluxo ponta a ponta | 5, 6, 8 |
| `mundo/testes/test_dominancia_de_armazenagem.py` (novo) | suíte de dominância | 8 |
| `docs/LINGUAGEM_DO_DOMINIO.md` | entradas novas | 9 |

---

### Task 1: Pilha no domínio do armazém

**Files:**
- Modify: `mundo/dominio/armazens.py`
- Test: `mundo/testes/test_armazens.py`

**Interfaces:**
- Consumes: nada.
- Produces: `Armazem.pilha: list[str]`, `Armazem.empilhar(identificador: str, quantidade: float) -> None`, `Armazem.desempilhar_ate(identificador: str, quantidades: dict[str, float]) -> list[str]`, `Armazem.profundidade(identificador: str) -> int`, `Armazem.reordenar(nova_ordem: list[str]) -> int`, e a exceção `CargaNaoEstaNoArmazemError`.

Índice 0 é o **fundo**; o último elemento é o **topo**. `profundidade` conta a partir do topo: o topo tem profundidade 0.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao final de `mundo/testes/test_armazens.py`:

```python
def test_empilhar_coloca_no_topo_e_soma_ocupacao():
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")

    armazem.empilhar("c1", 10.0)
    armazem.empilhar("c2", 5.0)

    assert armazem.pilha == ["c1", "c2"]
    assert armazem.ocupacao == 15.0


def test_profundidade_conta_do_topo():
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    for nome in ("c1", "c2", "c3"):
        armazem.empilhar(nome, 1.0)

    assert armazem.profundidade("c3") == 0
    assert armazem.profundidade("c2") == 1
    assert armazem.profundidade("c1") == 2


def test_desempilhar_devolve_o_alvo_e_tudo_acima_do_topo_para_baixo():
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    for nome in ("c1", "c2", "c3", "c4"):
        armazem.empilhar(nome, 10.0)

    quantidades = {nome: 10.0 for nome in armazem.pilha}
    removidos = armazem.desempilhar_ate("c2", quantidades)

    assert removidos == ["c4", "c3", "c2"]
    assert armazem.pilha == ["c1"]
    assert armazem.ocupacao == 10.0


def test_desempilhar_o_topo_devolve_so_ele():
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    armazem.empilhar("c1", 10.0)
    armazem.empilhar("c2", 10.0)

    assert armazem.desempilhar_ate("c2", {"c1": 10.0, "c2": 10.0}) == ["c2"]
    assert armazem.pilha == ["c1"]


def test_desempilhar_carga_ausente_levanta():
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    armazem.empilhar("c1", 10.0)

    with pytest.raises(CargaNaoEstaNoArmazemError):
        armazem.desempilhar_ate("fantasma", {"c1": 10.0})


def test_reordenar_devolve_a_soma_dos_deslocamentos():
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    for nome in ("a", "b", "c", "d", "e"):
        armazem.empilhar(nome, 1.0)

    # Inverter cinco posições move: 4 + 2 + 0 + 2 + 4 = 12.
    movimentos = armazem.reordenar(["e", "d", "c", "b", "a"])

    assert movimentos == 12
    assert armazem.pilha == ["e", "d", "c", "b", "a"]


def test_reordenar_que_nao_muda_nada_custa_zero():
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    for nome in ("a", "b", "c"):
        armazem.empilhar(nome, 1.0)

    assert armazem.reordenar(["a", "b", "c"]) == 0


def test_reordenar_exige_permutacao_exata():
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    armazem.empilhar("a", 1.0)
    armazem.empilhar("b", 1.0)

    with pytest.raises(ValueError):
        armazem.reordenar(["a"])            # falta um
    with pytest.raises(ValueError):
        armazem.reordenar(["a", "b", "c"])  # sobra um
    with pytest.raises(ValueError):
        armazem.reordenar(["a", "a"])       # repetido


def test_ocupacao_nunca_diverge_da_pilha():
    """A ocupação é função do que está empilhado, nunca um contador à parte.

    Era exatamente essa divergência que permitia zerar a ocupação de um
    armazém cheio chamando `liberar-carga` com um número inventado.
    """
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    armazem.empilhar("c1", 7.0)
    armazem.empilhar("c2", 3.0)
    armazem.desempilhar_ate("c2", {"c1": 7.0, "c2": 3.0})

    assert armazem.pilha == ["c1"]
    assert armazem.ocupacao == 7.0
```

Garantir que o arquivo tenha `import pytest` e importe `Armazem` e `CargaNaoEstaNoArmazemError` de `mundo.dominio.armazens`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest mundo/testes/test_armazens.py -q`
Expected: FAIL com `ImportError: cannot import name 'CargaNaoEstaNoArmazemError'`.

- [ ] **Step 3: Implementar**

Em `mundo/dominio/armazens.py`, acrescentar a exceção junto de `CapacidadeExcedidaError`:

```python
class CargaNaoEstaNoArmazemError(Exception):
    pass
```

Acrescentar o campo à dataclass `Armazem`, depois de `ocupacao`:

```python
    pilha: list[str] = field(default_factory=list)
```

E os métodos, substituindo `reservar_espaco`/`liberar_espaco` como interface pública — eles continuam existindo mas passam a ser detalhe interno usado só por `empilhar`/`desempilhar_ate`:

```python
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
```

**Por que `desempilhar_ate` recebe `quantidades`:** o domínio do armazém não conhece `CargaMineral`, e importá-lo quebraria a direção de dependência que o projeto manteve intacta. O chamador — que já tem as cargas em mão — passa o mapa de identificador para quantidade. Os testes do Step 1 já chamam com esse segundo argumento.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: PASS, 199 + 9 = 208.

- [ ] **Step 5: Commit**

```bash
git add mundo/dominio/armazens.py mundo/testes/test_armazens.py
git commit -m "feat: warehouses become ordered stacks"
```

---

### Task 2: Local `NA_MAO` para carga desenterrada

**Files:**
- Modify: `mundo/dominio/cargas.py`
- Modify: `mundo/config/modos.json`
- Test: `mundo/testes/test_cargas.py`

**Interfaces:**
- Consumes: nada.
- Produces: `LocalDaCarga.NA_MAO`, e a entrada `"na_mao"` em `multiplicador_por_local`.

Carga na mão está exposta, sem proteção de armazém: usa o mesmo multiplicador de `em_jazida`, que é `2.0`. Isso dá urgência a resolver o que foi desenterrado.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `mundo/testes/test_cargas.py`:

```python
def test_carga_na_mao_usa_sensibilidade_neutra():
    """Na mão não há proteção de armazém nem cuidado de transporte."""
    carga = CargaMineral("c1", "hematita", 10.0, 100.0, local=LocalDaCarga.NA_MAO)
    mineral = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_CATALOGO).obter("hematita")

    assert carga.sensibilidade_aplicavel(mineral) == 1.0


def test_multiplicador_de_carga_na_mao_e_o_de_exposta():
    catalogo = CatalogoDeModos.carregar_de_arquivo(CAMINHO_MODOS)

    assert catalogo.mult_do_local("na_mao") == catalogo.mult_do_local("em_jazida")
```

Importar `CatalogoDeModos` de `mundo.dominio.modos` e definir `CAMINHO_MODOS = Path(__file__).parent.parent / "config" / "modos.json"` se ainda não existirem no arquivo.

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest mundo/testes/test_cargas.py -q`
Expected: FAIL com `AttributeError: NA_MAO`.

- [ ] **Step 3: Implementar**

Em `mundo/dominio/cargas.py`, acrescentar ao enum, depois de `EM_TRANSITO`:

```python
    NA_MAO = "na_mao"
```

`sensibilidade_aplicavel` já devolve `1.0` para qualquer local que não seja armazém ou trânsito, então não muda.

Em `mundo/config/modos.json`, dentro de `multiplicador_por_local`, acrescentar depois de `"em_transito"`:

```json
    "na_mao": 2.0,
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: PASS, 210.

- [ ] **Step 5: Commit**

```bash
git add mundo/dominio/cargas.py mundo/config/modos.json mundo/testes/test_cargas.py
git commit -m "feat: add the in-hand cargo location"
```

---

### Task 3: Catálogo de custos de armazenagem

**Files:**
- Create: `mundo/config/armazenagem.json`
- Create: `mundo/dominio/armazenagem.py`
- Test: `mundo/testes/test_catalogo_de_armazenagem.py` (novo)

**Interfaces:**
- Consumes: nada.
- Produces: `CatalogoDeArmazenagem.carregar_de_arquivo(caminho: Path) -> CatalogoDeArmazenagem`, com os atributos `custo_de_armazenagem_por_unidade`, `custo_de_manutencao_por_unidade`, `custo_por_movimento`, `custo_por_desempilhamento`, todos `float`.

Segue o padrão de `CatalogoDeModos` em `mundo/dominio/modos.py`: dataclass simples carregada de JSON, sem lógica além de expor os valores.

- [ ] **Step 1: Escrever o teste que falha**

Criar `mundo/testes/test_catalogo_de_armazenagem.py`:

```python
from pathlib import Path

import pytest

from mundo.dominio.armazenagem import CatalogoDeArmazenagem

CAMINHO = Path(__file__).parent.parent / "config" / "armazenagem.json"


def test_carrega_os_quatro_custos_do_arquivo():
    catalogo = CatalogoDeArmazenagem.carregar_de_arquivo(CAMINHO)

    assert catalogo.custo_de_armazenagem_por_unidade == 0.05
    assert catalogo.custo_de_manutencao_por_unidade == 0.004
    assert catalogo.custo_por_movimento == 0.3
    assert catalogo.custo_por_desempilhamento == 0.8


def test_guardar_vinte_unidades_custa_o_mesmo_que_a_taxa_fixa_antiga():
    """A mudança não pode encarecer o caso simples.

    Antes, receber uma carga custava 1 de energia fixo. Vinte unidades a
    0.05 dão exatamente 1.0, então quem não usa a pilha não paga a mais.
    """
    catalogo = CatalogoDeArmazenagem.carregar_de_arquivo(CAMINHO)

    assert catalogo.custo_de_armazenagem_por_unidade * 20.0 == pytest.approx(1.0)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest mundo/testes/test_catalogo_de_armazenagem.py -q`
Expected: FAIL com `ModuleNotFoundError: mundo.dominio.armazenagem`.

- [ ] **Step 3: Implementar**

Criar `mundo/config/armazenagem.json`:

```json
{
  "custo_de_armazenagem_por_unidade": 0.05,
  "custo_de_manutencao_por_unidade": 0.004,
  "custo_por_movimento": 0.3,
  "custo_por_desempilhamento": 0.8
}
```

Criar `mundo/dominio/armazenagem.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CatalogoDeArmazenagem:
    """Os quatro preços da armazenagem posicional.

    Volume paga guardar e manter; contagem de itens paga remexer. É essa
    assimetria que faz a ordem da pilha importar sem que nenhuma regra
    mande ordenar.
    """

    custo_de_armazenagem_por_unidade: float
    custo_de_manutencao_por_unidade: float
    custo_por_movimento: float
    custo_por_desempilhamento: float

    @classmethod
    def carregar_de_arquivo(cls, caminho: Path) -> "CatalogoDeArmazenagem":
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return cls(
            custo_de_armazenagem_por_unidade=dados["custo_de_armazenagem_por_unidade"],
            custo_de_manutencao_por_unidade=dados["custo_de_manutencao_por_unidade"],
            custo_por_movimento=dados["custo_por_movimento"],
            custo_por_desempilhamento=dados["custo_por_desempilhamento"],
        )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: PASS, 212.

- [ ] **Step 5: Commit**

```bash
git add mundo/config/armazenagem.json mundo/dominio/armazenagem.py mundo/testes/test_catalogo_de_armazenagem.py
git commit -m "feat: add the storage cost catalog"
```

---

### Task 4: Custo de manutenção no tick

**Files:**
- Modify: `mundo/motor/motor_de_simulacao.py`
- Test: `mundo/testes/test_armazenagem_posicional.py` (novo)

**Interfaces:**
- Consumes: `CatalogoDeArmazenagem` da Task 3.
- Produces: `MotorDeSimulacao.catalogo_de_armazenagem`, e o passo `_cobrar_manutencao_dos_armazens()` no tick.

A manutenção é cobrada da central `armazenagem`. Se ela não tiver saldo, a cobrança **não** pode derrubar o tick: debita o que houver e publica `armazem_sem_energia`. Um mundo que trava por dívida de manutenção é pior que um mundo endividado.

- [ ] **Step 1: Escrever os testes que falham**

Criar `mundo/testes/test_armazenagem_posicional.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.armazenagem import CatalogoDeArmazenagem

CAMINHO_ARMAZENAGEM = Path(__file__).parent.parent / "config" / "armazenagem.json"
CUSTOS = CatalogoDeArmazenagem.carregar_de_arquivo(CAMINHO_ARMAZENAGEM)


def test_manutencao_cobra_por_unidade_armazenada_a_cada_ciclo():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "armazenagem", 100)
        motor.armazens["armazem-1"].empilhar("c1", 25.0)
        antes = motor.energia.consultar_energia("armazenagem")

        motor.avancar_ciclo(1)

        esperado = 25.0 * CUSTOS.custo_de_manutencao_por_unidade
        assert antes - motor.energia.consultar_energia("armazenagem") == pytest.approx(esperado)


def test_armazem_vazio_nao_custa_manutencao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        motor.energia.alocar_energia("reserva_estrategica", "armazenagem", 100)
        antes = motor.energia.consultar_energia("armazenagem")

        motor.avancar_ciclo(3)

        assert motor.energia.consultar_energia("armazenagem") == antes


def test_manutencao_sem_saldo_nao_derruba_o_ciclo():
    """Um mundo que trava por dívida de manutenção é pior que um endividado."""
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        motor.armazens["armazem-1"].empilhar("c1", 500.0)
        ciclo_antes = motor.ciclo_atual

        motor.avancar_ciclo(1)

        assert motor.ciclo_atual == ciclo_antes + 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest mundo/testes/test_armazenagem_posicional.py -q`
Expected: FAIL — a energia não é debitada, o primeiro teste falha na comparação.

- [ ] **Step 3: Implementar**

Em `mundo/motor/motor_de_simulacao.py`, importar o catálogo junto dos demais imports de domínio:

```python
from mundo.dominio.armazenagem import CatalogoDeArmazenagem
```

No `__init__`, ao lado de `self.catalogo_de_modos` (linha ~42):

```python
        self.catalogo_de_armazenagem = catalogo_de_armazenagem or CatalogoDeArmazenagem.carregar_de_arquivo(
            Path(__file__).parent.parent / "config" / "armazenagem.json"
        )
```

Acrescentar o parâmetro `catalogo_de_armazenagem: CatalogoDeArmazenagem | None = None` à assinatura do `__init__`, seguindo o mesmo formato de `catalogo_de_modos`.

Em `_processar_um_ciclo`, acrescentar a chamada depois de `self._recuperar_desgaste()`:

```python
        self._cobrar_manutencao_dos_armazens()
```

E o método, junto dos outros passos do tick:

```python
    def _cobrar_manutencao_dos_armazens(self) -> None:
        """Guardar minério custa energia a cada ciclo, proporcional ao volume.

        A cobrança nunca derruba o tick: sem saldo, publica-se o evento e a
        simulação segue. Travar o mundo por dívida de manutenção seria pior
        que deixá-lo endividado.
        """
        total = sum(armazem.ocupacao for armazem in self.armazens.values())
        if total <= 0.0:
            return
        custo = total * self.catalogo_de_armazenagem.custo_de_manutencao_por_unidade
        try:
            self.energia.debitar("armazenagem", custo)
        except Exception as erro:
            self.eventos.publicar(
                tipo="armazem_sem_energia",
                ciclo=self.ciclo_atual,
                dados={"custo": custo, "motivo": str(erro)},
            )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: PASS, 215. Se algum teste existente falhar por energia de armazenagem drenando, verificar se ele empilha carga; testes que não empilham não pagam manutenção.

- [ ] **Step 5: Commit**

```bash
git add mundo/motor/motor_de_simulacao.py mundo/testes/test_armazenagem_posicional.py
git commit -m "feat: charge warehouse upkeep every cycle"
```

---

### Task 5: `receber-carga` empilha, reordena e cobra

**Files:**
- Modify: `mundo/api/armazenagem.py`
- Test: `mundo/testes/test_armazenagem_posicional.py`

**Interfaces:**
- Consumes: `Armazem.empilhar`, `Armazem.reordenar` (Task 1); `CatalogoDeArmazenagem` (Task 3); `LocalDaCarga.NA_MAO` (Task 2).
- Produces: `POST /armazenagem/receber-carga` com corpo `{identificador_do_armazem: str, identificadores_das_cargas: list[str], nova_ordem: list[str] | None, id_autorizacao: str}`.

O campo passa de uma carga para **lista** de cargas, porque reordenar exige poder inserir várias e depois declarar a ordem final numa única operação.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `mundo/testes/test_armazenagem_posicional.py`:

```python
def _autorizar(cliente) -> str:
    resposta = cliente.post(
        "/missao/autorizar-missao",
        json={"operacao": "receber_carga", "central_solicitante": "armazenagem"},
    )
    return resposta.json()["id_autorizacao"]


def _preparar(cliente, quantidades: dict[str, float]):
    from mundo.dominio.cargas import CargaMineral, LocalDaCarga

    motor = instancia_do_mundo.obter_motor()
    motor.energia.alocar_energia("reserva_estrategica", "armazenagem", 300)
    for nome, quantidade in quantidades.items():
        motor.cargas[nome] = CargaMineral(
            nome, "hematita", quantidade, 100.0, local=LocalDaCarga.NA_MAO,
        )
    return motor


def test_receber_empilha_na_ordem_dada_e_cobra_por_unidade():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 10.0, "c2": 20.0})
        antes = motor.energia.consultar_energia("armazenagem")

        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1", "c2"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        armazem = motor.armazens["armazem-1"]
        assert armazem.pilha == ["c1", "c2"]
        gasto = antes - motor.energia.consultar_energia("armazenagem")
        manutencao = armazem.ocupacao * CUSTOS.custo_de_manutencao_por_unidade
        esperado = 30.0 * CUSTOS.custo_de_armazenagem_por_unidade + manutencao
        assert gasto == pytest.approx(esperado)


def test_nova_ordem_reordena_a_pilha_e_cobra_por_movimento():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 1.0, "c2": 1.0, "c3": 1.0})
        armazem = motor.armazens["armazem-1"]
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1", "c2"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)
        antes = motor.energia.consultar_energia("armazenagem")

        # Insere c3 e declara a ordem final invertida: [c1,c2,c3] -> [c3,c2,c1].
        # Deslocamentos: c3 2->0 (2), c2 1->1 (0), c1 0->2 (2) = 4.
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c3"],
            "nova_ordem": ["c3", "c2", "c1"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        assert armazem.pilha == ["c3", "c2", "c1"]
        gasto = antes - motor.energia.consultar_energia("armazenagem")
        manutencao = armazem.ocupacao * CUSTOS.custo_de_manutencao_por_unidade
        esperado = (
            1.0 * CUSTOS.custo_de_armazenagem_por_unidade
            + 4 * CUSTOS.custo_por_movimento
            + manutencao
        )
        assert gasto == pytest.approx(esperado)


def test_sem_nova_ordem_nada_se_move_e_nao_ha_custo_de_movimento():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 1.0, "c2": 1.0})
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)
        antes = motor.energia.consultar_energia("armazenagem")

        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c2"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        armazem = motor.armazens["armazem-1"]
        manutencao = armazem.ocupacao * CUSTOS.custo_de_manutencao_por_unidade
        gasto = antes - motor.energia.consultar_energia("armazenagem")
        esperado = 1.0 * CUSTOS.custo_de_armazenagem_por_unidade + manutencao
        assert gasto == pytest.approx(esperado)


def test_nova_ordem_que_nao_e_permutacao_e_operacao_invalida():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 1.0})
        invalidas = []
        motor.eventos.assinar(
            lambda e: invalidas.append(e) if e.tipo == "operacao_invalida" else None
        )

        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1"],
            "nova_ordem": ["c1", "fantasma"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        assert invalidas, "ordem inválida deveria publicar operacao_invalida"
        assert motor.armazens["armazem-1"].pilha == []


def test_receber_carga_move_para_em_armazem():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 5.0})

        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        from mundo.dominio.cargas import LocalDaCarga
        assert motor.cargas["c1"].local == LocalDaCarga.EM_ARMAZEM
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest mundo/testes/test_armazenagem_posicional.py -q`
Expected: FAIL — o corpo antigo usa `identificador_da_carga`, então o Pydantic rejeita com 422 e a pilha fica vazia.

- [ ] **Step 3: Implementar**

Em `mundo/api/armazenagem.py`, substituir `RequisicaoDeRecebimento` e `receber_carga` por:

```python
class RequisicaoDeRecebimento(BaseModel):
    identificador_do_armazem: str
    identificadores_das_cargas: list[str]
    nova_ordem: list[str] | None = None
    id_autorizacao: str


@router.post("/receber-carga")
async def receber_carga(requisicao: RequisicaoDeRecebimento) -> dict:
    motor = obter_motor()
    armazem = motor.armazens.get(requisicao.identificador_do_armazem)
    if armazem is None:
        raise HTTPException(status_code=404, detail="Armazém não encontrado")
    for identificador in requisicao.identificadores_das_cargas:
        if identificador not in motor.cargas:
            raise HTTPException(status_code=404, detail="Carga não encontrada")

    def executar() -> None:
        motor.autorizacoes.consumir(requisicao.id_autorizacao, "receber_carga")
        custos = motor.catalogo_de_armazenagem
        total = 0.0
        for identificador in requisicao.identificadores_das_cargas:
            carga = motor.cargas[identificador]
            if not armazem.compativel_com(carga.mineral):
                motor.eventos.publicar(
                    "carga_contaminada",
                    motor.ciclo_atual,
                    {"carga": carga.identificador, "armazem": armazem.identificador},
                )
                raise ValueError("Mineral incompatível com o armazém")
            total += carga.quantidade * custos.custo_de_armazenagem_por_unidade

        # A ordem é validada ANTES de empilhar. `executar()` roda dentro do
        # try do motor, então levantar aqui vira `operacao_invalida` — mas se
        # as cargas já tivessem sido empilhadas, a pilha ficaria alterada por
        # uma operação que o mundo registrou como inválida.
        if requisicao.nova_ordem is not None:
            pilha_resultante = armazem.pilha + list(requisicao.identificadores_das_cargas)
            if sorted(requisicao.nova_ordem) != sorted(pilha_resultante):
                raise ValueError(
                    "A nova ordem precisa ser uma permutação exata da pilha resultante"
                )

        for identificador in requisicao.identificadores_das_cargas:
            armazem.empilhar(identificador, motor.cargas[identificador].quantidade)

        movimentos = 0
        if requisicao.nova_ordem is not None:
            movimentos = armazem.reordenar(requisicao.nova_ordem)
            total += movimentos * custos.custo_por_movimento

        motor.energia.debitar(CENTRAL, total)
        for identificador in requisicao.identificadores_das_cargas:
            motor.cargas[identificador].mover_para(LocalDaCarga.EM_ARMAZEM)

        motor.eventos.publicar(
            "cargas_armazenadas",
            motor.ciclo_atual,
            {
                "armazem": armazem.identificador,
                "cargas": list(requisicao.identificadores_das_cargas),
                "movimentos": movimentos,
                "custo": total,
            },
        )
        if armazem.ocupacao >= armazem.capacidade:
            motor.eventos.publicar(
                "armazem_lotado", motor.ciclo_atual, {"armazem": armazem.identificador},
            )
        elif armazem.ocupacao >= armazem.capacidade * LIMIAR_PROXIMO_DA_CAPACIDADE:
            motor.eventos.publicar(
                "armazem_proximo_da_capacidade",
                motor.ciclo_atual,
                {"armazem": armazem.identificador},
            )

    motor.enfileirar_comando(Comando("receber_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}
```

**Por que a validação vem antes de empilhar:** `executar()` roda dentro do `try` do motor, então qualquer exceção vira `operacao_invalida` e o tick sobrevive — mas o que já foi mutado antes da exceção **permanece mutado**. Validar depois de empilhar deixaria a pilha alterada por uma operação que o mundo registrou como inválida, que é a mesma classe de bug do débito de energia antes da validação corrigido em `extracao.py`. O teste `test_nova_ordem_que_nao_e_permutacao_e_operacao_invalida` afirma pilha vazia justamente para prender isso.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: os testes novos passam. Testes existentes que chamam `receber-carga` com `identificador_da_carga` vão quebrar — são de `test_api_armazenagem.py`, `test_api_transporte.py` e `test_desgaste.py`. Atualizá-los para o corpo novo (lista com um elemento) é mudança mecânica de chamada, não de asserção; registrar no relatório quais foram tocados.

- [ ] **Step 5: Commit**

```bash
git add mundo/api/armazenagem.py mundo/testes/
git commit -m "feat: receiving cargo stacks it and optionally reorders"
```

---

### Task 6: `retirar-carga` destrutivo e remoção dos endpoints incoerentes

**Files:**
- Modify: `mundo/api/armazenagem.py`
- Test: `mundo/testes/test_armazenagem_posicional.py`

**Interfaces:**
- Consumes: `Armazem.desempilhar_ate`, `Armazem.profundidade` (Task 1).
- Produces: `POST /armazenagem/retirar-carga` com corpo `{identificador_do_armazem: str, identificador_da_carga: str, id_autorizacao: str}`, e o evento `cargas_desempilhadas`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `mundo/testes/test_armazenagem_posicional.py`:

```python
def test_retirar_devolve_o_alvo_e_tudo_acima_para_a_mao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 1.0, "c2": 1.0, "c3": 1.0})
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1", "c2", "c3"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        cliente.post("/armazenagem/retirar-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificador_da_carga": "c1",
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        from mundo.dominio.cargas import LocalDaCarga
        assert motor.armazens["armazem-1"].pilha == []
        for nome in ("c1", "c2", "c3"):
            assert motor.cargas[nome].local == LocalDaCarga.NA_MAO


def test_retirar_cobra_por_profundidade():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 1.0, "c2": 1.0, "c3": 1.0})
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1", "c2", "c3"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)
        antes = motor.energia.consultar_energia("armazenagem")

        # c1 está no fundo de uma pilha de três: profundidade 2.
        cliente.post("/armazenagem/retirar-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificador_da_carga": "c1",
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        gasto = antes - motor.energia.consultar_energia("armazenagem")
        assert gasto == pytest.approx(2 * CUSTOS.custo_por_desempilhamento)


def test_retirar_do_topo_nao_custa_desempilhamento():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 1.0, "c2": 1.0})
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1", "c2"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)
        antes = motor.energia.consultar_energia("armazenagem")

        cliente.post("/armazenagem/retirar-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificador_da_carga": "c2",
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        gasto_sem_manutencao = (
            antes
            - motor.energia.consultar_energia("armazenagem")
            - motor.armazens["armazem-1"].ocupacao * CUSTOS.custo_de_manutencao_por_unidade
        )
        assert gasto_sem_manutencao == pytest.approx(0.0)


def test_ocupacao_volta_a_zero_depois_de_retirar_tudo():
    """Regressão do vazamento que travava o mundo.

    Antes, entregar uma carga removia-a do mundo sem liberar espaço: a
    ocupação só subia. Com 1000 de capacidade contra 1484 de minério, quem
    processasse minério demais entupia os dois armazéns sem volta.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {f"c{i}": 20.0 for i in range(5)})
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": [f"c{i}" for i in range(5)],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)
        assert motor.armazens["armazem-1"].ocupacao == 100.0

        cliente.post("/armazenagem/retirar-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificador_da_carga": "c0",
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)

        assert motor.armazens["armazem-1"].ocupacao == 0.0
        assert motor.armazens["armazem-1"].pilha == []


def test_endpoints_incoerentes_com_a_pilha_sumiram():
    """Os três escreviam ocupação sem referência a carga alguma.

    Era o que permitia zerar um armazém cheio com um número inventado.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        for rota in ("liberar-carga", "realocar-carga", "reservar-espaco"):
            resposta = cliente.post(f"/armazenagem/{rota}", json={})
            assert resposta.status_code == 404, f"{rota} ainda existe"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest mundo/testes/test_armazenagem_posicional.py -q`
Expected: FAIL — `retirar-carga` devolve 404 e os três endpoints removidos ainda respondem 422 em vez de 404.

- [ ] **Step 3: Implementar**

Em `mundo/api/armazenagem.py`, **remover** por completo: `RequisicaoDeReserva` e `reservar_espaco`, `RequisicaoDeRealocacao` e `realocar_carga`, `RequisicaoDeLiberacao` e `liberar_carga`. Remover também a constante `CUSTO_ENERGETICO_OPERACAO`, que fica sem uso.

Acrescentar:

```python
class RequisicaoDeRetirada(BaseModel):
    identificador_do_armazem: str
    identificador_da_carga: str
    id_autorizacao: str


@router.post("/retirar-carga")
async def retirar_carga(requisicao: RequisicaoDeRetirada) -> dict:
    motor = obter_motor()
    armazem = motor.armazens.get(requisicao.identificador_do_armazem)
    if armazem is None:
        raise HTTPException(status_code=404, detail="Armazém não encontrado")

    def executar() -> None:
        motor.autorizacoes.consumir(requisicao.id_autorizacao, "retirar_carga")
        # A profundidade é medida antes de mexer na pilha: é ela que define o
        # preço, e depois de desempilhar não há mais o que medir.
        profundidade = armazem.profundidade(requisicao.identificador_da_carga)
        custo = profundidade * motor.catalogo_de_armazenagem.custo_por_desempilhamento
        motor.energia.debitar(CENTRAL, custo)

        quantidades = {nome: motor.cargas[nome].quantidade for nome in armazem.pilha}
        removidos = armazem.desempilhar_ate(requisicao.identificador_da_carga, quantidades)
        for nome in removidos:
            motor.cargas[nome].mover_para(LocalDaCarga.NA_MAO)

        motor.eventos.publicar(
            "cargas_desempilhadas",
            motor.ciclo_atual,
            {
                "armazem": armazem.identificador,
                "alvo": requisicao.identificador_da_carga,
                "cargas": removidos,
                "profundidade": profundidade,
                "custo": custo,
            },
        )

    motor.enfileirar_comando(Comando("retirar_carga", CENTRAL, requisicao.model_dump(), executar))
    return {"aceito": True}
```

Ajustar `descartar_carga` para exigir que a carga esteja `NA_MAO` e não mexer em ocupação — quando ela é descartada já saiu da pilha:

```python
    def executar() -> None:
        carga = motor.cargas[requisicao.identificador_da_carga]
        if carga.local != LocalDaCarga.NA_MAO:
            raise ValueError("Só se descarta carga que está na mão")
        del motor.cargas[requisicao.identificador_da_carga]
        motor.eventos.publicar("carga_descartada", motor.ciclo_atual, {"carga": carga.identificador})
```

Remover `identificador_do_armazem` de `RequisicaoDeDescarte`.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: PASS. Testes existentes que usavam os endpoints removidos precisam sair ou ser reescritos — verificar `test_api_armazenagem.py`. Remover teste que só exercitava endpoint removido é correto; registrar quais no relatório.

- [ ] **Step 5: Commit**

```bash
git add mundo/api/armazenagem.py mundo/testes/
git commit -m "feat: retrieval is destructive and unstacks everything above"
```

---

### Task 7: Transporte e distribuição exigem carga na mão

**Files:**
- Modify: `mundo/api/transporte.py`
- Modify: `mundo/api/pesquisa.py`
- Test: `mundo/testes/test_armazenagem_posicional.py`

**Interfaces:**
- Consumes: `LocalDaCarga.NA_MAO` (Task 2).
- Produces: nenhuma assinatura nova; muda a pré-condição de duas rotas existentes.

Entrar na pilha passa a ser sempre ação paga e explícita. A viagem termina com a carga na mão no destino, não dentro de um armazém.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `mundo/testes/test_armazenagem_posicional.py`:

```python
def test_nao_se_transporta_carga_que_esta_enterrada():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 1.0})
        motor.energia.alocar_energia("reserva_estrategica", "transporte", 100)
        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": ["c1"],
            "id_autorizacao": _autorizar(cliente),
        })
        motor.avancar_ciclo(1)
        invalidas = []
        motor.eventos.assinar(
            lambda e: invalidas.append(e) if e.tipo == "operacao_invalida" else None
        )

        autorizacao = cliente.post("/missao/autorizar-missao", json={
            "operacao": "iniciar_viagem", "central_solicitante": "transporte",
        }).json()["id_autorizacao"]
        cliente.post("/transporte/iniciar-viagem", json={
            "identificador_da_unidade": "transportadora-1",
            "identificador_da_rota": "rota-1",
            "identificador_da_carga": "c1",
            "id_autorizacao": autorizacao,
        })
        motor.avancar_ciclo(1)

        assert invalidas, "transportar carga empilhada deveria ser inválido"


def test_viagem_termina_com_a_carga_na_mao():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = _preparar(cliente, {"c1": 1.0})
        motor.energia.alocar_energia("reserva_estrategica", "transporte", 100)

        autorizacao = cliente.post("/missao/autorizar-missao", json={
            "operacao": "iniciar_viagem", "central_solicitante": "transporte",
        }).json()["id_autorizacao"]
        cliente.post("/transporte/iniciar-viagem", json={
            "identificador_da_unidade": "transportadora-1",
            "identificador_da_rota": "rota-1",
            "identificador_da_carga": "c1",
            "id_autorizacao": autorizacao,
        })
        for _ in range(8):
            motor.avancar_ciclo(1)

        from mundo.dominio.cargas import LocalDaCarga
        assert motor.cargas["c1"].local == LocalDaCarga.NA_MAO
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest mundo/testes/test_armazenagem_posicional.py -q`
Expected: FAIL — a viagem parte de carga empilhada sem reclamar, e termina em `EM_ARMAZEM`.

- [ ] **Step 3: Implementar**

Em `mundo/api/transporte.py`, dentro do `executar()` de `iniciar_viagem`, antes do débito de energia:

```python
        if carga.local != LocalDaCarga.NA_MAO:
            raise ValueError("Só se transporta carga que está na mão")
```

Na conclusão da viagem, trocar o destino:

```python
            carga_em_transito.mover_para(LocalDaCarga.NA_MAO)
```

Em `mundo/api/pesquisa.py`, no `executar()` de `preparar_distribuicao`, antes de faturar:

```python
        if carga.local != LocalDaCarga.NA_MAO:
            raise ValueError("Só se distribui carga que está na mão")
```

E remover a linha que mudava o local para `ENTREGUE` antes do `del`, se ela existir — a carga sai do mundo no mesmo passo, então o estado intermediário não é observável.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest mundo/testes -q`
Expected: PASS. Testes existentes de transporte e pesquisa que criavam carga com local padrão vão quebrar; ajustar para `local=LocalDaCarga.NA_MAO` na construção é mudança de preparação, não de asserção.

- [ ] **Step 5: Commit**

```bash
git add mundo/api/transporte.py mundo/api/pesquisa.py mundo/testes/
git commit -m "feat: transport and delivery require cargo in hand"
```

---

### Task 8: Suíte de dominância da armazenagem

**Files:**
- Create: `mundo/testes/test_dominancia_de_armazenagem.py`
- Modify: `mundo/config/armazenagem.json` (só se a calibração falhar)

**Interfaces:**
- Consumes: tudo das tarefas 1 a 7.
- Produces: nada consumido por outras tarefas.

Esta é a tarefa que protege o sub-projeto do defeito que este projeto já produziu quatro vezes: um mecanismo que, em vez de criar decisão, cria obrigação. **Se um teste falhar, o que muda é `armazenagem.json`, nunca a asserção.**

- [ ] **Step 1: Escrever os testes**

Criar `mundo/testes/test_dominancia_de_armazenagem.py`:

```python
"""A ordem da pilha precisa ser uma decisão, não uma obrigação.

Estes testes provam três coisas: que ordenar pela chave certa rende mais que
ordenar pela chave óbvia, que atingir a ordem-alvo com movimento mínimo é mais
barato que remontar a pilha, e que quem nunca reordena continua jogando.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mundo.api.app import criar_app
from mundo.api.dependencias import instancia_do_mundo
from mundo.dominio.cargas import CargaMineral, LocalDaCarga
from mundo.dominio.minerais import CatalogoDeMinerais

CAMINHO_MINERAIS = Path(__file__).parent.parent / "config" / "minerais.json"
MINERAIS = CatalogoDeMinerais.carregar_de_arquivo(CAMINHO_MINERAIS)

# Um de cada mineral do catálogo, mesma quantidade, para isolar a ordem como
# única variável.
SORTIMENTO = [m.nome for m in MINERAIS.todos()]
QUANTIDADE = 10.0


def _perda_de_valor_por_ciclo(nome: str) -> float:
    mineral = MINERAIS.obter(nome)
    return (
        mineral.taxa_degradacao
        * mineral.sensibilidade_armazenagem
        * mineral.valor_por_unidade
    )


def _autorizar(cliente, operacao: str, central: str) -> str:
    return cliente.post(
        "/missao/autorizar-missao",
        json={"operacao": operacao, "central_solicitante": central},
    ).json()["id_autorizacao"]


def _faturar_na_ordem(ordem_de_armazenagem: list[str], ciclos_entre_entregas: int = 3) -> float:
    """Guarda o sortimento na ordem dada, entrega tudo, e devolve o faturamento.

    As entregas saem sempre do topo, porque é o que uma estratégia racional
    faz. O que varia entre os cenários é só a ordem em que se guardou.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        motor = instancia_do_mundo.obter_motor()
        for central in ("armazenagem", "pesquisa"):
            motor.energia.alocar_energia("reserva_estrategica", central, 300)
        for nome in ordem_de_armazenagem:
            motor.cargas[nome] = CargaMineral(
                nome, nome, QUANTIDADE, 100.0, local=LocalDaCarga.NA_MAO,
            )

        cliente.post("/armazenagem/receber-carga", json={
            "identificador_do_armazem": "armazem-1",
            "identificadores_das_cargas": list(ordem_de_armazenagem),
            "id_autorizacao": _autorizar(cliente, "receber_carga", "armazenagem"),
        })
        motor.avancar_ciclo(1)

        faturamento_antes = motor.faturamento_total
        for _ in range(len(ordem_de_armazenagem)):
            topo = motor.armazens["armazem-1"].pilha[-1]
            cliente.post("/armazenagem/retirar-carga", json={
                "identificador_do_armazem": "armazem-1",
                "identificador_da_carga": topo,
                "id_autorizacao": _autorizar(cliente, "retirar_carga", "armazenagem"),
            })
            motor.avancar_ciclo(1)
            cliente.post("/pesquisa/preparar-distribuicao", json={
                "identificador_da_carga": topo,
                "id_autorizacao": _autorizar(cliente, "preparar_distribuicao", "pesquisa"),
            })
            motor.avancar_ciclo(ciclos_entre_entregas)

        return motor.faturamento_total - faturamento_antes


def test_ordenar_pela_perda_de_valor_rende_mais_que_ordenar_pelo_preco():
    """A chave certa não é a óbvia.

    O que sai primeiro deve ser o que perde valor mais depressa parado, e
    isso combina três campos do catálogo. Ordenar pelo preço — o palpite
    natural — coloca o cristal no topo quando quem sangra mais rápido é o
    gelo. As duas ordens divergem exatamente no topo, que é onde pesa.
    """
    # A pilha entrega do topo para o fundo, então o primeiro a sair fica por
    # último na ordem de armazenagem.
    por_perda = sorted(SORTIMENTO, key=_perda_de_valor_por_ciclo)
    por_preco = sorted(SORTIMENTO, key=lambda n: MINERAIS.obter(n).valor_por_unidade)

    assert por_perda != por_preco, (
        "o catálogo precisa fazer as duas chaves divergirem, senão este teste "
        "não prova nada"
    )
    assert _faturar_na_ordem(por_perda) > _faturar_na_ordem(por_preco)


def test_movimento_minimo_custa_menos_que_remontar_a_pilha():
    """A implementação esperta é recompensada.

    Como reordenar cobra por deslocamento, atingir a ordem-alvo preservando a
    maior parte já correta é estritamente mais barato que reescrever tudo.
    """
    app = criar_app(com_loop_real_time=False)
    with TestClient(app):
        motor = instancia_do_mundo.obter_motor()
        armazem = motor.armazens["armazem-1"]
        for nome in ("a", "b", "c", "d", "e"):
            armazem.empilhar(nome, 1.0)

        # Trocar só as duas do topo.
        movimentos_minimos = armazem.reordenar(["a", "b", "c", "e", "d"])
        armazem.reordenar(["a", "b", "c", "d", "e"])
        # Inverter tudo.
        movimentos_totais = armazem.reordenar(["e", "d", "c", "b", "a"])

        assert movimentos_minimos < movimentos_totais
        assert movimentos_minimos == 2
        assert movimentos_totais == 12


def test_quem_nunca_reordena_continua_jogando():
    """Reordenar precisa ser vantagem, nunca obrigação.

    Se uma estratégia que só empilha e desempilha não conseguir completar as
    entregas dentro do orçamento, o mecanismo virou pedágio e a calibração é
    que está errada.
    """
    faturamento = _faturar_na_ordem(list(SORTIMENTO))

    assert faturamento > 0.0, (
        "empilhar sem pensar precisa continuar sendo uma estratégia viável"
    )
```

- [ ] **Step 2: Rodar**

Run: `.venv/bin/pytest mundo/testes/test_dominancia_de_armazenagem.py -q`

- [ ] **Step 3: Se algum falhar, recalibrar `armazenagem.json`**

**Nunca ajustar a asserção.** As alavancas são os quatro custos. Diagnóstico:

- Se `test_ordenar_pela_perda...` falha, a degradação em armazém não está pesando o bastante contra os custos de operação: baixar `custo_por_desempilhamento` e `custo_por_movimento`, ou subir `custo_de_manutencao_por_unidade`, para que o tempo parado domine.
- Se `test_quem_nunca_reordena...` falha, os custos estão altos demais em termos absolutos: baixar todos proporcionalmente.
- Se não houver combinação que satisfaça os dois, reportar BLOCKED com os números e a região varrida. É achado legítimo — significa que os quatro custos não bastam para criar a decisão, e isso é informação valiosa.

- [ ] **Step 4: Mutation-check**

Verificar que os testes conseguem falhar. Zerar `custo_por_desempilhamento` na cópia de trabalho e confirmar que `test_ordenar_pela_perda...` muda de veredito ou fica marginal; restaurar e confirmar `git diff mundo/config/armazenagem.json` vazio. Registrar o resultado no relatório.

- [ ] **Step 5: Commit**

```bash
git add mundo/testes/test_dominancia_de_armazenagem.py mundo/config/armazenagem.json
git commit -m "test: prove stack ordering is a decision and not a toll"
```

---

### Task 9: Documentação no glossário

**Files:**
- Modify: `docs/LINGUAGEM_DO_DOMINIO.md`

**Interfaces:**
- Consumes: valores finais de `mundo/config/armazenagem.json`.
- Produces: nada.

- [ ] **Step 1: Confirmar os números**

A Task 8 pode ter recalibrado. Ler `mundo/config/armazenagem.json` e usar os valores que estão lá, não os do plano.

Run: `cat mundo/config/armazenagem.json`

- [ ] **Step 2: Escrever as entradas**

Acrescentar ao final de `docs/LINGUAGEM_DO_DOMINIO.md`, seguindo o estilo das entradas existentes (título `##`, um a três parágrafos, referências a arquivo quando ajudam):

- **Pilha do Armazém** — lista ordenada de identificadores em `Armazem.pilha`; índice 0 é o fundo, o último é o topo. Ocupação é função do que está empilhado, nunca um contador escrito à parte — foi justamente essa divergência que permitia zerar um armazém cheio com um número inventado.
- **Retirada Destrutiva** — alcançar carga enterrada desenterra tudo acima, e o que sobe vai para a mão. Recolocar é decisão nova e paga. Por isso o custo por profundidade não é fórmula: ele cai de ter que rearmazenar.
- **Na Mão** — `LocalDaCarga.NA_MAO`, estado de quem saiu da pilha e ainda não voltou nem partiu. Degrada com o multiplicador de exposta (2.0), o mesmo da jazida, o que dá urgência a resolver o que foi desenterrado.
- **Custos da Armazenagem** — os quatro preços e a assimetria deliberada: volume paga guardar e manter, contagem de itens paga remexer.
- **Ordem de Armazenagem** — a decisão central. A chave certa é a perda de valor por ciclo (`taxa_degradacao × sensibilidade_armazenagem × valor_por_unidade`), sob a qual o gelo de água supera o cristal marciano raro apesar de valer um quinto. Citar que o custo de reordenar ser a soma dos deslocamentos torna o movimento mínimo uma otimização a mais.

Acrescentar à entrada existente de **Degradação por Ciclo** uma frase sobre `na_mao` usar o multiplicador de exposta.

Registrar também, numa frase, a consequência aceita: com guardar e manter cobrando por unidade, o tamanho do lote deixa de ser decisão estratégica — extrair no maior lote possível domina. Nenhum documento deve afirmar o contrário.

- [ ] **Step 3: Commit**

```bash
git add docs/LINGUAGEM_DO_DOMINIO.md
git commit -m "docs: document positional storage in the domain glossary"
```

---

## Auto-revisão do plano

**Cobertura da spec:**

| seção da spec | tarefa |
|---|---|
| §2 pilha ordenada, retirada destrutiva | 1, 6 |
| §2 chave de ordenação e movimento mínimo | 8 |
| §3 pilha em `Armazem`, ocupação como volume | 1 |
| §3 guardar e reordenar são a mesma ação | 5 |
| §3 volume paga guardar/manter, itens pagam remexer | 3, 4, 5, 6 |
| §3 remoção dos três endpoints | 6 |
| §3 tamanho do lote deixa de ser decisão | 9 (documentado) |
| §4 métodos do domínio, `NA_MAO`, multiplicador | 1, 2 |
| §5 os quatro custos e valores | 3 |
| §6 rotas alteradas e removidas | 5, 6, 7 |
| §7 os quatro testes | 6 (regressão), 8 (os outros três) |

Sem lacunas.

**Consistência de tipos:** `desempilhar_ate(identificador, quantidades)` tem dois parâmetros em todos os lugares — Task 1 (definição e testes, com a nota do Step 3), Task 6 (chamada). `reordenar` devolve `int` e é usado como `int` na Task 5. `profundidade` conta do topo, e a Task 6 usa isso para cobrar. `LocalDaCarga.NA_MAO` definido na Task 2, usado nas 5, 6, 7 e 8.

**Sem placeholders:** todos os passos de código têm código. O único ponto sem valores fixos é a recalibração da Task 8, deliberadamente — os valores dependem da medição, e o passo diz exatamente qual alavanca mexer para cada falha e quando reportar BLOCKED.
