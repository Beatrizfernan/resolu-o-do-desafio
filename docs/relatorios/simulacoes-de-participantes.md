# Simulacoes de Participantes

## Objetivo

Simular perfis de jogadores para verificar se o mundo realmente empurra o participante para os trade-offs esperados: alocacao de energia, escolha de mineral, pacing da fila de pesquisa, degradacao e uso oportunista de armazenamento.

## Metodo

- Seeds usadas: `1000`, `1001`, `1002`
- Execucao: runner exploratorio disparando as APIs do mundo como um participante faria
- Encerramento: depois da estrategia terminar, a simulacao foi acelerada ate `simulacao_encerrada` para medir o placar final
- Foco do placar: faturamento total, cargas entregues, qualidade media entregue e operacoes invalidas

## Estrategias testadas

### 1. `corrida_no_raro`

- Alocacao inicial: missao 60, extracao 720, transporte 90, pesquisa 60, armazenagem 20
- Decisao: minerar apenas `cristal_marciano_raro`
- Extracao: `agressivo`
- Transporte: `rapido`
- Armazenagem: nao usa
- Racional: maximizar throughput e capturar o mineral de maior valor unitario, aceitando perda de qualidade

### 2. `raro_premium`

- Alocacao inicial: missao 70, extracao 730, transporte 80, pesquisa 50, armazenagem 20
- Decisao: minerar apenas `cristal_marciano_raro`
- Extracao: `cuidadoso`
- Transporte: `rapido`
- Armazenagem: nao usa
- Racional: abrir mao de volume para preservar qualidade no ativo mais valioso do jogo

### 3. `portfolio_bufferizado`

- Alocacao inicial: missao 70, extracao 690, transporte 80, pesquisa 70, armazenagem 40
- Prioridade: `cristal_marciano_raro` -> `gelo_de_agua` -> `jarosita`
- Extracao: raro em `cuidadoso`, gelo e jarosita em `agressivo`
- Transporte: `rapido` para tudo
- Armazenagem: usa `armazem-1` como buffer quando a pesquisa esta ocupada
- Racional: explorar primeiro o melhor ROI absoluto e depois converter energia residual em um segundo mineral valioso, reduzindo perda de fila com armazenamento

## Resultados

### Resumo agregado

| Estrategia | Faturamento medio | Qualidade media entregue | Operacoes invalidas medias | Leitura |
|---|---:|---:|---:|---|
| `corrida_no_raro` | 18858.00 | 63.29 | 0.33 | Muito caixa bruto por acao, mas degrada demais |
| `raro_premium` | 25698.00 | 85.96 | 0.33 | Melhor que a corrida pura: o raro paga pela preservacao |
| `portfolio_bufferizado` | 29256.13 | 74.50 | 1.00 | Melhor resultado financeiro total |

### Resultados por seed

#### `corrida_no_raro`

| Seed | Faturamento | Ciclo final | Cargas entregues | Qualidade media | Minerais entregues | Invalidas |
|---|---:|---:|---:|---:|---|---:|
| 1000 | 19038.00 | 10301 | 3 | 63.46 | cristal raro x3 | 1 |
| 1001 | 13032.00 | 13161 | 2 | 65.16 | cristal raro x2 | 0 |
| 1002 | 24504.00 | 10301 | 4 | 61.26 | cristal raro x4 | 0 |

#### `raro_premium`

| Seed | Faturamento | Ciclo final | Cargas entregues | Qualidade media | Minerais entregues | Invalidas |
|---|---:|---:|---:|---:|---|---:|
| 1000 | 25878.00 | 1577 | 3 | 86.26 | cristal raro x3 | 1 |
| 1001 | 17432.00 | 9040 | 2 | 87.16 | cristal raro x2 | 0 |
| 1002 | 33784.00 | 1569 | 4 | 84.46 | cristal raro x4 | 0 |

#### `portfolio_bufferizado`

