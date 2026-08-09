# Revisão final de branch — `modos-de-operacao` + `desgaste-por-intensidade`

Escopo: `main...HEAD`. Método: leitura do diff completo, análise algébrica das
métricas, sondas de simulação instrumentadas e mutações de código de produção
com a suíte completa.

**Estado deste documento.** As seções Critical / Important / Minor abaixo
descrevem a branch **como estava quando a revisão foi escrita** (190 testes) e
são mantidas como registro do que foi encontrado. Todos os cinco achados
bloqueantes — C1, C2, C3, I1, I2 — foram corrigidos depois, e a suíte está em
199 testes verdes.

Duas coisas mudaram na conclusão e estão no **Desfecho**, ao final:

- o diagnóstico de **C2** estava errado (culpava o desgaste; a causa era o
  comprimento das rotas), e a correção veio de um mecanismo novo — degradação em
  trânsito proporcional à raridade do mineral;
- a medição do espaço de estratégias mostra que a seleção de modo é **rasa**:
  jogar sempre `normal`+`normal` custa 0.7% contra a escolha ótima por cenário.

Leia o Desfecho antes de agir sobre qualquer coisa aqui.

---

## Critical

### C1 — `mult_degradacao_local` vaza no abort da viagem e vira estratégia dominante

`mundo/api/transporte.py:136` grava `carga.mult_degradacao_local =
perfil.mult_degradacao` ao partir. O único ponto que restaura o valor é o
caminho feliz de `concluir()`, em `mundo/api/transporte.py:153`. O caminho de
aborto (`mundo/api/transporte.py:141-150`, introduzido em `832c42e`) publica
`viagem_abortada` e retorna **sem** restaurar nem `local` nem
`mult_degradacao_local`. E `mundo/api/armazenagem.py:77` (`receber_carga`)
corrige `carga.local` mas **não** `mult_degradacao_local`.

Consequências, ambas medidas:

**(a) Exploit — degradação permanentemente reduzida em armazém.** Iniciar uma
viagem em `rapido`, abortá-la no ciclo seguinte e receber a carga no armazém
deixa a carga em `em_armazem` com `mult_degradacao_local = 0.5` para sempre.
Medido com `gelo_de_agua`, 20 ciclos em armazém:

| cenário | mult | perda de qualidade |
|---|---|---|
| viagem `rapido` concluída normalmente | 1.0 | 12.60 |
| viagem `rapido` abortada + `receber-carga` | **0.5** | **6.30** |
| viagem `economico` concluída normalmente | 1.0 | 15.43 |
| viagem `economico` abortada + `receber-carga` | **2.5** | **31.50** |

Custo do exploit: ~3.15 de energia e uma `viagens_disponiveis`. Para qualquer
carga de valor que vá esperar em armazém, o retorno é trivialmente positivo.
Isto é exatamente a classe de defeito que o sub-projeto existe para eliminar —
uma jogada que toda estratégia deveria fazer sempre — e ela nasce de um bug de
estado, não de calibração. O espelho também é injusto: quem aborta uma viagem
`economico` leva 2.5x de degradação em armazém, permanentemente, sem nenhum
evento que explique por quê.

**(b) Carga órfã em trânsito.** Sem `receber-carga`, a carga abortada fica em
`em_transito` com o multiplicador do modo para sempre. Medido: `gelo_de_agua`
em `economico` cai de 100 para 39.25 em 54 ciclos e continua caindo até zero,
sem nenhum caminho de recuperação no domínio.

**Correção sugerida:** restaurar `local` e `mult_degradacao_local` no caminho de
aborto (`em_jazida`/`1.0`, ou o local de origem), e tornar `receber_carga`
responsável por normalizar `mult_degradacao_local = 1.0` junto com `local` —
`local` e `mult_degradacao_local` são um par e nunca deveriam ser escritos
separadamente. Considerar encapsular isso num método de `CargaMineral`
(`mover_para(local, mult)`) para que o par não possa dessincronizar de novo.

### C2 — O desgaste destruiu o trade-off dos modos de transporte; `economico` domina universalmente

Este é o padrão que a instrução pediu para caçar, na sua forma mais cara: um
fator novo que **reconfigura** a comparação e está **ausente da métrica** que
deveria protegê-la.

