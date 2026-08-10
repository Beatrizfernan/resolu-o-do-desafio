# Correção dos achados finais — `mundo/`

Base: `14d40e7` (167 testes). Estado final: `eec28b4`, **174 testes passando**.

| Achado | Commit |
| --- | --- |
| 2 — efeitos agendados não canceláveis | `832c42e` |
| 1 — desperdício sem preço no motor | `eec28b4` |

> **Os commits saíram na ordem inversa da pedida.** Um segundo agente estava
> escrevendo neste mesmo worktree durante a tarefa e publicou `832c42e` antes de
> eu fechar o Achado 1. Detalhes e a consequência em "Concorrência", no fim.

---

## Achado 1 — escassez da jazida encarece a extração

### O que mudou

A energia de extração passa a ser multiplicada por um **fator de escassez** que
depende da fração restante da jazida:

```
fator = min(fator_escassez_maximo, fracao_restante ** -expoente_escassez)
```

Com `expoente_escassez = 2.0` e `fator_escassez_maximo = 100.0`
(`mundo/config/modos.json`). Numa jazida intacta o fator é exatamente `1.0`;
conforme a jazida esvazia, cada unidade seguinte custa mais.

Arquivos:

- `mundo/config/modos.json` — `fator_escassez_maximo`, `expoente_escassez`
- `mundo/dominio/modos.py` — `CatalogoDeModos.fator_de_escassez()`, expostos
  como `fator_base_de_energia` já era
- `mundo/dominio/jazidas.py` — campo `quantidade_inicial` (default via
  `__post_init__`, então nenhum ponto de construção existente quebrou) e
  propriedade `fracao_restante`
- `mundo/motor/motor_de_simulacao.py` — `quantidade_inicial` explícito na
  geração do mundo
- `mundo/api/extracao.py` — o fator entra no produto do custo

Invariantes verificadas: custo estritamente positivo e finito (fator ∈ [1,
`fator_escassez_maximo`], testado inclusive em `fracao_restante = 0`), e jazidas
continuam sem regenerar (teste dedicado).

### Por que isso dá preço ao desperdício

O fator é igual para todos os modos numa dada fração restante — o que difere é a
**velocidade com que cada modo chega lá**. Um modo com `fator_desperdicio = 1.4`
consome 40% mais jazida por unidade entregue que um modo com `1.0`, então empurra
a jazida para a faixa cara 40% mais depressa. Para um alvo fixo de minério, o
agressivo paga integral de escassez sobre um trecho maior da curva.

Isso só aparece quando o alvo é **uma quantidade de minério**, não "esvaziar a
jazida": se todos os modos exaurirem a jazida inteira, o `fator_desperdicio`
cancela entre minério obtido e energia gasta e a razão volta a ser
`qualidade_inicial / mult_energia`. A decisão estratégica real é "quanto desta
jazida eu quero", e é essa que passou a existir.

### Recalibração

**Nenhuma.** `modos.json` não teve nenhum valor de modo alterado — só ganhou as
duas chaves novas. A suíte de dominância continua verde sem ajuste.

### Vencedores pela métrica do teste (inalterados)

| Mineral | Vencedor |
| --- | --- |
| hematita | agressivo |
| silica_de_alta_pureza | normal |
| jarosita | normal |
| gelo_de_agua | normal |
| cristal_marciano_raro | cuidadoso |

`mundo/testes/test_dominancia_de_modos.py`: 6 passando.

### Quadro in-engine (o que o jogador realmente enfrenta)

Retorno = valor entregue por energia gasta, extraindo em passos de uma jazida
até um alvo `x` (alvo de minério como fração do tamanho original da jazida).
O mineral cancela na razão, então o quadro vale para todo o catálogo.

| x | cuidadoso | normal | agressivo |
| --- | --- | --- | --- |
| 0.05 | 13.3 | 21.8 | **40.6** |
| 0.25 | 10.5 | 16.2 | **28.4** |
| 0.50 | 7.0 | 9.3 | **13.2** |
| 0.60 | 5.6 | 6.5 | **7.1** |
| 0.63 | 5.2 | **5.7** | 5.3 |
| 0.66 | 4.8 | **4.9** | 3.6 |
| 0.70 | **4.2** | 3.8 | 2.6 |
| 0.80 | **2.8** | 1.5 | inviável |
| 1.00 | **0.7** | inviável | inviável |

