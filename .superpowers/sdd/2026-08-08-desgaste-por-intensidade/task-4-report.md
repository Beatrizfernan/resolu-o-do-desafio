# Task 4 — Desgaste no transporte

## Status: DONE

## O que mudou

### `mundo/api/transporte.py`
Dentro do closure `executar()` de `iniciar_viagem` (a autorização continua sendo
consumida como primeira ação, antes de qualquer validação ou mutação):

- O débito de linha única
  `motor.energia.debitar(CENTRAL, CUSTO_ENERGETICO_VIAGEM * perfil.mult_energia)`
  virou um `custo` nomeado, composto como produto:

```python
custo = (
    CUSTO_ENERGETICO_VIAGEM
    * perfil.mult_energia
    * motor.catalogo_de_modos.fator_de_desgaste(unidade.desgaste)
)
motor.energia.debitar(CENTRAL, custo)
unidade.desgaste += custo * motor.catalogo_de_modos.taxa_de_desgaste
```

- O desgaste acumula a partir do custo **final** (já com o fator de desgaste
  aplicado), igual ao padrão estabelecido em `mundo/api/extracao.py` na Task 3.
  Isso é deliberado: uma unidade desgastada paga mais e, por pagar mais, se
  desgasta mais rápido.
- O evento `transporte_concluido` ganhou o campo `desgaste_da_unidade`
  (lido no momento da conclusão), preservando `unidade`, `carga` e `modo`.

Invariantes preservadas: nenhum handler mutou estado de forma síncrona; nenhuma
aleatoriedade nova; `fator_de_desgaste` retorna `1.0 + max(0, desgaste) * k`,
sempre >= 1.0, então o custo permanece estritamente positivo.

### `mundo/testes/test_desgaste.py`
Acrescentados (conforme o brief, verbatim):
- `_autorizar(cliente)` — helper que obtém um `id_autorizacao` para `iniciar_viagem`.
- `test_transportadora_desgastada_paga_mais_pela_mesma_viagem`
- `test_viagem_acumula_desgaste_na_transportadora`

Import adicionado: `from mundo.dominio.cargas import CargaMineral`.

## Testes

- Step 2 (vermelho): `2 failed, 6 passed` — custos iguais entre desgaste 0.0 e
  4.0, e `unidade.desgaste == 0.0` contra o esperado `1.5`.
- Step 4 (verde): `8 passed` em `test_desgaste.py`.
- Step 5 (suíte completa): `186 passed` em `mundo/testes`.

## Asserções pré-existentes atualizadas

**Nenhuma.** O Step 5 antecipava falhas em `test_api_transporte.py`, mas nenhuma
ocorreu. Motivo: todo teste com energia fixada usa uma app recém-criada, onde
`transportadora-1` começa com `desgaste = 0.0`, e faz apenas uma viagem. Com
desgaste zero, `fator_de_desgaste(0.0) == 1.0`, então o custo continua
`3 * mult_energia` — idêntico ao valor anterior. As asserções verificadas:

- `test_iniciar_viagem_exige_autorizacao_e_debita_viagem_disponivel`
  (`== energia_antes - 3`) — uma viagem só, desgaste inicial 0 → 3 * 1.0 * 1.0 = 3.
- `test_modo_rapido_chega_antes_e_gasta_mais_energia_que_o_economico` — app nova
  por modo, comparação relativa, não valor fixo.
- `test_iniciar_viagem_sem_viagens_disponiveis...` e
  `test_iniciar_viagem_com_carga_inexistente...` — asseguram que **nada** é
  debitado; o caminho de erro não chega ao cálculo de custo.

Nenhum desgaste foi enfraquecido ou desabilitado para acomodar teste antigo.
