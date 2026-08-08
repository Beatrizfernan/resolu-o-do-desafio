# Design — Modos de Operação e Degradação por Ciclo

## 1. Contexto

O núcleo mecânico do `mundo/` está em `main`: domínio, motor de ciclos, e as APIs das cinco Centrais. Hoje as ações são de custo fixo — extração custa 2 de energia, dura 5 ciclos e sempre produz carga com qualidade 100; transporte custa 3 e degrada a carga por `rota.risco` (0.05–0.08, desprezível). Não existe decisão: só há uma forma de fazer cada coisa.

Este documento especifica o sub-projeto **B** de uma evolução maior, que introduz possibilidades estratégicas ao mundo. B entrega os **modos de operação** — o primeiro eixo de trade-off real — e a **degradação por ciclo**, que é o que faz tempo custar dinheiro.

### Onde B se encaixa

A evolução completa foi decomposta em cinco sub-projetos:

| # | Sub-projeto | Estado |
|---|---|---|
| **A** | Informação incompleta, regiões e exploração | spec futura |
| **B** | **Modos de operação e degradação** | **este documento** |
| **C** | Armazenagem com custo de organização | spec futura |
| **D** | Central: missões e alocação | spec futura |
| **E** | Eventos que alteram trade-offs e janelas de oportunidade | spec futura |

A–D são independentemente jogáveis. E depende dos demais existirem, porque o que E faz é modular os multiplicadores que eles introduzem.

### Princípio que governa o desenho

Toda ação ou parâmetro novo precisa passar em três perguntas:

1. Existe decisão real? (se uma opção é sempre superior, não há estratégia)
2. Existe custo ou trade-off? (energia, tempo, capacidade, qualidade, risco ou informação)
3. Uma implementação mais inteligente consegue explorar essa decisão?

A progressão desejada: estratégia simples funciona; estratégia inteligente funciona melhor; nenhuma estratégia específica é obrigatória.

## 2. Decisões tomadas

- **Modo é enum fechado**, não parâmetro contínuo. Três modos por ação, nomeados. Prioriza compreensibilidade sobre teto de otimização.
- **Degradação por ciclo entra em B.** Sem custo de tempo, o modo econômico/lento nunca perde nada e domina — o trade-off de transporte colapsaria antes de nascer.
- **"Risco" do modo agressivo se materializa como desperdício da jazida**, não como falha probabilística nem desgaste do robô. A jazida é debitada de mais do que a carga recebe; a diferença some do mundo permanentemente. Isso cria custo global (minerais são finitos) a partir de uma otimização local.
- **Números ficam em config externa** (`mundo/config/modos.json`), protegidos por uma suíte de testes de dominância.
- **Perfis são compostos, não embutidos no cálculo.** Requisito antecipado do sub-projeto E: os multiplicadores precisam ser um ponto de composição para que eventos possam modulá-los depois sem refatoração.

## 3. Modelo de domínio

Novo módulo `mundo/dominio/modos.py`, seguindo o padrão de `minerais.py` (dataclasses imutáveis + catálogo carregado de JSON):

```
ModoDeExtracao   = CUIDADOSO | NORMAL | AGRESSIVO
ModoDeTransporte = ECONOMICO | NORMAL | RAPIDO

PerfilDeExtracao(mult_energia, mult_duracao, qualidade_inicial, fator_desperdicio)
PerfilDeTransporte(mult_energia, mult_duracao, mult_degradacao)

CatalogoDeModos.carregar_de_arquivo(caminho)
CatalogoDeModos.obter_extracao(modo) -> PerfilDeExtracao
CatalogoDeModos.obter_transporte(modo) -> PerfilDeTransporte
```

`CargaMineral` ganha `local: LocalDaCarga`, enum `EM_JAZIDA | EM_ARMAZEM | EM_TRANSITO | ENTREGUE`. Esse campo é o que faltava para rastrear custódia, e é o que permite degradação sensível ao contexto.

