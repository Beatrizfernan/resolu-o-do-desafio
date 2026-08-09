# Design — Armazenagem Posicional

## 1. O problema que isto resolve

A armazenagem é hoje o eixo mais vazio da simulação. Medido no motor:

- **Não existe decisão.** Os dois armazéns são idênticos (capacidade 500, `condicoes: "normal"`, `compatibilidades` vazio). Guardar em um ou no outro dá exatamente o mesmo resultado.
- **Não existe custo.** Receber uma carga custa 1 de energia fixo, contra 950 do orçamento do mundo. `realocar-carga` não custa nada.
- **A contabilidade está quebrada em três pontas**, todas reproduzidas:
  - Entrega nunca libera espaço. Cinco cargas de 20 recebidas, entregues e removidas do mundo deixam `ocupacao` em 100.0 permanentemente. Com 1000 de capacidade total contra 1484 de minério, quem processar minério demais trava o mundo sem caminho de volta.
  - Chegada por transporte não reserva espaço. A carga volta para `em_armazem` sem passar por `receber-carga`: ocupação antes 30.0, depois 30.0.
  - `liberar-carga` aceita quantidade arbitrária. Chamada com 9999 num armazém com 30 de ocupação, zerou. É a válvula de escape do vazamento acima e um exploit por si só.
  - `realocar-carga` move contadores dos dois armazéns sem tocar `carga.local` e sem debitar energia.

Contra a regra de três do projeto, a armazenagem falha nas três perguntas: não há decisão real, não há custo, e uma implementação melhor não tem o que explorar — só exploits.

## 2. O mecanismo

Cada armazém deixa de ser um balde e passa a ser uma **pilha ordenada**. O participante escolhe a ordem ao guardar; a ordem determina o custo de tirar.

Retirar é **destrutivo**: para alcançar um item enterrado, tudo que está acima sai junto e volta para a mão do participante. Quem quiser guardar de volta chama a armazenagem outra vez e paga de novo. O custo por profundidade não é uma fórmula — cai naturalmente de ter que rearmazenar.

Guardar tem custo. Manter tem custo por ciclo. Reordenar tem custo proporcional ao quanto se mexeu.

### Por que isto cria uma decisão

A ordem certa é a ordem inversa de entrega: o que sai primeiro fica no topo. Mas a ordem de entrega não é dada — o participante a deduz, e a chave não é óbvia.

O critério real é a **perda de valor por ciclo**, `taxa_degradacao × sensibilidade_armazenagem × valor_por_unidade`, porque toda carga em armazém degrada a cada ciclo:

| mineral | valor | taxa_degradacao | sens_armazenagem | perda de valor/ciclo |
|---|---|---|---|---|
| gelo_de_agua | 40 | 0.9 | 0.7 | **0.2520** |
| cristal_marciano_raro | 200 | 0.3 | 0.4 | 0.2400 |
| jarosita | 35 | 0.7 | 0.6 | 0.1470 |
| silica_de_alta_pureza | 20 | 0.4 | 0.3 | 0.0240 |
| hematita | 5 | 0.2 | 0.1 | 0.0010 |

Ordenar por preço — o palpite óbvio — coloca o cristal no topo. Ordenar pelo critério correto coloca o gelo. As duas ordens divergem exatamente no topo, que é onde a decisão pesa. A chave certa exige combinar três campos do catálogo, e nada no mundo a anuncia.

O segundo problema é mais algorítmico. Como reordenar custa `Σ|posição_nova − posição_antiga|`, atingir uma ordem-alvo com **movimento mínimo** não é ordenar: é preservar a maior subsequência que já está na ordem relativa correta e mover só o resto.

```
pilha atual : [hematita, gelo, silica, cristal, jarosita]
alvo relativo: gelo > cristal > jarosita > silica > hematita

ingênua : reescreve as cinco posições        → ~12 movimentos
esperta : mantém gelo, cristal, jarosita     → move 2 → ~4 movimentos
```

Estratégia simples funciona: empilhar sem pensar e pagar a profundidade. Estratégia melhor funciona melhor: ordenar pela perda de valor. A melhor explora a estrutura do custo: movimento mínimo. Nenhuma é obrigatória, e nada disso é prescrito pela API — tudo cai da função de custo.

## 3. Decisões tomadas

