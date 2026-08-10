# Revisão final — `central-de-missao`

11 commits, `93579c4..8fb45a7`. Suíte: 270 (baseline 241).

**Quem revisou:** o controlador. O reviewer despachado não produziu saída em ~45 minutos, mesmo após ping — padrão que se repetiu ao longo desta sessão inteira. Registro porque muda o peso desta revisão: é real, com mutação, mas não é um par de olhos independente. E **todas as oito tarefas também foram implementadas pelo controlador**, porque os subagentes travaram 7 de 7 na branch anterior. Nada nesta branch teve revisor independente.

**Método:** invariantes por AST e busca; mutação de 12 pontos entre domínio, motor, API e config; verificação de terminação em quatro cenários extremos; e conferência de precisão nas 16 asserções recalculadas.

---

## Critical

Nenhum.

## Important

Nenhum.

## Minor

1. **`autorizar-missao` muta de forma síncrona** (`mundo/api/missao.py:90,93`), fora de qualquer `Comando.executar()`. É exceção deliberada e documentada: a rota devolve o identificador que o chamador usa na requisição seguinte, então enfileirá-la quebraria todas as outras rotas do projeto. Verificado por AST que é a **única** no `mundo/api/` inteiro. Não estender.

2. **Estratégia ruim produz a execução mais longa.** Despejar 900 na extração e ignorar a missão minera para o nada por 18.201 ciclos, porque as outras centrais secaram no ciclo 200 e não há autorização para escoar nada. É o castigo funcionando, mas inverte a relação intuitiva entre qualidade da jogada e tempo de execução. Não é defeito do mundo; é problema do observador, e pertence à spec do Avaliador.

3. **`condicoes` e `compatibilidades` seguem campos mortos**, herdados. Gancho para armazéns especializados.

---

## O que foi verificado e está limpo

**Invariantes.** `mundo/dominio/` não importa de `motor/`, `api/` nem `eventos/`. Nenhum uso de `random` em domínio ou API. Varredura de AST em `mundo/api/` encontrou exatamente uma mutação síncrona em handler, que é a exceção documentada acima.

**Terminação — a propriedade de que o Avaliador depende.** Todos os extremos que consegui construir encerram:

| cenário | ciclos | encalhado |
|---|---|---|
| não aloca nada | 200 | 950 |
| aloca 0 explicitamente | 200 | 950 |
| tudo (950) numa central só | 19.201 | 0 |
| reserva inteira para a missão | 19.201 | 0 |

O teto é ~19.200 ciclos — 950 de energia a 0.05/ciclo numa central. Esse número pertence à spec do Avaliador: é o pior caso que cem execuções precisam orçar.

A condição de fim pergunta se **alguma central está operante**, e não se alguma cobre o consumo. Isso não é detalhe: a versão com comparação de saldo contra consumo encerrava a execução **um ciclo cedo**, porque subtrações sucessivas em float deixam o saldo um fio abaixo do valor exato. "Todas dormentes" é exato.

**A armadilha é proporcional.** Dispara no ciclo 200 sem nenhuma alocação, e 40 de energia a empurram além de 1000. É visível em `/missao/estado` desde o ciclo 1. E é uma armadilha, não cinco: extração seca é ressuscitável, missão seca não.

**A calibração está presa dos dois lados.** Com `consumo_por_ciclo_da_central` em 0.001 a armadilha nunca dispara e 9 testes caem; em 0.5 o mundo fica punitivo e caem 10; em 0.0 nada termina. Nenhum valor precisou mudar durante a implementação.

**As 16 asserções recalculadas mantiveram a precisão.** A Task 3 somou o consumo como termo a testes que mediam diferença de energia. Deslocar qualquer preço de operação em 0.01 ainda derruba teste:

| preço deslocado | testes que caem |
|---|---|
| extração (`mult_energia` ×1.01) | 3 |
| viagem (3 → 3.01) | 1 |
| análise (2 → 2.01) | 1 |
| armazenagem por unidade (+0.001) | 3 |

**Mutações do mecanismo, todas pegas:**

| mutação | testes que caem |
|---|---|
| tick não cobra consumo | 18 |
| só a primeira central paga | 18 |
| `esta_operante` aceita saldo zero | 13 |
| nunca encerra | 4 |
| `avancar_ciclo` ignora `encerrada` | 2 |
| autorizar de graça | 1 |
| missão dormente ainda aloca | 1 |
| evento relata encalhada zerada | 1 |
| guarda de dormência removida (por central) | 1–2 cada |

---

## Três defeitos encontrados e corrigidos durante a implementação

Registro porque o padrão importa mais que os bugs.

**O check que É o mecanismo do deadlock não estava coberto.** Remover a verificação de missão dormente em `alocar_energia` deixava 262 testes verdes. A asserção era `extracao < antes + 50`, e o consumo do ciclo satisfaz isso sozinho — com a alocação acontecendo o saldo fica `antes + 50 - consumo`, ainda abaixo do limite. Corrigido para afirmar o saldo exato. É o quarto teste neste projeto cujo nome prometia uma invariante que as asserções não pegavam.

**A guarda de dormência foi escrita em quatro arquivos e testada em um.** As outras três podiam ser deletadas com a suíte verde. Escrever a mesma guarda em N lugares e testar uma é indistinguível de escrever e confiar.

**O encerramento comparava saldo com consumo em float**, e terminava um ciclo cedo com uma lasca de energia sobrando.

Nenhum dos três foi encontrado por leitura. Todos por mutação.

Uma nota de método que vale mais que os três: duas mutações **pareceram** escapar porque o `perl` substituiu a definição da constante e quebrou a sintaxe. O pytest falhava na coleta, meu grep por "N failed" não encontrava nada, e o resultado saía como "0 failed" — indistinguível de "teste não pega". **Uma mutação que não compila não prova nada**, e o teste de sanidade é confirmar que a suíte roda antes de acreditar no resultado.

---

## Veredito

**Ship.** Nenhum Critical ou Important. Os três Minor não bloqueiam, e dois são herdados ou pertencem a outra spec.

O que fica registrado para o Avaliador, que é o próximo sub-projeto:

1. **O teto de execução é ~19.200 ciclos**, e a pior estratégia é quem chega perto dele. O Avaliador precisa do próprio orçamento de medição — teto no observador, não regra no mundo.
2. **`simulacao_encerrada` já entrega o que ele precisa medir**: ciclo, faturamento e energia encalhada. A energia encalhada é o placar do erro de alocação, e é o primeiro sinal que distingue quem ignorou a missão de quem só jogou mal.
3. **A terminação é garantida e verificada**, então cem execuções sempre param sozinhas.
