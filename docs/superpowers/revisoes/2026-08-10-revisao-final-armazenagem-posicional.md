# Revisão final — `armazenagem-posicional`

16 commits, `8334e3c..300b711`. Suíte: 233 (baseline 199).

**Quem revisou:** o controlador. O reviewer despachado não produziu saída em ~45 minutos, mesmo após dois pings — padrão que se repetiu ao longo desta sessão. Registro porque muda o peso desta revisão: ela é real, com mutação, mas não é um par de olhos independente.

**Método:** verificação dos invariantes por análise de AST e busca; mutação de 5 pontos do domínio, da API e da config, medindo quantos testes caem; auditoria manual da ordem validação-antes-de-mutação em todos os handlers que debitam ou mutam; e reprodução fim-a-fim dos cenários de falha.

---

## Critical

Nenhum aberto. **Um foi encontrado e corrigido durante a revisão** — está registrado abaixo porque a forma como escapou importa mais que o bug.

### (corrigido, `2be8fee`) `receber-carga` debitava depois de empilhar

`executar()` roda dentro do `try` do motor, então a falha vira `operacao_invalida` e o tick sobrevive — mas o que já foi mutado continua mutado. Central com saldo insuficiente:

```
evento   : operacao_invalida
pilha    : ['x']
ocupacao : 500.0
local    : na_mao
```

Carga dentro e fora do armazém ao mesmo tempo, com a ocupação contando algo que o mundo acabou de declarar que não guardou. É a divergência exata que o sub-projeto existe para eliminar, reintroduzida por um caminho de erro — mesma classe do bug de extração que queimava energia antes de descobrir que a jazida não comportava o pedido.

Corrigido invertendo a ordem: validar, somar o custo, debitar, e só então empilhar, reordenar e mover. O deslocamento da reordenação passou a ser aritmética pura sobre a pilha que ainda não existe, justamente para o preço ser conhecido antes de tocá-la.

**Como escapou:** vivia em código que eu mesmo revisei e aprovei na Task 5, e nenhum teste cobria o caminho de falha. Só apareceu porque o implementer da Task 8 corrigiu uma afirmação errada minha e eu fui verificar a correção dele. Está preso por teste agora.

## Important

### (corrigido, `300b711`) pedido com id repetido deixava rastro parcial

A correção de `2be8fee` fechou uma porta para o mesmo defeito e deixou outra aberta. Um pedido repetindo um identificador — ou nomeando um já empilhado — só era pego por `Armazem.empilhar` na segunda ocorrência, quando a primeira já tinha entrado e o custo já fora cobrado pelas duas cópias.

Com `['a','b','a']`: `operacao_invalida` publicado, as duas cargas empilhadas, ocupação 20.0, ambas ainda `NA_MAO`, e 1.58 de energia gasta por 30 unidades quando só existiam 20.

O pedido passa a ser checado contra si mesmo antes de tudo. O teste que existia afirmava a mutação parcial como esperada — documentava o bug em vez de pegá-lo — e agora afirma o que deve valer.

**Como escapou:** o implementer da Task 5 sinalizou exatamente este caminho no relatório dele, e eu corrigi só metade ao tratar o Critical do débito. Achado de peer que eu subestimei.

## Minor

1. **`registrar_webhook` muta de forma síncrona** (`mundo/api/missao.py:89`), fora de qualquer `Comando.executar()`. Pré-existente e não tocado por esta branch; registra um webhook, não estado do mundo. Fora de escopo, mas anotado porque é a única violação do invariante no projeto.
2. **`condicoes` e `compatibilidades` seguem campos mortos.** `compativel_com` sempre devolve `True` porque `compatibilidades` nasce vazio, o que torna o evento `carga_contaminada` inalcançável. Declarado fora de escopo na spec §8; é o gancho para armazéns especializados.
3. **Buscas lineares em `Armazem`** — `empilhar`, `profundidade` e `desempilhar_ate` varrem a lista. Irrelevante nas profundidades atuais.

---

## Triagem dos achados diferidos