O desgaste entra na energia de transporte (`mundo/api/transporte.py:126`) e
acumula como `taxa_de_desgaste / perfil.mult_duracao`
(`mundo/api/transporte.py:131`). Mas o número de operações por ciclo também
escala com `1 / mult_duracao`. Logo o desgaste **por ciclo** escala com
`1 / mult_duracao²`. Os `mult_duracao` de transporte vão de 2.0 a 0.5 — uma
faixa de 4x, que vira **16x** de desgaste por ciclo. Os de extração vão de 1.4 a
0.6 — 2.33x, que vira 5.4x. A calibração (`taxa 1.0`, `sensibilidade 0.65`) foi
varrida apenas sobre extração; no eixo de transporte ela morde 3x mais forte.

Medição, operação contínua de 100 ciclos, uma transportadora, valor entregue
por energia gasta (qualidade capturada na chegada, via assinante do evento
`transporte_concluido`):

| rota | mineral | economico | normal | rapido | vencedor |
|---|---|---|---|---|---|
| rota-1 | hematita | **9.08** | 3.19 | 1.16 | economico |
| rota-1 | silica_de_alta_pureza | **35.41** | 12.71 | 4.65 | economico |
| rota-1 | jarosita | **57.17** | 21.90 | 8.12 | economico |
| rota-1 | gelo_de_agua | **64.79** | 24.99 | 9.28 | economico |
| rota-1 | cristal_marciano_raro | **354.06** | 127.07 | 46.54 | economico |
| rota-2 | hematita | **9.92** | 3.78 | 1.41 | economico |
| rota-2 | silica_de_alta_pureza | **38.28** | 15.00 | 5.61 | economico |
| rota-2 | jarosita | **59.65** | 25.70 | 9.76 | economico |
| rota-2 | gelo_de_agua | **67.33** | 29.31 | 11.15 | economico |
| rota-2 | cristal_marciano_raro | **382.78** | 150.04 | 56.13 | economico |

`economico` vence **10 de 10** combinações, por 7x sobre `rapido`.

Que a causa é o desgaste, e não a calibração dos perfis de transporte, está
provado por contraste. Com `taxa_de_desgaste: 0.0` (mutação temporária,
revertida), a mesma medição:

| rota | mineral | economico | normal | rapido | vencedor |
|---|---|---|---|---|---|
| rota-1 | hematita | **17.34** | 15.54 | 15.87 | economico |
| rota-1 | gelo_de_agua | 123.75 | 121.64 | **126.41** | rapido |
| rota-2 | hematita | **16.69** | 15.26 | 14.93 | economico |
| rota-2 | gelo_de_agua | 113.28 | 118.37 | **118.44** | rapido |

Antes do desgaste: espalhamento de ~4% e liderança que **gira** com o mineral e
a rota — um trade-off saudável. Depois do desgaste: 7x e liderança fixa.

Por que a suíte não pega: `test_dominancia_de_modos.py:67-74`
(`_retorno_do_transporte`) modela só `qualidade / mult_energia`. Não tem
desgaste e não tem custo de duração. Ela mede o mundo pré-`77c113d`. Não existe
nenhum equivalente de `_simular_operacao_continua` para transporte — toda a
prova de inversão do sub-projeto de desgaste é unilateral, só do lado da
extração.

Ressalva honesta, para o registro: em **valor por ciclo**, `rapido` ainda vence
(22 viagens contra 8 em 100 ciclos, 8760 de valor contra 2840). O trade-off só
desaba porque a energia é o recurso que amarra: são 1000 no mundo inteiro, para
cinco centrais, e não regeneram — `rapido` sozinho queimou 944 desses 1000 em
100 ciclos com **uma** transportadora, entregando 1099 de valor em hematita,
contra 398 por 43.8 de energia do `economico`. Sob o orçamento real, `economico`
entrega ~8x mais valor total. Se algum dia a energia regenerar ou os ciclos
virarem o recurso escasso, este achado se inverte — mas hoje não é o caso, e a
premissa "energia nunca regenera" é decisão fechada do dono do projeto.

**Correção sugerida:** recalibrar o desgaste com uma varredura que inclua o eixo
de transporte, e/ou fazer o desgaste de transporte escalar com a duração real da
viagem em vez de `1/mult_duracao` (o que neutralizaria a amplificação
quadrática). E, obrigatoriamente, **estender a prova de inversão a transporte**:
sem um `_simular_operacao_continua` para viagens, este defeito volta na próxima
recalibração sem nada acusar.

### C3 — Extração perto do fim da jazida queima até 100x de energia, trava a unidade e não produz nada

