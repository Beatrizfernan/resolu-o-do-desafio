# Task 7 — Suíte de dominância — BLOCKED (parcial)

Commit: `58ad8bf`

Resultado: `.venv/bin/pytest mundo/testes -q` → **3 failed, 164 passed**.
Os 3 vermelhos são os testes de dominância de **extração**; os 3 de **transporte**
passam após uma recalibração de `mundo/config/modos.json`. Nenhum teste
pré-existente quebrou.

O arquivo `mundo/testes/test_dominancia_de_modos.py` foi escrito **exatamente**
como no brief. Nenhuma asserção foi enfraquecida, nenhum cenário removido.

---

## 1. Transporte — RESOLVIDO por recalibração da config

### Diagnóstico

Com a calibração anterior o **econômico vencia nos 30 cenários da grade**
(5 minerais × 6 tempos de rota). Normal e rápido nunca venciam.

Motivo: na métrica `valor / energia`, o valor entra só pela qualidade
sobrevivente (`q/100`) e a energia pelo `mult_energia`. O vencedor é
`argmax q_modo / mult_energia_modo`. A perda de qualidade numa viagem era
pequena — o pior caso do catálogo é gelo_de_água numa rota de 30 ciclos:
`taxa 0.9 × sens_transporte 0.5 = 0.45/ciclo`, ou ~13 pontos de 100 no modo
normal. Contra isso, o `mult_energia` variava 3× (0.6 → 1.8). Uma vantagem de
qualidade de no máximo ~15% nunca compensa uma desvantagem de energia de 200%.

### Números alterados (`mundo/config/modos.json`, bloco `transporte`)

| modo | campo | antes | depois |
|---|---|---|---|
| economico | mult_energia | 0.6 | **0.85** |
| economico | mult_duracao | 1.5 | **2.0** |
| economico | mult_degradacao | 1.3 | **2.5** |
| rapido | mult_energia | 1.8 | **1.05** |
| rapido | mult_duracao | 0.6 | **0.5** |
| rapido | mult_degradacao | 0.8 | **0.5** |

`normal` ficou intocado (1.0/1.0/1.0) — ele é a âncora numérica de
`test_api_transporte.py:278` (qualidade 89.88), de `test_api_transporte.py:144`
(custo 3) e da duração exata `tempo_base`. Mexer nele quebraria testes
pré-existentes.

### Raciocínio

- **Aproximar os custos de energia (0.85 / 1.0 / 1.05).** É o ajuste essencial.
  O teto é estrutural: a qualidade perdida pelo modo normal no pior cenário da
  grade é ~13.5 pontos, então o prêmio de energia do rápido tem de ser menor que
  ~15% para ele ser escolhível em algum lugar. 1.05 dá margem.
- **Ampliar o contraste de degradação (2.5 vs 0.5).** É o que dá ao econômico
  uma desvantagem real e transforma a decisão em trade-off: o barato só é barato
  para minério estável ou rota curta.
- **Duração 2.0 vs 0.5.** Reforça o mesmo eixo (mais ciclos expostos → mais
  degradação) e mantém a leitura narrativa dos modos.

Ordenações fixadas por `test_modos.py` continuam válidas:
`rapido.mult_energia > economico.mult_energia`, `rapido.mult_duracao <
economico.mult_duracao`, `rapido.mult_degradacao < economico.mult_degradacao`.

### Mapa de vencedores resultante (grade completa)

- **economico**: hematita e sílica em todas as rotas; cristal marciano em todas
  as rotas; gelo e jarosita em rotas curtas (3, 5, 8).
- **normal**: gelo e jarosita em rota média (12).
- **rapido**: gelo e jarosita em rotas longas (20, 30).

Cada modo é a melhor escolha numa faixa nítida — é exatamente o comportamento
que a spec pede.

---

## 2. Extração — BLOCKED (impossível por construção da métrica)

Os três testes de extração **não podem passar juntos com calibração nenhuma**.
Não é um problema de números em `modos.json`; é a métrica do helper.

### Prova

`_retorno_da_extracao` calcula:

```
retorno = [ Q·V·(q_i/100) − Q·(f_d−1)·V ] / [ c·Q·f_base·m_e ]
        = ( V / (c · f_base) ) · [ q_i/100 − (f_d − 1) ] / m_e
                └──────────────┘   └──────────────────────────┘
                 só do mineral            só do modo
```

O termo do mineral (`V / c`) é um **fator comum positivo** que multiplica os três
modos igualmente. Ele não muda o `argmax`. Logo o ranking dos modos de extração
é **idêntico para todo mineral do catálogo**, e um único modo vence sempre.

Consequência direta: `test_cuidadoso_vence_em_mineral_caro_e_escasso` e
`test_agressivo_vence_em_mineral_barato` são **mutuamente contraditórios**, e
`test_todo_modo_de_extracao_vence_em_algum_mineral_do_catalogo` sempre reportará
dois modos ausentes. Nenhum valor de `mult_energia`, `qualidade_inicial` ou
`fator_desperdicio` altera isso (o único trecho não-linear seria o clamp de
qualidade em 100, que também é independente do mineral).

Termos por modo na calibração atual (`[q_i/100 − (f_d−1)] / m_e`):

| modo | termo | vence em |
|---|---|---|
| cuidadoso | 0.6250 | nenhum mineral |
| **normal** | **0.7700** | **todos os 5** |
| agressivo | 0.5429 | nenhum mineral |

### O que está faltando na métrica

O nome do teste diz o que a fórmula esqueceu: *"mineral caro **e escasso**"*.
`raridade` não aparece no cálculo. Ela é justamente o eixo que diferencia os
minerais entre si de forma **não proporcional** a `V/c` — destruir 4 unidades de
cristal marciano raro (raridade 0.95) custa mais que o preço de mercado delas,
porque a jazida é finita; destruir hematita (raridade 0.1) não custa quase nada
além do minério.

### Correção sugerida (precisa de decisão de quem escreveu o brief)

Ponderar o desperdício pela raridade, uma linha em `_retorno_da_extracao`:

```python
valor_perdido = desperdicado * mineral.valor_por_unidade * (1 + mineral.raridade * K)
```

Com um `K` calibrável, o `fator_desperdicio` do agressivo passa a doer muito em
minério raro e quase nada em minério comum — e aí cuidadoso, normal e agressivo
vencem em faixas diferentes do catálogo, exatamente como no transporte.

**Não apliquei essa mudança**: a instrução da task é explícita — o teste não se
mexe, só a config. Mas aqui a config comprovadamente não tem grau de liberdade
suficiente, então a decisão volta para quem definiu a métrica. As alternativas
são (a) corrigir o helper como acima, ou (b) introduzir em `modos.json` um eixo
de extração sensível ao mineral (ex.: desperdício que escala com raridade), o
que também é uma mudança de fórmula no domínio, não só de números.

---

## Checklist do brief

- [x] Step 1 — suíte escrita literalmente como especificado
- [~] Step 2 — 3/6 passam; extração bloqueada por impossibilidade da métrica
- [x] Step 3 — suíte completa: 164 passam, só os 3 de extração falham
- [x] Step 4 — commit `58ad8bf` (sem `--no-verify`)