| achado | veredito |
|---|---|
| Task 1: guard de duplicata sem teste | **fechado.** Carregado para a Task 5, que o cobriu no nível da API — é lá que um participante pode disparar, repetindo um id na lista. Mutação confirma: remover o guard derruba 1 teste. |
| Task 8: escolher a chave certa vale ~0.02% | **real, aceito, documentado.** Gelo (25.2/ciclo) e cristal (24.0) sangram quase igual, e são justamente os dois que trocam de lugar entre as chaves. O teste que prende isso é determinístico e se auto-protege — se uma recalibração fizer as chaves coincidirem, a primeira asserção diz isso. A magnitude está no docstring para ninguém ler uma asserção verde como prova de que a chave importa estrategicamente. Fazer pesar exige separar as taxas de perda em `minerais.json`. |
| Task 8: minha afirmação de que "custos zerados dão margem 0.000%" | **estava errada, corrigida.** Zerar `custo_de_armazenagem_por_unidade` faz `debitar` rejeitar quantidade não-positiva, então `receber_carga` falha e o cenário colapsa nos dois braços — media nada. Números corretos, verificados: ~92% da margem de 5.21% é degradação; o modelo de custo responde por ~11 de 145 unidades. |

---

## O que foi verificado e está limpo

**Invariantes arquiteturais.** `mundo/dominio/` não importa de `motor/`, `api/` nem `eventos/`. Determinismo preservado: um único `random.Random(configuracao.semente)`, nenhum `random` módulo-level em produção. Varredura de AST em `mundo/api/` não achou mutação síncrona em handler algum desta branch.

**Validação antes de mutação**, auditada em todo handler que debita ou muta:

| handler | ordem | veredito |
|---|---|---|
| `receber-carga` | valida → soma → debita → empilha → reordena → move | correto (após `2be8fee`) |
| `retirar-carga` | profundidade → debita → desempilha → move | correto |
| `iniciar-viagem` | validações → debita → desgaste → estado → move | correto |
| `preparar-distribuicao` | valida `NA_MAO` → fatura → remove | correto |

**A pilha nunca aponta para nada inexistente.** `retirar-carga` monta o mapa de quantidades a partir de `armazem.pilha`, então um identificador empilhado sem carga correspondente daria `KeyError` depois do débito. Confirmado inalcançável: os dois únicos pontos que removem carga do mundo — `preparar_distribuicao` e `descartar_carga` — exigem `NA_MAO` antes, e carga empilhada nunca está `NA_MAO`. As guardas das Tasks 6 e 7 fecham o buraco.

**Testes são load-bearing.** Cinco mutações, todas pegas:

| mutação | testes que caem |
|---|---|
| `empilhar` põe no fundo em vez do topo | 16 |
| `desempilhar_ate` tira só o alvo (não destrutivo) | 5 |
| `empilhar` aceita duplicata | 1 |
| reordenar de graça | 1 |
| manutenção de graça | 1 |

**A decisão existe.** Guardar na ordem de entrega rende +5.21% contra guardar contra ela. Reordenar com movimento mínimo custa 2 contra 12 de remontar. Quem nunca reordena continua jogando — o guarda contra o mecanismo virar pedágio.

**A contabilidade antiga está morta.** Os três endpoints que escreviam ocupação sem referência a carga alguma foram removidos, e um teste afirma que respondem 404. O vazamento que travava o mundo — entregar sem liberar espaço, com 1000 de capacidade contra 1484 de minério — tem teste de regressão próprio.

---

## Veredito

**Ship.** Nenhum Critical ou Important aberto. Os Minor não bloqueiam e dois deles são explicitamente fora de escopo pela spec.

Duas coisas para o próximo ciclo, ambas já registradas no glossário:

1. **`custo_de_manutencao_por_unidade` é a alavanca perigosa.** Em 0.5 a margem da ordenação **inverte** (−3.81%), porque manutenção cobra por volume parado e pune quem guarda, não quem guarda errado. O valor atual (0.004) está com folga confortável, mas quem recalibrar precisa saber que existe um teto.
2. **A chave de ordenação quase não pesa** enquanto gelo e cristal sangrarem quase igual. Separar as taxas em `minerais.json` é o que a tornaria estratégica.

E uma observação de processo, não de código: sete despachos de subagente travaram nesta branch, e seis das nove tarefas foram terminadas pelo controlador. O Critical acima estava exatamente numa dessas. Vale considerar, no próximo ciclo, um segundo revisor sobre o que o controlador escreveu.