Fronteiras: **agressivo vence até x ≈ 0.62, normal de 0.62 a 0.67, cuidadoso
acima de 0.67** — e é o único capaz de levar a jazida além de 0.83 (o normal
esbarra em 1/1.2 e o agressivo em 1/1.4). Nenhum modo domina.

**Ressalva honesta:** a janela do `normal` é estreita (~5% do eixo). Ela é
consequência das razões `qualidade_inicial / mult_energia` já fixadas (173.3 /
92.0 / 55.6) — nenhuma escolha de `expoente_escassez` a alarga sem mexer nesses
valores, e mexer neles quebra a métrica da suíte de dominância, que é sensível o
bastante para o agressivo só vencer hematita com `mult_energia ≤ 0.46`. Preferi
não recalibrar: o `normal` tem uma faixa própria de vitória, que era o requisito.

### Testes adicionados

- `test_api_extracao.py::test_extrair_de_jazida_esvaziada_custa_mais_que_de_jazida_intacta`
  — jazida com 25% restante custa ×16 a mesma extração numa jazida intacta
- `test_modos.py::test_fator_de_escassez_cresce_conforme_a_jazida_esvazia`
- `test_modos.py::test_fator_de_escassez_e_sempre_positivo_e_finito`
- `test_jazidas.py::test_fracao_restante_parte_de_um_e_cai_com_a_extracao`
- `test_jazidas.py::test_jazida_nunca_regenera`

### Asserções fixas atualizadas

**Nenhuma.** Contra a expectativa da revisão, `test_api_extracao.py` não quebrou:
todos os testes de custo extraem de `jazida-1` intacta, onde o fator de escassez
é exatamente `1.0`. Os números fixos (`custo_extracao × 10.0 × 0.2 ×
mult_energia`) continuam corretos por construção.

---

## Achado 2 — abortar/interromper agora cancela de fato

Implementado em `832c42e`. Cada `concluir()` agendado reconfere o estado da
unidade antes de agir e desiste se a operação foi abortada:

- `mundo/api/transporte.py` — se a unidade não está mais `EXECUTANDO`, publica
  `viagem_abortada` e retorna sem marcar a carga como `EM_ARMAZEM`
- `mundo/api/extracao.py` — se a unidade não está mais `EXECUTANDO`, publica
  `extracao_interrompida` e retorna sem consumir a jazida nem criar carga

`AgendaDeEfeitos` não foi tocada, como pedido. Os nomes de evento seguem o estilo
de cada router (`transporte_concluido` / `viagem_abortada`,
`extracao_concluida` / `extracao_interrompida`).

Testes:

- `test_api_transporte.py::test_abortar_viagem_meio_do_caminho_impede_entrega_e_publica_evento`
  — a carga permanece `EM_TRANSITO` no ciclo original de chegada
- `test_api_extracao.py::test_interromper_extracao_impede_criacao_de_carga_e_publica_evento`
  — nenhuma carga criada e a jazida intacta no ciclo original de conclusão

Revisei o código e os testes: ambos avançam até o ciclo de conclusão original e
provam a ausência do efeito, não só a mudança de estado da unidade.

---

## Concorrência — leia antes do merge

Um segundo agente editou e commitou nestes mesmos arquivos enquanto eu
trabalhava. Consequências reais:

1. **Ordem dos commits invertida** em relação ao pedido (Achado 2 antes do 1).
2. **`832c42e` não compila isoladamente.** Ele arrastou junto duas linhas do meu
   Achado 1 (a multiplicação por `fator_de_escassez` em `extracao.py` e o teste
   de escassez), que referenciam `CatalogoDeModos.fator_de_escassez` e
   `Jazida.fracao_restante` — símbolos que só passam a existir em `eec28b4`. Ou
   seja: **`832c42e` está quebrado como commit intermediário**; a árvore só volta
   a ficar sã em `eec28b4`.
3. Corrigi também uma duplicação de chaves em `modos.json` introduzida por esse
   outro agente (`fator_escassez_maximo` e `expoente_de_escassez` aparecendo duas
   vezes, com nomes e valores divergentes).

Não reescrevi o histórico para consertar (2) porque o outro agente podia estar
ativo. Se o merge for por squash, o problema desaparece sozinho. Se o histórico
for preservado, vale um `git rebase -i 14d40e7` movendo as duas linhas para o
commit certo — ou simplesmente um squash dos dois commits.