`mundo/api/extracao.py:102-103`: `consumido = quantidade *
perfil.fator_desperdicio` e `jazida.extrair(consumido)` rodam dentro de
`concluir()`, muito depois de a energia já ter sido debitada
(`mundo/api/extracao.py:83`), do desgaste aplicado (`:86`) e da unidade ter ido
para `EXECUTANDO` (`:87`). Se `consumido` exceder o disponível, `extrair` levanta,
a agenda de efeitos captura e publica `operacao_invalida` — e a unidade fica em
`EXECUTANDO` **para sempre**, sem nenhum efeito agendado para liberá-la.

O ledger de `modos-de-operacao` registra isso como "janela pré-existente,
alargada pelo fator de desperdício". A medição mostra que "alargada" subestima:
o fator de escassez torna a falha **mais cara exatamente onde ela é mais
provável**. Cenário reproduzido — jazida com 11.0 de 100.0, extração de 10.0 em
modo `agressivo` (10 × 1.4 = 14 > 11):

```
apos despacho:      estado=executando  desgaste=1.667  energia gasta=74.38
30 ciclos depois:   estado=executando  jazida=11.0 disponivel  cargas=0
eventos:            [('operacao_invalida', 'Quantidade solicitada excede o disponível')]
```

**74.38 de energia — 7.4% do orçamento global do mundo — numa única chamada, sem
nenhum minério produzido, e a unidade bricada.** A unidade nem recupera desgaste,
porque a recuperação só acontece em `DISPONIVEL`
(`mundo/motor/motor_de_simulacao.py:115`).

Agravante de jogabilidade: nada disso é observável de fora. `GET
/extracao/jazidas` mostra `quantidade_disponivel: 11.0`; pedir 10 é uma ação
perfeitamente razoável. `fator_desperdicio` não é exposto por nenhum endpoint,
então o jogador não tem como saber que 10 em `agressivo` consome 14. É uma
armadilha invisível que cobra 7% do orçamento do mundo.

**Correção sugerida:** validar `quantidade * fator_desperdicio <=
jazida.quantidade_disponivel` no `executar()`, **antes** do débito de energia e
da transição de estado — mesma correção que `a4ad7cd` aplicou ao lookup de carga
em `iniciar_viagem`, pelo mesmo motivo. Alternativa mínima: envolver `concluir()`
num `try/finally` que devolva a unidade a `AGUARDANDO`. A validação antecipada é
melhor: também evita o gasto.

---

## Important

### I1 — `test_lideranca_de_custo_gira_conforme_a_janela_de_operacao` afirma algo falso sobre `agressivo`

`mundo/testes/test_desgaste.py:296-299` afirma `"agressivo" not in
lideres.values()`, e a docstring em `:270-271` declara: "`agressivo` nunca
lidera em custo". **Isso é falso.**

Varredura de janelas de 5 a 160 ciclos, passo 5, com a métrica exata do teste:

```
jan   líder      cuidadoso  normal  agressivo
  5   agressivo     0.360   0.217     0.115
 10   agressivo     0.432   0.282     0.176
 15   agressivo     0.432   0.349     0.239
 20   agressivo     0.506   0.349     0.305
 25   agressivo     0.506   0.419     0.374
 30   agressivo     0.582   0.491     0.446
 35   normal        0.582   0.491     0.522
 ...
 80   cuidadoso     1.000   1.083     1.389
```

`agressivo` é o mais barato por unidade útil em **todas** as janelas ≤ 30
ciclos. A afirmação só se sustenta porque as quatro janelas escolhidas
(40/60/80/120) caem todas depois da virada `agressivo`→`normal`, que acontece
por volta de 32 ciclos. É artefato da escolha de janelas, não propriedade
estrutural.

Vale separar: a **rotação em si é real e robusta**. A virada `normal`→`cuidadoso`
entre 60 e 80 ciclos se confirma na varredura de resolução 5 e se sustenta até
160. As asserções 1 (líderes distintos) e 3 (líder mais conservador na janela
longa) estão corretas e são propriedades genuínas. O problema é só a asserção 2.

E ela é ativamente nociva: se uma recalibração futura empurrar a virada
`agressivo`→`normal` de ~32 para ~45 ciclos, o teste quebra e alguém vai
"consertar" a calibração para restaurar uma propriedade que nunca existiu. Além
disso a docstring, agora canonizada, desinforma quem for ler o modelo.

**Correção sugerida:** trocar a asserção 2 por uma que seja verdadeira e
igualmente protetora — por exemplo, incluir uma janela curta (20) no conjunto e
afirmar que `agressivo` lidera lá e não lidera na mais longa. Isso vira a
rotação de duas viradas numa afirmação mais forte, não mais fraca, e o modelo
fica descrito com honestidade: `agressivo` é o modo de rajada curta.