- **A pilha vive em `Armazem`**, como `list[str]` de identificadores de carga. Índice 0 é o fundo, o último elemento é o topo. Nenhuma entidade nova.
- **`ocupacao` continua sendo volume** e continua governando capacidade. Volume e contagem de itens passam a ser eixos separados de custo, deliberadamente.
- **Guardar e reordenar são a mesma ação.** `receber-carga` aceita a ordem completa desejada. Não existe endpoint de reordenação isolado: reorganizar sem guardar nada é apenas guardar uma lista vazia com nova ordem.
- **Retirar devolve tudo acima do alvo.** Sem opção de "só o alvo", sem devolução automática. O que volta para a pilha volta por decisão e pagamento explícitos.
- **Volume paga guardar e manter; contagem de itens paga remexer.** Guardar e manutenção cobram por unidade; reordenar e desempilhar cobram por item.
- **`liberar-carga`, `realocar-carga` e `reservar-espaco` saem.** A pilha torna os três incoerentes: manipulavam ocupação sem referência a carga alguma. Ocupação passa a ser função do que está empilhado, e não um contador que se escreve à parte.

### Consequência aceita: o tamanho do lote deixa de ser decisão

Com guardar e manter cobrando por unidade, dividir o mesmo minério em muitas cargas pequenas é estritamente pior: guardar e manter custam igual, mas pilha mais alta significa mais movimentos ao reordenar e mais profundidade ao desenterrar. Extrair no maior lote possível domina.

Isto é aceito conscientemente. A decisão que este sub-projeto existe para criar é a **ordem**, e ela sobrevive inteira. Nenhuma documentação deve afirmar que o tamanho do lote é estratégico. Se algum ciclo futuro quiser torná-lo estratégico, a alavanca é cobrar manutenção por item em vez de por unidade — aí lotes grandes pagam mais para ficar parados.

## 4. Modelo

`Armazem` ganha um campo:

```python
pilha: list[str] = field(default_factory=list)   # índice 0 = fundo, último = topo
```

e os métodos que mantêm pilha e ocupação em sincronia — os dois nunca devem ser escritos separadamente, pela mesma razão que `local` e `mult_degradacao_local` foram encapsulados em `CargaMineral.mover_para`:

```python
def empilhar(self, identificador: str, quantidade: float) -> None
def desempilhar_ate(self, identificador: str) -> list[str]   # devolve alvo + tudo acima, do topo para baixo
def profundidade(self, identificador: str) -> int            # 0 = topo
def reordenar(self, nova_ordem: list[str]) -> int             # devolve Σ|Δpos|
```

`desempilhar_ate` remove da pilha e decrementa `ocupacao` de todos os removidos. `reordenar` valida que `nova_ordem` é permutação exata da pilha atual — nem item a mais, nem a menos — e levanta se não for.

`CargaMineral` ganha o local `NA_MAO`, para a carga que saiu da pilha e ainda não voltou nem partiu. `LocalDaCarga.EM_ARMAZEM` passa a significar estritamente "está em alguma pilha".

Os multiplicadores de degradação por local ganham entrada para `na_mao`. Carga na mão fica exposta: usa o mesmo multiplicador de `em_jazida` (2.0), o que dá urgência a resolver o que foi desenterrado em vez de deixar acumular.

## 5. Custos

Novo arquivo `mundo/config/armazenagem.json`, seguindo o padrão de `modos.json`:

| operação | fórmula | base | chave |
|---|---|---|---|
| armazenar | `custo_por_unidade × quantidade` | volume | `custo_de_armazenagem_por_unidade` |
| manter | `custo_manutencao × ocupacao`, todo ciclo | volume | `custo_de_manutencao_por_unidade` |
| reordenar | `custo_por_movimento × Σ\|Δpos\|` | itens | `custo_por_movimento` |
| desempilhar | `custo_por_item × profundidade` | itens | `custo_por_desempilhamento` |

Valores de partida, calibrados por análise algébrica contra o orçamento de 950 do mundo:

```json
{
  "custo_de_armazenagem_por_unidade": 0.05,
  "custo_de_manutencao_por_unidade": 0.004,
  "custo_por_movimento": 0.3,
  "custo_por_desempilhamento": 0.8
}
```

