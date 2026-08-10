# Task 20 — API: Router da Central de Transporte

**Status:** DONE
**Commit:** c58c37e — `feat: add Central de Transporte router enforcing route/authorization rules`

## O que foi feito

A tentativa anterior havia deixado trabalho não commitado em `mundo/api/transporte.py`,
`mundo/api/app.py` e `mundo/testes/test_api_transporte.py`. Revisei o conteúdo contra o
brief: estava completo, correto e já atendia ao padrão de testes exigido. Optei por
construir sobre ele em vez de recomeçar.

### Arquivos

- `mundo/api/transporte.py` (novo, 180 linhas) — router com prefixo `/transporte`:
  - `GET /transporte/rotas`
  - `GET /transporte/transportadores` (filtra por `hasattr(robo, "viagens_disponiveis")`)
  - `GET /transporte/cargas-disponiveis`
  - `GET /transporte/planejar-transporte` (404 se carga inexistente)
  - `POST /transporte/carregar`
  - `POST /transporte/iniciar-viagem` (consome autorização, agenda efeito de chegada)
  - `POST /transporte/abortar-viagem`
  - `POST /transporte/descarregar`
  - `POST /transporte/retornar-unidade`
- `mundo/api/app.py` — `app.include_router(transporte.router)` registrado ao lado de
  missao/extracao/armazenagem.
- `mundo/testes/test_api_transporte.py` (novo, 302 linhas, 22 testes).

### Invariantes respeitadas

- Nenhum handler muta estado de forma síncrona; toda mutação vive dentro do closure
  `executar()` de um `Comando`. Handlers só fazem lookup e levantam `HTTPException` 404.
- `iniciar_viagem` chama `motor.autorizacoes.consumir(id_autorizacao, "iniciar_viagem")`
  — consome, não apenas verifica.
- Todo o domínio e os testes em português; identificadores de FastAPI/Pydantic mantidos.

## Testes

22 testes em `test_api_transporte.py`; suíte completa: **105 passed**.

Cobertura das exigências do padrão de teste:

1. Todo endpoint tem ao menos um teste que roda `motor.avancar_ciclo(...)` e afirma o
   estado resultante (não só `{"aceito": True}`).
2. Reuso de autorização: `test_iniciar_viagem_rejeita_reuso_da_mesma_autorizacao` usa o
   MESMO `id_autorizacao` duas vezes (segunda numa unidade diferente) e afirma
   `operacao_invalida` + `viagens_disponiveis == 10` na segunda unidade.
   `test_iniciar_viagem_sem_autorizacao_valida_gera_operacao_invalida` cobre id inexistente.
   `test_iniciar_viagem_rejeita_autorizacao_de_outra_operacao` cobre autorização emitida
   para outra operação.
3. Branches condicionais com lógica real, cada uma com teste próprio:
   - rota interditada rejeita a viagem;
   - `viagens_disponiveis <= 0` rejeita e não debita energia;
   - `carregar` acima da capacidade;
   - `carregar` com unidade não-DISPONIVEL;
   - `planejar-transporte` filtrando apenas rotas LIVRE;
   - conclusão agendada após `tempo_base`, degradando a qualidade da carga em `rota.risco`.
4. 404s cobertos para carga/unidade/rota inexistentes.

### Verificação por mutação

Para confirmar que os testes não passam trivialmente, mutei o código e reverti:

- Removendo a checagem `rota.condicao != LIVRE` →
  `test_iniciar_viagem_em_rota_interditada_gera_operacao_invalida` FALHA.
- Trocando `autorizacoes.consumir(...)` por um lookup não-consumidor →
  `test_iniciar_viagem_rejeita_reuso_da_mesma_autorizacao` FALHA.

Arquivo restaurado; 22/22 verdes novamente.

## Concerns

Nenhum bloqueante. Duas observações menores herdadas do brief:

- `consultar_transportadores` identifica transportadores por `hasattr(robo,
  "viagens_disponiveis")` em vez de `isinstance`. Funciona e segue o brief literalmente,
  mas é duck-typing implícito — se aparecer outro tipo de robô com esse atributo, o filtro
  passa a vazar.
- `descarregar` apenas publica `carga_disponivel`; não muta estado da unidade nem move a
  carga para armazém. É o que o brief especifica; presumo que a integração com a Central
  de Armazenagem seja responsabilidade de outra tarefa.