| Seed | Faturamento | Ciclo final | Cargas entregues | Qualidade media | Minerais entregues | Invalidas |
|---|---:|---:|---:|---:|---|---:|
| 1000 | 26728.80 | 1561 | 4 | 75.33 | cristal raro x3, gelo de agua x1 | 1 |
| 1001 | 26728.80 | 1561 | 4 | 75.33 | cristal raro x3, gelo de agua x1 | 1 |
| 1002 | 34310.80 | 1553 | 5 | 72.84 | cristal raro x4, gelo de agua x1 | 1 |

## Decisoes e interpretacao

### O que funcionou melhor

`portfolio_bufferizado` foi o melhor perfil financeiro.

Razoes:

- O mineral raro continua sendo o melhor uso inicial da energia.
- `cuidadoso` no raro compensa claramente; a perda de qualidade do modo `agressivo` destruiu valor demais.
- Depois que o raro deixa de caber bem no custo marginal, migrar para `gelo_de_agua` ainda gera bom caixa.
- O buffer no armazem evita que parte da fila morra exposta em `na_mao` quando a pesquisa esta ocupada.

### O que perdeu dinheiro

`corrida_no_raro` confirmou o trade-off central do simulador:

- focar so em throughput nao basta;
- o modo `agressivo` acelera demais a deterioracao economica do raro;
- o maior valor unitario do mundo nao perdoa perda de qualidade.

### O que o simulador esta forcando corretamente

- **Qualidade importa de verdade.** O salto de `corrida_no_raro` para `raro_premium` foi grande mesmo mantendo o mesmo mineral-alvo.
- **Pesquisa e um gargalo real.** Sem pacing ou buffer, a operacao perde dinheiro por fila exposta.
- **Energia e o recurso mestre.** A melhor estrategia nao foi a mais rapida, foi a que converteu melhor cada bloco de energia em faturamento.
- **A escolha do segundo mineral importa.** Depois do raro, `gelo_de_agua` apareceu como extensao melhor do que insistir cegamente no mesmo padrao.

## Achados sobre a jogabilidade

### 1. A aprovacao formal nao bloqueia faturamento

Na implementacao atual, `preparar-distribuicao` exige apenas que a carga esteja analisada. Nao foi necessario passar por `aprovar-carga` para monetizar.

Impacto:

- reduz o papel tatico da aprovacao;
- encurta o fluxo de pesquisa;
- permite um jogador pragmatico pular uma etapa que, pela narrativa, parece obrigatoria.

### 2. O roteamento esta economicamente simplificado demais

Na pratica, foi vantajoso usar sempre `rota-1`, a rota mais curta. Nao encontrei validacao que force compatibilidade entre origem real da carga e a rota escolhida.

Impacto:

- a complexidade de roteamento quase desaparece;
- a decisao de transporte fica mais perto de escolher `modo` do que escolher rota.

### 3. O desperdicio da extracao precisa entrar no raciocinio do jogador

As poucas operacoes invalidas observadas vieram do fim de jazida: pedir uma quantidade que parecia caber, mas cujo `fator_desperdicio` fazia o consumo real ultrapassar o restante.

Impacto:

- isso e bom para a avaliacao;
- obriga o participante a modelar o custo real da acao, nao so a quantidade solicitada.

### 4. O estado das mineradoras nao esta exposto por endpoint dedicado

Isso empurra o participante para bookkeeping local por eventos ou para leitura do codigo.

Impacto:

- aumenta a exigencia de integracao orientada a eventos;
- mas tambem cria um pequeno atrito de observabilidade que nao adiciona muito ao desafio economico em si.

## Conclusao

O simulador ja esta forcando boa parte do exercicio esperado.

Sinais fortes:

- qualidade versus throughput muda materialmente o placar;
- a fila da pesquisa importa;
- energia e gargalos operacionais definem a estrategia vencedora;
- armazenamento passa a ter utilidade quando o jogador tenta extrair alem do que a pesquisa absorve.

O melhor resultado que encontrei foi `portfolio_bufferizado`, com faturamento medio de `29256.13` nas seeds testadas.

Se o objetivo e selecionar devs por estrategia e nao por exploitar brechas, eu ajustaria primeiro:

1. exigir aprovacao formal antes da distribuicao;
2. validar a compatibilidade entre rota, origem e local da carga;
3. decidir se a observabilidade das unidades mineradoras deve ser explicita via API ou claramente parte do desafio.