O módulo pertence a `dominio/` e não importa nada de `motor/` nem de `api/` — a direção de dependência que o núcleo manteve intacta ao longo de 22 tarefas.

## 4. Degradação por ciclo

Novo passo no tick do motor, aplicado a todas as cargas:

```
perda_por_ciclo = mineral.taxa_degradacao × sensibilidade_do_local × mult_do_local
```

`sensibilidade_do_local` vem do catálogo de minerais, escolhida pelo `local` da carga:

| local | sensibilidade usada | mult_do_local |
|---|---|---|
| `EM_ARMAZEM` | `sensibilidade_armazenagem` | 1.0 |
| `EM_TRANSITO` | `sensibilidade_transporte` | `mult_degradacao` do modo de transporte |
| `EM_JAZIDA` | 1.0 (exposta, sem proteção) | 2.0 |
| `ENTREGUE` | — | 0.0 (não degrada mais) |

Com os valores já presentes em `minerais.json`, isso diferencia os minerais sem nenhuma regra especial:

| mineral | em armazém | exposta na jazida |
|---|---|---|
| hematita (taxa 0.2) | 0.02/ciclo | 0.40/ciclo |
| gelo de água (taxa 0.9) | 0.63/ciclo | 1.80/ciclo |

Hematita pode ficar parada; gelo de água vira corrida contra o relógio. Urgência passa a ser propriedade emergente do mineral.

A qualidade permanece limitada a [0, 100] pelo `clamp_qualidade` existente.

### Débito técnico que isso quita

Três achados foram registrados como deferidos na revisão final do núcleo e caem exatamente neste buraco:

- `CargaMineral` não tinha vínculo com onde estava (custódia não rastreável).
- O transporte passava `rota.risco` no parâmetro `taxa_degradacao` — unidades erradas, resultado desprezível.
- `taxa_degradacao`, `sensibilidade_temperatura`, `sensibilidade_transporte` e `sensibilidade_armazenagem` existiam no catálogo e não eram lidas por código nenhum.

`sensibilidade_temperatura` permanece sem uso após B: ela é o gancho para os eventos climáticos do sub-projeto E.

## 5. Aplicação nas rotas

`POST /extracao/iniciar-extracao` e `POST /transporte/iniciar-viagem` ganham campo **opcional** `modo`, com default `NORMAL`. Clientes e testes existentes seguem funcionando sem alteração.

**Extração:**

```
custo    = mineral.custo_extracao × quantidade × FATOR_BASE_DE_ENERGIA × perfil.mult_energia
duracao  = DURACAO_EXTRACAO_EM_CICLOS × perfil.mult_duracao
carga    = CargaMineral(..., qualidade=perfil.qualidade_inicial, local=EM_JAZIDA)
jazida.extrair(quantidade × perfil.fator_desperdicio)
```

A carga recebe `quantidade`; a jazida perde `quantidade × fator_desperdicio`. `custo_extracao` do catálogo passa a ser usado (mais um campo hoje morto).

**Transporte:**

```
custo   = CUSTO_ENERGETICO_VIAGEM × perfil.mult_energia
duracao = rota.tempo_base × perfil.mult_duracao
```

A chamada pontual a `degradar()` na conclusão da viagem é removida — a degradação agora é contínua e vive no tick.

**Transições de `local`** — cada uma acontece dentro do closure que já existe:

| de → para | quem dispara |
|---|---|
| (criação) → `EM_JAZIDA` | conclusão da extração |
| `EM_JAZIDA` → `EM_ARMAZEM` | `armazenagem/receber-carga` |
| `EM_ARMAZEM` → `EM_TRANSITO` | `transporte/iniciar-viagem` |
| `EM_TRANSITO` → `EM_ARMAZEM` | conclusão da viagem (carga parada no destino) |
| `EM_ARMAZEM` → `ENTREGUE` | `pesquisa/preparar-distribuicao` |

`ENTREGUE` é terminal: a carga é removida de `motor.cargas` no mesmo passo, então na prática o estado marca o instante do faturamento e não persiste.

