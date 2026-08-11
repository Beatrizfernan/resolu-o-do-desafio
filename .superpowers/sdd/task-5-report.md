# Task 5 Report

## Escopo implementado

- Endpoint `POST /pesquisa/iniciar-analise` agora aceita `tipo_de_analise` opcional.
- Tipos suportados: `rapida`, `completa` e `forense`.
- `completa` permanece como valor padrao.
- `rapida` ajusta duracao para `0.5x` e custo para `0.8x`.
- `completa` mantem duracao e custo em `1.0x`.
- `forense` ajusta duracao para `1.5x` e custo para `1.4x`.
- Nesta task, `forense` ajusta apenas custo e duracao, sem efeitos extras de informacao.

## Arquivos alterados

- `mundo/api/pesquisa.py`
- `mundo/testes/test_api_pesquisa.py`

## TDD executado

### Red

- Adicionado teste `test_analise_rapida_termina_antes_da_completa` em `mundo/testes/test_api_pesquisa.py`.
- Comando executado:

```bash
pytest mundo/testes/test_api_pesquisa.py::test_analise_rapida_termina_antes_da_completa -v
```

- Resultado observado: `FAILED`.
- Motivo da falha: a requisicao enviava `tipo_de_analise`, mas a API ainda ignorava o campo e a analise mantinha a duracao padrao.

### Green

- `RequisicaoDeAnalise` passou a aceitar `tipo_de_analise` com default `completa`.
- `iniciar_analise` passou a aplicar multiplicadores de custo e duracao por tipo.
- Duracao calculada com `max(1, round(...))` para preservar minimo de 1 ciclo.

### Verificacao do teste novo

- Comando executado:

```bash
pytest mundo/testes/test_api_pesquisa.py::test_analise_rapida_termina_antes_da_completa -v
```

- Resultado observado: `PASSED`.

## Verificacao solicitada no brief

- Comando executado:

```bash
pytest mundo/testes/test_api_pesquisa.py -v
```

- Resultado observado: `17 passed`.

## Preservacao de restricoes

- Codigo de dominio mantido em portugues.
- Nenhuma mudanca em monetizacao, armazenagem ou sistemas cruzados.
- Fluxo de aprovacao para distribuicao foi preservado sem alteracoes.
- Mudanca permanece deterministica por seed, pois nao introduz aleatoriedade.
- Mutacoes por ciclo foram preservadas: a analise continua sendo enfileirada e concluida por efeito agendado.

## Self-review

- A mudanca ficou restrita ao endpoint de pesquisa e ao teste correspondente.
- O uso de `Literal` restringe os tipos aceitos no contrato da API e evita valores arbitrarios.
- O ajuste de duracao nao altera o mecanismo de fila, energia, aprovacao ou distribuicao.
- Nao foram encontrados efeitos colaterais no comportamento existente de `completa`.

## Commit

- Commit criado: `feat: adiciona tipos de analise`
