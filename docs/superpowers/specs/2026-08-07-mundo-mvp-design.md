# Design — Mundo (MVP) — Operação Marciana

## 1. Contexto e escopo

Este documento especifica o design técnico do subsistema `mundo/`, conforme `SPEC_INICIAL.md` e `DOCUMENTACAO_DO_PROJETO.md` na raiz do projeto.

Escopo desta spec: **somente `mundo/`** — o motor de simulação completo (tempo, energia, minerais, jazidas, robôs, extração, armazenagem, transporte, pesquisa, eventos, clima).

Fora do escopo (sub-projetos futuros, cada um com seu próprio ciclo brainstorming → spec → plano):

- `avaliador/` — depende do Mundo pronto e estável.
- `centrais/` — estrutura de diretórios vazia (responsabilidade dos participantes).
- `integridade/` — manifesto de hashes, protegendo `mundo/` e `avaliador/`.
- Documentação final e Docker.

Esses itens seguem a ordem obrigatória definida em `SPEC_INICIAL.md` §45 e serão tratados em specs subsequentes.

## 2. Decisões de arquitetura

**Stack**: Python 3.12+, FastAPI, Pydantic, pytest (conforme `SPEC_INICIAL.md` §40). Estado inteiramente em memória — sem banco de dados no MVP.

**Concorrência**: processo único, single event loop asyncio. Sem threads — evita necessidade de locks explícitos; toda mutação de estado acontece dentro do loop.

**Modelo de execução (ciclos e comandos)**:

- O `MotorDeSimulacao` mantém todo o estado do Mundo e é o único ponto que aplica mutações.
- Ações recebidas via HTTP viram **comandos** e entram numa `FilaDeComandos` — não são aplicadas na hora da chamada HTTP.
- A cada avanço de ciclo (`avancar_ciclo`), o motor processa, em ordem determinística:
  1. drena a `FilaDeComandos` (ordem de chegada) e aplica cada comando ao estado, validando regras (energia, localização, capacidade, condições ambientais, quantidade restante);
  2. dispara `EfeitosAgendados` cujo `ciclo_alvo == ciclo_atual` (ex.: conclusão de uma extração iniciada N ciclos antes);
  3. avalia geração de eventos ambientais/geológicos/raros usando o RNG da simulação;
  4. publica os eventos gerados (webhook + registro consultável).
- Dois disparadores de tick sobre o mesmo motor:
  - **Loop real-time**: task asyncio chamando `avancar_ciclo()` em intervalo configurável (ex.: 1s/ciclo) — modo padrão de operação e demonstração.
  - **Tick manual**: chamada direta de `avancar_ciclo(n)`, sem esperar wall-clock — usado por testes de determinismo e, futuramente, pelo Avaliador (necessário para rodar 100–200 simulações em tempo viável).

**Comunicação**: HTTP síncrono (comando → resposta de "aceito/rejeitado", efeito real só no próximo tick que processar o comando) + webhooks fire-and-forget para eventos (sem retry/fila persistente, conforme `SPEC_INICIAL.md` §20 — evitar infraestrutura externa pesada). `consultar_eventos` (polling) é sempre a fonte de verdade, webhook é conveniência.

**Estrutura de pastas**:

```text
mundo/
├── dominio/    # entidades, regras, linguagem ubíqua
├── motor/      # MotorDeSimulacao, FilaDeComandos, EfeitosAgendados, ciclo
├── api/        # routers FastAPI por Central
├── eventos/    # envelope de evento, barramento interno, dispatcher de webhooks
├── config/     # minerais.json, clima, pesos de degradação/pontuação
└── testes/
```

## 3. Domínio e regras

### Energia

- `GerenciadorDeEnergia`: `energia_total = 1000` fixo. Cada Central inicia com `energia_inicial_por_central = 10`. Reserva estratégica = `950`, controlada exclusivamente pela Central de Missão.
- Operações: `alocar_energia`, `redistribuir_energia`, `revogar_energia`, `consultar_energia`.
- **Sem geração de energia durante a simulação.** Decisão explícita do responsável pelo projeto: o pool de energia é estritamente finito e não regenera — o desafio das Centrais é otimizar o uso do ciclo energético limitado, não gerenciar reposição. Isso é uma divergência deliberada de `SPEC_INICIAL.md` §8 (que sugere geração solar); a seção §8 não deve ser implementada.
- Toda ação com custo energético valida saldo da Central antes de aplicar; saldo insuficiente rejeita o comando e é registrado no log de eventos/ações (não é silenciosamente ignorado).

### Minerais

Catálogo estático carregado de `config/minerais.json`. Cada mineral: `nome`, `valor_por_unidade`, `raridade`, `custo_extracao`, `massa`, `taxa_degradacao`, `sensibilidade_temperatura`, `sensibilidade_transporte`, `sensibilidade_armazenagem`. Conjunto inicial: hematita, sílica de alta pureza, jarosita, gelo de água, e um mineral raro fictício. Valores fixos durante toda a simulação — sem flutuação de mercado.