### I2 — O crédito por HTTP 200 não é inofensivo: ele é o que sustenta I1

`mundo/testes/test_desgaste.py:203`: `_simular_operacao_continua` credita
`entregue` quando a resposta é 200, não quando o evento `extracao_concluida`
sai. O ledger de `desgaste-por-intensidade` defere isso como inofensivo porque o
orçamento não estoura (96.9 contra 900). Confirmo que o orçamento não estoura e
que nenhuma `operacao_invalida` ocorre em nenhuma das três simulações — mas essa
é a razão errada, e a conclusão está errada.

O dano real é outro: **extrações em voo são contadas como entregues.** Como os
modos têm durações diferentes, o viés é assimétrico e favorece sistematicamente
os modos lentos na fronteira da janela. Na janela 40, `cuidadoso` fez 5 pedidos
para 4 conclusões (25% de inflação) enquanto `agressivo` fez 8 para 8 (0%).

Contando os eventos `extracao_concluida` reais, o líder **muda** nas janelas 40,
45, 50 e 105:

| janela | líder atual (pedidos) | líder corrigido (entregas) |
|---|---|---|
| 40 | normal | **agressivo** |
| 45 | normal | **cuidadoso** |
| 50 | normal | **agressivo** |
| 105 | cuidadoso | **normal** |

A janela 40 é uma das quatro que o teste usa. Sob contagem correta, o líder lá é
`agressivo` — e a asserção `"agressivo" not in lideres.values()` de I1
**quebraria**. Os dois defeitos se sustentam mutuamente: a métrica errada é o que
faz a afirmação falsa passar.

A conclusão de fundo sobrevive à correção (a virada `normal`→`cuidadoso` continua
lá, e `cuidadoso` lidera as janelas longas com folga), então isto não é Critical.
Mas "inofensivo" está errado e o item não deve ser deferido de novo.

**Correção sugerida:** contar `extracao_concluida` no barramento de eventos.
Corrigir I2 e I1 juntos, na mesma edição — a correção de um muda o resultado do
outro.

---

## Minor

1. **Energia de transporte não escala com a rota.** `CUSTO_ENERGETICO_VIAGEM` é
   constante (`mundo/api/transporte.py:16`); rota-1 (`tempo_base` 5) e rota-2
   (7) custam o mesmo. Pré-existente, mas amplifica C2: como a duração não tem
   custo energético, a única desvantagem de `economico` é a degradação, e ela é
   fraca demais para pagar 8x de energia.

2. **A métrica de dominância de transporte ignora desgaste e duração.**
   `test_dominancia_de_modos.py:67-74`. Coberto por C2; anotado à parte porque a
   correção é no teste, não na calibração.

3. **Margens estreitas na dominância de extração.** A métrica reduz-se
   algebricamente a `[qualidade_inicial/100 − (fator_desperdicio−1)(1+raridade)]
   / mult_energia` — `valor_por_unidade` e `custo_extracao` cancelam, sobra só a
   raridade. `normal` vence apenas na faixa `0.181 < raridade < 0.822`. O
   catálogo tem 0.1 / 0.3 / 0.5 / 0.6 / 0.95, então `hematita` está a 0.08 da
   fronteira. Coincide com o item já deferido no ledger; a suíte existe
   justamente para pegar isso. Ship.

4. **Jazida só vira `ESGOTADA` em `== 0`** (`mundo/dominio/jazidas.py:61`). Com
   `fator_desperdicio` fracionário o resto quase nunca é exatamente zero, então
   a jazida fica presa em `DISPONIVEL` com um resíduo que nenhuma extração
   consegue tirar (`extrair` rejeita `quantidade > disponivel`). Pré-existente,
   agravado por este branch. Correção barata (`<= 1e-9`), mas independente do
   resto — pode ir depois. Relacionado a C3, que é a face cara do mesmo
   descuido.

5. **Comentário factualmente errado.** `mundo/testes/test_api_extracao.py:225`
   diz `mult_energia(1.55)`; a asserção na linha 226 e o config usam 1.8.
   Resíduo do conflito de escrita concorrente da Task 7, já registrado no
   ledger. Uma linha.

6. **TOCTOU em `a4ad7cd`.** A carga é validada no handler
   (`mundo/api/transporte.py:113`) e consumida no tick seguinte. Nada remove
   cargas hoje, então não é explorável. Anotado porque a mesma correção proposta
   em C3 tem a mesma forma.