Toda mutação continua acontecendo apenas dentro de closures `Comando.executar()`; nenhuma rota muta estado de forma síncrona.

## 6. Configuração

`mundo/config/modos.json`, ponto de partida:

| extração | mult_energia | mult_duracao | qualidade_inicial | fator_desperdicio |
|---|---|---|---|---|
| cuidadoso | 1.6 | 1.4 | 100 | 1.00 |
| normal | 1.0 | 1.0 | 92 | 1.15 |
| agressivo | 0.7 | 0.6 | 78 | 1.40 |

| transporte | mult_energia | mult_duracao | mult_degradacao |
|---|---|---|---|
| econômico | 0.6 | 1.5 | 1.3 |
| normal | 1.0 | 1.0 | 1.0 |
| rápido | 1.8 | 0.6 | 0.8 |

No mesmo arquivo ficam `fator_base_de_energia = 0.2` e os multiplicadores de local (`EM_JAZIDA` = 2.0, `EM_ARMAZEM` = 1.0, `ENTREGUE` = 0.0; `EM_TRANSITO` usa o `mult_degradacao` do modo).

O `fator_base_de_energia` calibra a nova fórmula de custo contra a antiga constante fixa de 2: extrair 10 unidades de hematita (`custo_extracao` 1.0) em modo normal custa `1.0 × 10 × 0.2 × 1.0 = 2` — idêntico ao custo atual. Minerais caros escalam a partir daí: as mesmas 10 unidades de cristal marciano raro (`custo_extracao` 8.0) custam 16 de energia, contra 2000 de valor bruto potencial.

Estes números são um ponto de partida calibrado por análise algébrica, não por medição — o Avaliador ainda não existe. O que os protege são os testes de dominância.

## 7. Testes

Além dos testes normais de comportamento (perfil aplicado corretamente, carga nasce com a qualidade do modo, jazida debitada com desperdício, degradação acumulando por ciclo em cada local, retrocompatibilidade do default `NORMAL`), B entrega uma **suíte de dominância**.

Métrica: **valor entregue por energia gasta**. Para cada um dos seis modos, um teste demonstra pelo menos um cenário (mineral × rota × energia disponível) onde aquele modo é estritamente o melhor dos três da sua categoria:

- **cuidadoso** vence no cristal marciano raro (valor 200/unidade): 22 pontos de qualidade a mais valem muito mais que 60% de energia extra, e preservar 40% de uma jazida escassa e valiosa domina qualquer economia.
- **agressivo** vence na hematita (valor 5/unidade) sob energia apertada: qualidade quase não multiplica valor, desperdiçar hematita é barato, e liberar o robô 40% mais cedo compensa.
- **normal** vence na sílica de alta pureza, onde os extremos se penalizam mutuamente.
- **econômico** vence transportando hematita (sensibilidade ao transporte 0.1): degradação é irrelevante nos três modos, então o mais barato ganha.
- **rápido** vence transportando gelo de água ou jarosita: sensíveis e valiosos, a qualidade preservada paga a energia extra.
- **normal (transporte)** vence no meio-termo entre os dois casos acima.

Se alguém descalibrar os pesos, o teste falha e aponta qual modo virou inútil. Essa suíte roda hoje, sem depender do Avaliador.

## 8. Fora de escopo

- Armazenagem posicional, custo de recuperação e reorganização (sub-projeto C).
- Regiões, jazidas ocultas, exploração e análise com incerteza (sub-projeto A).
- Missões persistentes e alocação de energia por missão (sub-projeto D).
- Eventos ambientais, modificadores temporários e janelas de oportunidade (sub-projeto E). O ponto de composição de multiplicadores previsto na seção 2 é a preparação para ele; nenhum evento é implementado em B.
- Desgaste de robô e falha probabilística de operação: avaliados e descartados como semântica de risco em favor do desperdício da jazida.
- O Avaliador (execução de N simulações, médias e dispersão) permanece não implementado. Enquanto não existir, a validação de que "estratégia melhor produz vantagem observável" é feita por análise de cenário, não estatisticamente.
