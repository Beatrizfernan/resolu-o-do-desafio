# Task 6 Report

## Status

DONE

## Escopo implementado

- Atualizei `POST /pesquisa/aprovar-carga` para aceitar `politica` opcional por requisição.
- Mantive a politica atuando apenas no limiar da aprovação atual, sem persistir estado na central.
- Preservei a exigência de aprovação formal para distribuição e não ampliei escopo para Armazenagem nem Sistemas cruzados.

## Politicas aplicadas

- `comercial`: usa `motor.catalogo_de_pesquisa.limiar_qualidade_aprovacao` (40.0 no catálogo atual).
- `estrita`: 70.0.
- `premium`: 85.0.

## TDD

1. Adicionei o teste `test_politica_estrita_exige_qualidade_maior_que_a_comercial` em `mundo/testes/test_api_pesquisa.py`.
2. Rodei `pytest mundo/testes/test_api_pesquisa.py::test_politica_estrita_exige_qualidade_maior_que_a_comercial -v` e confirmei o vermelho esperado: a carga ainda era aprovada sem suporte a politica.
3. Implementei o suporte minimo em `mundo/api/pesquisa.py` com `RequisicaoDeAprovacao` e selecao do limiar por politica.
4. Rodei `pytest mundo/testes/test_api_pesquisa.py -v` e confirmei a suite verde.

## Self-review

- O endpoint continua aceitando chamadas antigas sem `politica`, via default `comercial`.
- O comportamento segue deterministico: nao houve introducao de aleatoriedade nem mudanca no uso da seed.
- A mutacao de estado continua ocorrendo no processamento do comando enfileirado por ciclo, preservando a semantica existente.
- Os tipos de analise permanecem intactos; a mudanca ficou isolada no fluxo de aprovacao.

## Testes executados

- `pytest mundo/testes/test_api_pesquisa.py::test_politica_estrita_exige_qualidade_maior_que_a_comercial -v`
- `pytest mundo/testes/test_api_pesquisa.py -v`

## Commit

- `feat: adiciona politicas de aprovacao`