7. **`catalogo_de_modos or ...`** usa truthiness em vez de `is None`
   (`mundo/motor/motor_de_simulacao.py:42`). `CatalogoDeModos` não define
   `__bool__` nem `__len__`, então é sempre truthy e o comportamento está
   correto hoje. Ship.

8. **`catalogo_de_minerais.obter()` sem proteção dentro do tick.**
   `mundo/motor/motor_de_simulacao.py:103`, em `_degradar_cargas`, fora dos dois
   laços que capturam exceção logo acima. Um nome de mineral desconhecido
   derrubaria o tick inteiro. Cargas só nascem de jazidas, então não é
   alcançável hoje. Ship, mas a assimetria é real.

9. **Edição concorrente durante a revisão.** Outro agente adicionou
   `test_desgaste_da_viagem_escala_com_o_ritmo_do_modo`
   (`mundo/testes/test_desgaste.py:203-229`) enquanto eu revisava; a suíte foi de
   189 para 190. Li a versão final: o teste é sólido e fecha um buraco real
   (`test_viagem_acumula_desgaste_na_transportadora` usa `normal`, cujo
   `mult_duracao` é 1.0, então não prende o divisor). Não é achado — é aviso de
   que a branch se moveu debaixo desta revisão, e `mundo/testes/test_desgaste.py`
   aparece como modificado no `git status` por causa disso, não por minha ação.

---

## Verificações que passaram limpas

Digo em uma linha cada, como pedido.

- **Invariantes arquiteturais.** `mundo/dominio/` não importa de `mundo/motor/`
  nem de `mundo/api/` (grep limpo). Nenhum uso de `random` de módulo — só
  `self.rng = random.Random(semente)`. Handlers não mutam estado
  sincronamente: toda mutação está em `executar()`/`concluir()`; as únicas
  escritas síncronas novas são validações que levantam `HTTPException`.
  `iniciar_viagem` consome a autorização dentro de `executar()`
  (`mundo/api/transporte.py:117`).
- **Costura única dos multiplicadores.** `fator_de_escassez` e
  `fator_de_desgaste` são métodos de `CatalogoDeModos` e entram como fatores na
  mesma expressão de custo dos `mult_*` do perfil, sem abrir eixo novo. Correto.
- **Equivalência do snapshot por prefixo (`68bc723`).** Genuína. O corpo do laço
  em `_simular_operacao_continua` nunca referencia `janelas` exceto para
  fotografar; o motor é construído do zero a cada chamada com semente fixa; e
  nenhum RNG é consumido dentro do laço (o `rng` só é usado em
  `_gerar_mundo_inicial`). A trajetória até o ciclo N é portanto idêntica
  independentemente de `max(janelas)`. O raciocínio se sustenta, não só os
  números.
- **Bateria de mutação — nenhum teste é inerte.** Cinco mutações de produção,
  suíte completa em cada uma, todas revertidas:

  | mutação | falhas |
  |---|---|
  | `sensibilidade_ao_desgaste` 0.65 → 0.0 | 6 |
  | `recuperacao_de_desgaste_por_ciclo` 0.15 → 0.0 | 2 |
  | desgaste ignora `mult_duracao` (extração + transporte) | 3 |
  | `fator_de_escassez` sempre 1.0 | 4 |
  | `mult_degradacao_local` removido da degradação | 2 |

  Notavelmente, a mutação "desgaste ignora `mult_duracao`" derruba tanto
  `test_agressivo_deixa_de_dominar_sob_operacao_continua` quanto
  `test_lideranca_de_custo_gira_conforme_a_janela_de_operacao` — os dois testes
  de calibração são realmente carregantes, apesar de I1.
- **`test_agressivo_deixa_de_dominar_sob_operacao_continua`.** A inversão é real
  em toda a faixa medida: em 120 ciclos `agressivo` custa 2.588 por unidade útil
  contra 1.492 de `cuidadoso`, e a distância cresce monotonicamente. Sobrevive à
  correção de I2 (2.588 contra 1.606).
- **Caça a outros cancelamentos.** Varri as duas expressões de custo e a de
  degradação. `mineral.custo_extracao`, `quantidade` e `fator_base_de_energia`
  cancelam na comparação entre modos de extração, mas são escala global e não
  pretendem ser alavanca. `fator_de_escassez` cancela numa decisão isolada
  (já adjudicado) mas **não** ao longo do tempo, porque `fator_desperdicio`
  empurra a fração restante em ritmos diferentes — a docstring em
  `mundo/dominio/modos.py:96-98` descreve isso corretamente. `fator_de_desgaste`
  não cancela, porque o desgaste é função do histórico do modo. Na degradação,
  `taxa_degradacao × sensibilidade` multiplica todos os modos igualmente, mas
  não cancela porque a duração difere. **O único cancelamento verdadeiro que
  encontrei está em C2** — e é do tipo pior, um fator que existe no motor e está
  ausente da métrica.