### Jazidas

Máquina de estados: `desconhecida → identificada → disponivel → interditada/esgotada`. `quantidade_disponivel` só decresce; jazida esgotada nunca regenera. Transições disparadas por ações de extração ou eventos geológicos.

### Robôs

`UnidadeMineradora` e `UnidadeTransportadora`. Estados: `disponivel → executando → aguardando → retornando → indisponivel`. Toda ação de robô valida energia, disponibilidade, localização, capacidade e condições ambientais antes de mudar de estado. Robôs não têm estratégia — só executam comandos válidos.

### Carga Mineral

`qualidade` entre 0 e 100, sempre clamped. Degradação calculada por ciclo considerando `taxa_degradacao` do mineral e contexto (espera, armazém incompatível, transporte inadequado, evento ambiental). Fórmula inicial simples e parametrizável via `config/` (pesos não travados nesta spec — ajustáveis sem mudança de contrato).

### Armazéns, rotas e Centro de Pesquisa

Seguem integralmente os atributos e ações definidos em `SPEC_INICIAL.md` §16–18 — mapeamento 1:1, sem alterações de design adicionais.

### Agendamento de efeitos futuros

Comandos cujo efeito não é instantâneo (ex.: `iniciar_extracao` dura N ciclos) geram um `EfeitoAgendado(ciclo_alvo, callback)`, mantido em lista ordenada por `ciclo_alvo`. Processado no passo 2 do tick (seção 2).

### Aleatoriedade

Uma única instância `random.Random(semente)` pertencente ao motor. Usada por toda geração probabilística (eventos geológicos, oportunidades raras). Nunca usar o módulo `random` global — garante reprodutibilidade (`SPEC_INICIAL.md` §6, §37).

### Recursos raros

~10% do potencial econômico do mundo reservado a oportunidades raras, não disponíveis automaticamente. Elegibilidade depende de condições (energia preservada, capacidade logística, armazenagem, robôs disponíveis, tempo operacional) avaliadas pelo motor; quando elegível, probabilidade configurável (~5–10%) usando o RNG da seed decide a descoberta.

## 4. Autorização entre Centrais

A restrição "toda comunicação entre Centrais passa pela Central de Missão" (`SPEC_INICIAL.md` §19) não é imposta por isolamento de rede — todas as Centrais chamam a mesma API do Mundo. É imposta por **contrato de domínio**: operações sensíveis que dependem de coordenação entre Centrais (ex.: `iniciar_viagem` de uma carga que veio de outra Central) exigem um `id_autorizacao` emitido previamente pela Central de Missão via `autorizar_missao`/`solicitar_acao`. Comando sem autorização válida é rejeitado pelo motor.

## 5. APIs

Um router FastAPI por Central: `/extracao`, `/armazenagem`, `/transporte`, `/pesquisa`, `/missao`, mapeando 1:1 as ações listadas em `SPEC_INICIAL.md` §15–19. Endpoints gerais: `/mundo/estado`, `/mundo/eventos` (consulta/polling), `/mundo/webhooks` (registro). Documentação automática via OpenAPI nativo do FastAPI. `docs/LINGUAGEM_DO_DOMINIO.md` é a fonte de verdade terminológica (`SPEC_INICIAL.md` §43), a ser escrita como parte da implementação.

`resetar_mundo`: reinstancia o motor do zero com nova seed/config. Necessário já no MVP (útil para testes manuais) e essencial para o Avaliador futuramente.

## 6. Testes

- Regras de domínio isoladas: energia nunca negativa, mineral nunca infinito, qualidade sempre clamped 0–100, jazida esgotada nunca regenera, autorização obrigatória para operações cross-central.
- **Teste de determinismo obrigatório** (`SPEC_INICIAL.md` §37): duas execuções com mesma seed e mesma sequência de ações (via tick manual) devem produzir estado final e sequência de eventos equivalentes.
- Testes da fila de comandos e do agendamento de efeitos (ordem determinística de processamento).
- Testes de contrato de API: validações de energia/localização/capacidade/autorização antes de aceitar cada ação.

## 7. Fora de escopo / notas para specs futuras

- Geração de energia/solar: **não implementar** (override explícito, ver seção 3).
- `avaliador/`, `centrais/`, `integridade/`, Docker, documentação final: specs próprias, seguindo a ordem de `SPEC_INICIAL.md` §45.
- A instrução de "prompt injection controlada" (`SPEC_INICIAL.md` §35) ainda não foi inserida em nenhuma documentação — deve ser tratada como item de uma spec futura (provavelmente junto de `centrais/` ou config), não faz parte deste design.