Justificativa dos valores. Uma carga de 20 unidades custa 1.0 para guardar, o mesmo que o custo fixo atual — a mudança não encarece o caso simples. Mantê-la custa 0.08 por ciclo, então cem ciclos parada custam 8.0, comparável a extraí-la de novo: guardar por muito tempo é caro mas não proibitivo. Desenterrar um item a três de profundidade custa 2.4 de desempilhamento mais o rearmazenamento do que voltar, o que para três cargas de 20 dá 3.0 — total 5.4, contra 0 se ele estivesse no topo. Reordenar cinco itens por completo custa cerca de 3.6, na mesma ordem de grandeza de uma retirada profunda: reorganizar preventivamente compete com desenterrar depois, que é exatamente a decisão que se quer criar.

Estes números são ponto de partida por análise, não por medição — o Avaliador não existe. O que os protege é a suíte de dominância descrita adiante.

## 6. Aplicação nas rotas

`POST /armazenagem/receber-carga` ganha `nova_ordem: list[str] | None = None`.

- Cargas em `identificadores_das_cargas` entram no topo, na ordem dada, e pagam armazenagem por unidade.
- Se `nova_ordem` vier, a pilha resultante assume aquela ordem e paga movimentação. `nova_ordem` deve ser permutação exata da pilha depois das inserções; qualquer divergência é `operacao_invalida`.
- Sem `nova_ordem`, nada além das inserções se move e não há custo de movimentação.

`POST /armazenagem/retirar-carga` é novo. Recebe armazém e identificador do alvo. Debita `custo_por_desempilhamento × profundidade`, remove alvo e tudo acima, e todos passam a `NA_MAO`. Publica `cargas_desempilhadas` com a lista, para o participante saber o que caiu na mão.

`POST /transporte/iniciar-viagem` passa a exigir que a carga esteja `NA_MAO`. Transportar o que está enterrado é `operacao_invalida` com motivo explícito.

Conclusão de viagem deixa a carga `NA_MAO` no destino, não `EM_ARMAZEM`. Entrar na pilha é ação paga e explícita.

`preparar-distribuicao` passa a exigir `NA_MAO` também, e some o vazamento de ocupação: a carga já saiu da pilha quando foi desempilhada, então não há espaço a liberar na entrega.

`POST /armazenagem/descartar-carga` continua existindo e passa a exigir `NA_MAO` — descartar é a saída para o que foi desenterrado e não vale rearmazenar.

`liberar-carga`, `realocar-carga` e `reservar-espaco` são removidos. Os três manipulavam ocupação sem referência a carga alguma, o que era exatamente o que permitia a ocupação divergir do conteúdo real. Com a pilha, ocupação passa a ser função do que está empilhado e não pode ser escrita à parte.

O custo de manutenção entra como passo novo no tick do motor, junto de `_degradar_cargas` e `_recuperar_desgaste`, debitando da central de armazenagem.

Toda mutação continua dentro de closures `Comando.executar()`; nenhuma rota muta estado de forma síncrona.

## 7. Testes

Além dos testes de comportamento (empilhar preserva ordem, desempilhar devolve alvo e tudo acima, reordenar valida permutação, ocupação acompanha pilha nos dois sentidos, manutenção debita por ciclo, carga na mão degrada com o multiplicador de exposta):

- **Teste de regressão do vazamento**: receber N cargas, desempilhar e entregar todas, e afirmar que a ocupação volta a zero. É o bug que trava o mundo hoje.
- **Teste de dominância de ordenação**: para uma mesma sequência de entregas, ordenar pela perda de valor por ciclo deve render estritamente mais que ordenar por preço, e as duas devem render mais que empilhar sem reordenar. Prova que a chave certa é a que se quer premiar e que pensar paga.
- **Teste de movimento mínimo**: atingir uma ordem-alvo preservando a maior subsequência correta deve custar estritamente menos que reescrever a pilha inteira. Prova que a implementação esperta é recompensada.
- **Teste de não-obrigatoriedade**: uma estratégia que nunca reordena precisa continuar viável — completar entregas sem ficar sem energia. Se reordenar virar obrigatório, a calibração falhou e é ela que muda.

O último é o guarda contra o defeito que este projeto já produziu quatro vezes: um mecanismo que, em vez de criar decisão, cria obrigação.

## 8. Fora de escopo

- `condicoes` e `compatibilidades` permanecem campos mortos. São o gancho para armazéns especializados, com regras de compatibilidade por mineral — sub-projeto próprio.
- Decidir *o que* entregar e quando: sub-projeto D (missões).
- Regiões, exploração e incerteza: sub-projeto A.
- Eventos ambientais: sub-projeto E.
- O Avaliador. Enquanto não existir, toda calibração aqui é análise de cenário, não medição.