- **Determinismo, linguagem de domínio, tokens de autorização.** Sem
  observações. Português no domínio, inglês nos identificadores
  FastAPI/Pydantic, consistentemente.

---

## Triagem dos achados deferidos nos ledgers

### `2026-08-08-modos-de-operacao/progress.md`

| # | Item | Veredito |
|---|---|---|
| T3 | `catalogo_de_modos or ...` em vez de `is None` | **Ship.** Correto hoje; ver Minor 7. |
| T3 | `catalogo_de_minerais.obter()` sem try/except no tick | **Ship.** Inalcançável hoje; ver Minor 8. |
| T4 | `GerenciadorDeEnergia` anota `int`, recebe `float` | **Ship.** Só anotação, sem type checker no repo. Alargar para `float` na próxima task que tocar energia, como o ledger já prevê. |
| T4 | Jazida só vira `ESGOTADA` em `== 0` | **Ship com ressalva.** Correção de uma linha, mas independente; ver Minor 4. |
| T4 | `concluir()` pode falhar em `jazida.extrair` após o débito | **Corrigir antes do merge — virou C3.** O ledger classificou como janela pré-existente alargada; a medição mostra 74.38 de energia (7.4% do orçamento global) e unidade travada permanentemente, porque o fator de escassez torna a falha mais cara justamente onde ela é mais provável. Reclassificado. |
| T5 | Arredondamento bancário em `round(tempo_base × mult_duracao)` | **Ship, e o item está obsoleto.** O ledger cita `economico 1.5`; o config atual tem 2.0, então `rota-2 × economico = 14`, exato. Resta `round(5 × 0.5) = 2` e `round(7 × 0.5) = 4` em `rapido` — inofensivo. Vale apagar a entrada do ledger para não confundir. |
| T5 | `rota.risco` sem uso | **Ship.** Campo morto, como `sensibilidade_temperatura`. Se for gancho para eventos ambientais, documentar junto dela; se não, remover. |
| T5 | Import redundante de `instancia_do_mundo` | **Ship.** |
| T7 | Calibração alternativa estacionada | **Ship.** Ruling do usuário: recalibrar quando o Avaliador existir. Sem objeção — mas C2 mostra que essa recalibração precisa varrer o eixo de transporte, não só o de extração. |
| T7 | Margens estreitas nos pontos de virada | **Ship.** Ver Minor 3. |
| T7 | Comentário diz 1.55, asserção usa 1.8 | **Corrigir antes do merge.** Uma linha, comentário factualmente errado num teste de calibração — exatamente onde um comentário errado engana mais. Ver Minor 5. |

### `2026-08-08-desgaste-por-intensidade/progress.md`

| # | Item | Veredito |
|---|---|---|
| T5 | `_operar_continuamente` credita entrega no HTTP 200 | **Corrigir antes do merge — virou I2.** O ledger defere como inofensivo com base no orçamento; a razão está errada e a conclusão também: a contagem por pedido muda o líder em 4 janelas, incluindo a 40, e é o que sustenta a asserção falsa de I1. |

### Sobre a Task 5 sem revisão independente

Os commits `9846b9e`, `88ce3b1`, `3c9c784`, `68bc723` receberam a atenção extra
pedida. Resultado: `9846b9e` (desgaste por tempo, não por energia) está correto e
é o coração do sub-projeto — a mutação que remove o divisor derruba três testes.
`68bc723` (snapshot por prefixo) é equivalente, e o raciocínio se sustenta, não
só os números. `88ce3b1` e `3c9c784` produziram testes que pegam mutações reais,
mas `3c9c784` introduziu a asserção falsa de I1 e herdou o viés de contagem de
I2. A verificação direta do controller foi correta no que verificou; o que passou
foi a pergunta que uma revisão independente teria feito — "essa afirmação é
verdadeira fora das quatro janelas escolhidas?".

---

## Veredito

**Não fazer merge ainda — corrigir C1, C2 e C3 antes.**

C1 e C3 são bugs de estado com correção pequena e localizada: C1 é sincronizar
`local` com `mult_degradacao_local` em dois lugares, C3 é mover uma validação
para antes do débito. Ambos são reparáveis numa sessão e ambos são exploráveis
ou punitivos hoje, do jeito que a branch está.

