# Simulacoes de Participantes

## Objetivo

Recalibrar a bateria exploratoria depois da Fase 1 e verificar se as novas escolhas de `Missao`, `Extracao` e `Pesquisa` aumentaram a riqueza estrategica sem abrir escopo para `Armazenagem` nem para sistemas cruzados.

## Rodada Fase 1

- Missao agora distingue classes de autorizacao e repasse
- Extracao agora distingue tipo de mineradora e perfil de escavacao
- Pesquisa agora distingue tipo de analise e politica de aprovacao

## Metodo

- Seeds usadas: `1000`, `1001`, `1002`
- Runner: harness ad hoc desta rodada, executado via APIs do mundo com `TestClient`
- Encerramento: depois da estrategia parar de emitir novas acoes, a simulacao foi acelerada ate `simulacao_encerrada`
- Medidas principais: faturamento total, qualidade media entregue, cargas entregues, operacoes invalidas e minerais efetivamente monetizados
- Escopo deliberadamente mantido em `Missao`, `Extracao` e `Pesquisa`

## Perfis testados

### 1. `conservador_de_qualidade`

- Usa repasse de missao com `contingencia`
- Prefere analises mais longas e politicas mais estritas
- Aceita faturar menos para preservar qualidade final

### 2. `caixa_rapido_administrado`

- Usa repasse `pulso` e autorizacoes `rapida`
- Busca giro curto com aprovacao `comercial`
- Tolera perda de qualidade para transformar mineral valioso em caixa cedo

### 3. `operador_hibrido_de_valor`

- Mistura repasse conservador com filtro economico por carga
- Tenta equilibrar qualidade minima viavel com retorno por entrega
- Evita monetizacao de cargas que ficam ruins demais para o limiar escolhido

## Resultados

### Resumo agregado

| Estrategia | Faturamento medio | Cargas entregues medias | Qualidade media entregue | Operacoes invalidas medias | Leitura |
|---|---:|---:|---:|---:|---|
| `conservador_de_qualidade` | 1822.07 | 13.67 | 91.18 | 1.67 | Preserva muito bem a qualidade, mas converte pouco valor em caixa |
| `caixa_rapido_administrado` | 14452.56 | 12.33 | 58.62 | 0.00 | Melhor caixa medio, sacrificando qualidade para monetizar cristal raro cedo |
| `operador_hibrido_de_valor` | 4015.13 | 2.67 | 75.11 | 2.33 | Fica no meio: mais seletivo que o perfil rapido, mais rentavel que o conservador em seeds focadas em cristal |

### Resultados por seed

#### `conservador_de_qualidade`

| Seed | Faturamento | Ciclo final | Cargas entregues | Qualidade media | Minerais entregues | Invalidas |
|---|---:|---:|---:|---:|---|---:|
| 1000 | 1701.80 | 1752 | 1 | 85.09 | cristal_marciano_raro x1 | 5 |
| 1001 | 1753.00 | 2272 | 20 | 94.64 | hematita x14, silica_de_alta_pureza x6 | 0 |
| 1002 | 2011.41 | 2212 | 20 | 93.80 | hematita x12, silica_de_alta_pureza x8 | 0 |

#### `caixa_rapido_administrado`

| Seed | Faturamento | Ciclo final | Cargas entregues | Qualidade media | Minerais entregues | Invalidas |
|---|---:|---:|---:|---:|---|---:|
| 1000 | 14412.00 | 959 | 12 | 60.05 | cristal_marciano_raro x12 | 0 |
| 1001 | 14973.60 | 781 | 13 | 57.59 | cristal_marciano_raro x13 | 0 |
| 1002 | 13972.08 | 855 | 12 | 58.22 | cristal_marciano_raro x12 | 0 |

#### `operador_hibrido_de_valor`

| Seed | Faturamento | Ciclo final | Cargas entregues | Qualidade media | Minerais entregues | Invalidas |
|---|---:|---:|---:|---:|---|---:|
| 1000 | 4757.40 | 1394 | 3 | 79.29 | cristal_marciano_raro x3 | 5 |
| 1001 | 2948.80 | 1988 | 2 | 73.72 | cristal_marciano_raro x2 | 1 |
| 1002 | 4339.20 | 1753 | 3 | 72.32 | cristal_marciano_raro x3 | 1 |

## Interpretacao

## 1. A Fase 1 aumentou a separacao entre perfis de jogo

As tres centrais novas agora puxam a simulacao para regioes bem distintas de resultado:

- um perfil orientado a qualidade termina com carga excelente, mas baixa conversao em caixa;
- um perfil orientado a giro rapido monetiza muito mais cedo, com qualidade bem mais baixa;
- um perfil hibrido ocupa o meio do caminho, evitando a pior perda de qualidade, mas sem replicar o caixa do perfil mais agressivo.

Isso ja e riqueza estrategica observavel, nao apenas diferenca cosmetica de API.

## 2. Missao, Extracao e Pesquisa passaram a interferir juntas no resultado

O ranking deixou de depender so de transporte.

- Em `Missao`, classe de autorizacao e politica de repasse mudam o ritmo e a folga energetica.
- Em `Extracao`, perfil de escavacao altera custo e qualidade inicial, o que desloca o teto de aprovacao possivel.
- Em `Pesquisa`, tipo de analise e politica de aprovacao definem se a carga vira faturamento ou descarte.

O efeito combinado aparece com clareza na bateria: o perfil rapido ganha caixa porque aceita um limiar baixo e gira mais cedo; o conservador segura qualidade porque filtra mais e paga por isso em throughput; o hibrido tenta proteger margem, mas fica exposto ao custo de ser seletivo demais.

## 3. A riqueza aumentou, mas ainda nao existe uma estrategia dominante universal

Nenhum dos tres perfis vence em tudo ao mesmo tempo:

- `caixa_rapido_administrado` vence em faturamento medio;
- `conservador_de_qualidade` vence em qualidade media entregue;
- `operador_hibrido_de_valor` fica entre os dois extremos e mostra que o espaco de busca agora e real, nao binario.

Isso e uma melhora importante para avaliacao, porque agora o simulador separa intencoes estrategicas diferentes em vez de esmagar tudo no mesmo comportamento economicamente correto.

## Conclusao

Sim: as tres mudancas centrais da Fase 1 aumentaram a riqueza estrategica.

Leitura final desta rodada:

1. `Missao`, `Extracao` e `Pesquisa` agora alteram o resultado economico de forma material;
2. a bateria nova produz perfis com trade-offs diferentes e legiveis;
3. o jogo passou a distinguir com mais honestidade entre preservar qualidade, acelerar caixa e buscar valor intermediario.

O principal sinal positivo nao e so o ranking, mas o fato de que cada perfil termina em uma combinacao diferente de faturamento, qualidade e taxa de erro. Isso indica que a Fase 1 abriu espaco para decisao real sem depender de exploit nem de expansao para outras centrais.
