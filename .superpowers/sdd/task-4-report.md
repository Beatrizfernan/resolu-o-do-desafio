# Task 4 Report: Perfis de Escavacao na Extracao

## Escopo executado

- Adicionado o campo opcional `perfil_de_escavacao` em `POST /extracao/iniciar-extracao`.
- Implementados os perfis `superficial`, `profunda` e `mapeadora` com os ajustes exatos do brief.
- Mantido o escopo restrito a `mundo/api/extracao.py` e `mundo/testes/test_api_extracao.py`.
- Nao foi implementado nenhum efeito extra de revelacao de informacao para `mapeadora`.

## TDD executado

1. Escrevi o teste `test_perfil_profundo_custa_mais_energia_que_superficial`.
2. O teste inicial do brief passou por acaso porque o payload extra era ignorado e a assercao verificava apenas um custo absoluto ja verdadeiro. Ajustei o teste para comparar `superficial` vs `profunda` e rodei de novo.
3. Rodei `pytest mundo/testes/test_api_extracao.py::test_perfil_profundo_custa_mais_energia_que_superficial -v` e confirmei falha real de comportamento.
4. Adicionei o teste `test_perfil_mapeadora_melhora_qualidade_inicial_da_carga` para ancorar o ajuste de qualidade.
5. Rodei ambos os testes e confirmei falha antes da implementacao.
6. Implementei a mudanca minima em `mundo/api/extracao.py`.
7. Rodei os testes novos e confirmei verde.
8. Rodei a suite completa de `mundo/testes/test_api_extracao.py`; isso expôs expectativas antigas de custo que ainda refletiam o comportamento pre-task.
9. Atualizei essas expectativas para o novo padrao `superficial` e rodei a suite completa novamente ate ficar verde.

## Implementacao

- `RequisicaoDeExtracao` agora aceita `perfil_de_escavacao` com valores literais validos e padrao `superficial`.
- O custo energetico da extracao agora multiplica o custo base pelo ajuste de energia do perfil.
- A qualidade inicial da carga agora soma o bonus de qualidade do perfil, limitada a `100.0`.
- Nenhuma mudanca foi feita em mutacoes por ciclo, seed, transporte, armazenagem ou sistemas cruzados.

## Testes executados

- `pytest mundo/testes/test_api_extracao.py::test_perfil_profundo_custa_mais_energia_que_superficial -v`
- `pytest mundo/testes/test_api_extracao.py::test_perfil_profundo_custa_mais_energia_que_superficial mundo/testes/test_api_extracao.py::test_perfil_mapeadora_melhora_qualidade_inicial_da_carga -v`
- `pytest mundo/testes/test_api_extracao.py -v`

## Self-review

- Conferi o diff para garantir que a mudanca ficou restrita aos arquivos da task.
- Verifiquei que o perfil padrao `superficial` altera o custo base esperado e, por isso, atualizei os testes historicos de custo para refletirem o novo contrato.
- Mantive o codigo de dominio em portugues e sem reintroduzir qualquer regra de monetizacao.
- Mantive o comportamento deterministico: nao houve adicao de aleatoriedade nem alteracao do fluxo de agendamento por ciclo.

## Observacoes

- Os comandos de `pytest` continuam emitindo warnings pre-existentes sobre `asyncio_mode` e `starlette.testclient`; nao foram introduzidos por esta task.