C2 é o achado que realmente importa e o mais caro. A branch resolveu com rigor a
dominância no eixo de extração e, ao fazê-lo, criou dominância no eixo de
transporte — com o mesmo mecanismo que a instrução mandou caçar, um fator que
está no motor e não está na métrica. `economico` vence 10 de 10 combinações por
7x, e a prova de que a causa é o desgaste está no contraste com
`taxa_de_desgaste: 0.0`, onde o espalhamento cai para 4% e a liderança gira. A
suíte de dominância de transporte não pode ver isso porque modela o mundo
anterior ao desgaste. Fazer merge assim entrega aos avaliados um dos dois eixos
de decisão já resolvido — precisamente o que o projeto existe para evitar.

I1 e I2 devem ser corrigidos juntos, na mesma edição, porque a correção de um
altera o resultado do outro. Os Minor podem ir depois, com exceção do
comentário 1.55/1.8, que custa uma linha.

O resto da branch está sólido: invariantes arquiteturais limpos, determinismo
preservado, costura de multiplicadores respeitada, e uma suíte cujos testes
demonstradamente falham quando a produção quebra.

---

# Desfecho — diagnóstico refeito após as correções

Escrito depois de corrigir C1, C2, C3, I1 e I2. Duas partes: onde o diagnóstico
original de C2 estava errado, e o que a medição diz sobre o espaço de
estratégias que a branch efetivamente entrega.

## 1. O diagnóstico de C2 estava errado

A revisão atribuiu a dominância de `economico` ao desgaste — "um fator novo que
reconfigura a comparação e está ausente da métrica". A medição não sustenta isso.

**Com `taxa_de_desgaste: 0.0`, `economico` continuava vencendo 10 de 10.** O
desgaste agrava, não causa. Varri 16 combinações de perfis (incluindo a faixa de
energia da spec original, 0.6/1.0/1.8, e faixas de duração estreitadas): todas
com `economico` 10/10.

A causa real é o **comprimento das rotas**. O mundo gera duas, `tempo_base` 5 e
7. Em tão poucos ciclos a degradação em trânsito nunca acumula o bastante para
pagar velocidade:

| taxa de desgaste | tb=5 | tb=10 | tb=20 | tb=40 |
|---|---|---|---|---|
| 0.0 | eco 5 | eco 3, rap 2 | eco 1, rap 4 | eco 1, rap 4 |
| 0.25 | eco 5 | eco 5 | eco 3, nor 2 | eco 3, nor 2 |
| 1.0 | eco 5 | eco 5 | eco 5 | eco 3, nor 2 |

As duas causas são independentes: rota curta mata `rapido` mesmo sem desgaste, e
desgaste mata `rapido` mesmo em rota longa.

E a razão de a suíte nunca ter pego: `test_todo_modo_de_transporte_vence_em_alguma_combinacao`
varre `tempo_base ∈ (3,5,8,12,20,30)` — comprimentos que a simulação nunca cria.
Testava um mundo hipotético.

**Calibração sozinha não resolvia.** Somando as varreduras, 42 combinações: ou
`normal` ou `rapido` estava sempre morto. Em valor-por-energia se quer energia
barata ou qualidade preservada; o meio só vence onde as duas curvas se cruzam. A
única configuração com os três exigia taxa de desgaste específica de transporte
em 0.08 contra 1.0 da extração, e valia numa banda de 0.01 de largura — 0.07
perdia `normal`, 0.09 perdia `rapido`. Coincidência num ponto, não decisão.

**A correção foi acrescentar o eixo que faltava**, por decisão do dono do
projeto: a degradação em trânsito passa a escalar com a **raridade** do mineral.
Minério raro é instável fora do armazém, então cada ciclo na estrada custa mais
quanto mais raro for. `raridade` era, até então, campo que nenhum cálculo do
motor lia — o que também fechava o achado de que o mineral cancelava por completo
da escolha de modo.

A banda é `sensibilidade_a_raridade_em_transito ∈ [25, 80]`, 3.2× de largura.
É essa folga que torna a solução embarcável, e não a existência de um ponto que
funciona.

## 2. O espaço de estratégias — medido, não presumido

Pergunta: as decisões novas geram equilíbrio melhor e permitem mais estratégias?

### Por eixo, isoladamente: sim

**Transporte**, nos cenários que o mundo realmente produz:

