# Task 1 Report

## Status

Concluida.

## Requisitos Atendidos

- `Autorizacao` agora carrega o metadado `classe` com default `"rapida"`.
- `RegistroDeAutorizacoes.emitir` passou a aceitar `classe` e preserva esse valor ao consumir a autorizacao.
- `POST /missao/autorizar-missao` agora aceita `classe` em `"rapida" | "segura" | "lote"`.
- O debito de energia da central `missao` usa os custos exatos do brief: `0.2`, `0.5`, `0.8`.

## TDD Executado

1. Adicionado `test_autorizacao_segura_custa_mais_que_rapida` em `mundo/testes/test_api_missao.py`.
2. Executado `pytest mundo/testes/test_api_missao.py::test_autorizacao_segura_custa_mais_que_rapida -v`.
3. Falha observada: a rota continuava debitando apenas `motor.catalogo_de_operacao.custo_de_autorizacao`.
4. Adicionado `test_autorizacao_em_lote_registra_classe_no_registro` em `mundo/testes/test_api_missao.py`.
5. Executado `pytest mundo/testes/test_api_missao.py::test_autorizacao_em_lote_registra_classe_no_registro -v`.
6. Falha observada: `RegistroDeAutorizacoes.emitir()` nao aceitava `classe`.
7. Implementacao minima aplicada em `mundo/dominio/autorizacao.py` e `mundo/api/missao.py`.
8. Reexecutados os dois testes isolados com sucesso.
9. Executado `pytest mundo/testes/test_api_missao.py -v` com sucesso.

## Self-Review

- Escopo mantido apenas em Missao e autorizacoes; nada foi expandido para Armazenagem ou sistemas cruzados.
- A classe foi tratada apenas como metadado e custo distinto, sem introduzir expiracao diferenciada.
- O endpoint de autorizacao permaneceu sincrono como ja era antes; nenhuma mutacao por ciclo adicional foi introduzida.
- O default `"rapida"` preserva compatibilidade com chamadas existentes.

## Arquivos Alterados

- `mundo/dominio/autorizacao.py`
- `mundo/api/missao.py`
- `mundo/testes/test_api_missao.py`

## Observacoes

- Os testes executados passaram com 2 warnings preexistentes do ambiente pytest/FastAPI (`asyncio_mode` desconhecido e `starlette.testclient` deprecado com `httpx`).
- Hash do commit: pendente no momento da escrita inicial do relatorio.