| rota | hematita | sílica | jarosita | gelo | cristal |
|---|---|---|---|---|---|
| rota-1 | eco | eco | **rapido** | normal | normal |
| rota-2 | eco | eco | **rapido** | **rapido** | normal |

4/3/3 — os três lideram, e a leitura é legível: comum viaja barato, raro não
espera.

**Extração**, sob operação contínua, a liderança gira com a janela: `agressivo`
até ~30 ciclos, `normal` até ~70, `cuidadoso` daí em diante, com margem que
cresce até +120% em 160 ciclos.

### No pipeline completo: a decisão é rasa

Medindo extrair → armazenar → transportar → entregar em pipeline sequencial (sem
o gargalo de transporte que enviesaria a conta), 9 combinações × 5 minerais × 2
rotas, faturamento por energia:

| cenário | melhor combinação | margem sobre a 2ª |
|---|---|---|
| hematita (ambas rotas) | agressivo + economico | 1.0–1.1% |
| sílica, gelo, cristal | normal + normal | 12–30% |
| jarosita rota-1 | normal + normal | 19.9% |
| jarosita rota-2 | cuidadoso + rapido | 2.8% |

Os três modos aparecem nos dois eixos. Mas o número que importa é o
**arrependimento de estratégias fixas** — quanto se perde jogando sempre a mesma
coisa, contra escolher o melhor em cada cenário:

| estratégia fixa | perda |
|---|---|
| **sempre `normal` + `normal`** | **0.7%** |
| sempre cuidadoso + normal | 24.4% |
| sempre agressivo + normal | 42.9% |
| sempre normal + rapido | 48.9% |
| sempre agressivo + economico | 83.6% |

**Jogar sempre `normal+normal` custa 0.7%.** A decisão de *qual modo* existe
formalmente — cada modo vence em algum cenário, e os testes que fixam isso são
load-bearing —, mas o prêmio por acertar cenário a cenário é 0.7%, enquanto
errar custa até 84%.

Isto é o oposto do alvo declarado do projeto. "Estratégia simples funciona"
está satisfeito com folga; "estratégia inteligente funciona melhor" quase não
está: a inteligência rende menos de um ponto percentual.

### Onde a profundidade real está

Não na escolha de modo, e sim no **escalonamento**: quando pausar para recuperar
desgaste, e por quanto tempo sustentar o ritmo. É o eixo que a rotação por
janela mede, e ali as diferenças são de 11% a 120%, não de 0.7%. A branch cria
uma decisão real — só que é temporal, não categórica.

### Ressalva de método

O arrependimento acima foi medido num regime: jazida efetivamente infinita,
robôs devolvidos a `DISPONIVEL` imediatamente, pipeline sequencial, métrica
faturamento por energia. Ele **não** captura esgotamento de jazida, o fator de
escassez, gestão de desgaste por pausa, nem restrição de ciclos. Um mundo com
jazidas finitas e orçamento de ciclos apertado provavelmente separa mais os
modos — o teto de entrega por jazida (100.0 / 83.3 / 71.4 unidades para
cuidadoso / normal / agressivo) é um diferenciador que este regime anula ao dar
minério infinito.

A afirmação segura é a negativa: **no regime medido, a seleção de modo não
recompensa quem pensa.** Confirmar ou refutar isso nos demais regimes é trabalho
do Avaliador, que continua sendo a única forma de validar calibração
empiricamente.

## 3. Recomendação

A branch pode ser mergeada: entrega o que o sub-projeto prometeu, os cinco
achados estão corrigidos e verificados por mutação, e 199 testes passam.

O que fica registrado para o próximo ciclo, em ordem de valor:

1. **Aprofundar a seleção de modo, ou aceitá-la como rasa e dizer isso.** Hoje o
   default quase ótimo torna a escolha decorativa. As alavancas mais promissoras
   são as que este regime anulou: jazidas finitas com escassez mordendo, e
   orçamento de ciclos que faça o teto de entrega por jazida pesar.
2. **`CUSTO_ENERGETICO_VIAGEM` é constante** (`mundo/api/transporte.py:16`):
   rota-1 e rota-2 custam a mesma energia apesar de comprimentos diferentes.
   Enquanto duração não tiver preço energético, o modo lento leva vantagem
   estrutural.
3. **`raridade` agora entra no motor, mas só no transporte.** Na extração o
   mineral continua cancelando da comparação: a razão `agressivo/cuidadoso` é
   3.1975 nos cinco minerais, idêntica a quatro casas.
4. **O Avaliador.** Toda calibração desta branch é algébrica e de cenário.
