# Design - Avaliador e Integridade - Operacao Marciana

## 1. Contexto e escopo

Este documento especifica o design tecnico dos subsistemas `avaliador/` e `integridade/`, conforme `SPEC_INICIAL.md`, `DOCUMENTACAO_DO_PROJETO.md`, `README.md` e o estado atual de `mundo/`.

Escopo desta spec:

- implementar um `avaliador/` offline;
- implementar `integridade/` para proteger o codigo-base da plataforma;
- definir o contrato offline que conecta `centrais/` ao avaliador;
- gerar um relatorio local em Markdown com os resultados da avaliacao.

Fora do escopo:

- interface HTTP para o avaliador;
- isolamento de processos ou sandbox do codigo em `centrais/`;
- score composto opaco acima das metricas-base;
- qualquer imposicao de arquitetura interna dentro de `centrais/` alem do ponto de entrada exigido pelo avaliador.

## 2. Objetivos de produto

O avaliador existe para executar varias simulacoes reproduziveis sobre o mesmo codigo de `centrais/`, medir o resultado operacional agregado e produzir um artefato local auditavel.

O subsistema de integridade existe para garantir que o competidor nao alterou o nucleo confiavel da plataforma entre a geracao do manifesto e a avaliacao. O que pode variar e `centrais/`; o que nao pode variar e o comportamento do mundo nem da propria avaliacao.

## 3. Decisoes de arquitetura

### 3.1 Visao geral

O sistema fica dividido em quatro blocos:

1. `mundo/`
   Fonte de verdade da simulacao. O avaliador nunca replica regra de dominio; apenas instancia o motor, avanca ciclos, observa eventos e coleta o resultado final.

2. `centrais/`
   Codigo do participante. Pode ser organizado livremente, mas precisa expor um ponto de entrada estavel para a avaliacao offline.

3. `integridade/`
   Gera e verifica um manifesto de hashes dos arquivos protegidos. Roda antes da avaliacao.

4. `avaliador/`
   Orquestrador offline responsavel por verificar integridade, executar seeds, invocar o runner das centrais, coletar metricas, agregar resultados e escrever o relatorio Markdown.

### 3.2 Abordagem escolhida

O avaliador sera um orquestrador Python em processo, nao uma aplicacao HTTP. Ele reutiliza diretamente o modo de tick manual do `mundo/`, porque esse caminho ja foi previsto na spec do Mundo para testes e futuras execucoes em lote.

Essa escolha reduz acoplamento acidental, evita infraestrutura temporaria de rede, simplifica testes e mantem reproducibilidade alta.

### 3.3 Fluxo principal

```text
verificar_integridade
  -> se falhar: abortar e gerar relatorio curto
  -> para cada seed:
       criar mundo limpo
       criar cliente de avaliacao
       carregar centrais.avaliacao:executar_avaliacao
       executar a estrategia
       coletar metricas da seed
  -> agregar resultados
  -> escrever relatorio Markdown local
```

## 4. Contrato entre avaliador e centrais

### 4.1 Ponto de entrada obrigatorio

O avaliador conhece apenas:

- arquivo: `centrais/avaliacao.py`
- simbolo obrigatorio: `executar_avaliacao`

Assinatura:

```python
def executar_avaliacao(cliente, limite_de_ciclos: int) -> None:
    ...
```

### 4.2 Responsabilidade do participante

`executar_avaliacao` dirige a estrategia da operacao para uma seed. O participante controla quando consultar estado, quando consultar eventos, quais comandos enviar e quando avancar ciclos.

### 4.3 Cliente de avaliacao

O avaliador entrega ao participante uma fachada controlada, sem acesso cru ao `MotorDeSimulacao`.

Essa fachada precisa expor somente o necessario para operar a simulacao offline:

- consultar estado consolidado do mundo;
- consultar eventos desde um ciclo;
- enviar comandos equivalentes aos endpoints das centrais;
- avancar um ciclo ou varios ciclos;
- consultar se a simulacao encerrou.

O contrato da fachada deve ser pequeno e estavel. O objetivo e permitir estrategia, nao introspeccao irrestrita do motor.

### 4.4 Restricoes

- `centrais/` nao recebe referencia direta ao motor;
- `centrais/` nao depende de `avaliador/` ou `integridade/` como biblioteca de dominio;
- qualquer organizacao interna em `centrais/` continua livre, respeitando o ponto de entrada fixo.

### 4.5 Falhas do runner

Se `executar_avaliacao` levantar excecao:

- a seed e marcada como `falha_operacional`;
- o traceback resumido entra no relatorio;
- o avaliador continua para as proximas seeds.

## 5. Integridade

### 5.1 Objetivo

Garantir que o codigo-base confiavel da plataforma nao foi alterado durante a avaliacao.

### 5.2 Operacoes

O subsistema `integridade/` expora duas operacoes offline:

1. `gerar_manifesto_integridade`
   Produz um manifesto versionado contendo o hash SHA-256 de cada arquivo protegido.

2. `verificar_integridade`
   Recalcula os hashes e compara com o manifesto salvo.

### 5.3 Escopo protegido

Entram no manifesto:

- `mundo/**`
- `avaliador/**`
- `pyproject.toml`

Nao entram no manifesto:

- `centrais/**`
- relatorios gerados;
- caches e artefatos temporarios;
- `__pycache__`, `.pytest_cache`, `*.pyc`.

### 5.4 Formato do manifesto

O manifesto sera um JSON simples e deterministico, com:

- versao do formato;
- raiz do projeto relativa considerada;
- algoritmo (`sha256`);
- mapa ordenado de `caminho_relativo -> hash`.

Exemplo conceitual:

```json
{
  "versao": 1,
  "algoritmo": "sha256",
  "arquivos": {
    "mundo/api/extracao.py": "...",
    "pyproject.toml": "..."
  }
}
```

### 5.5 Politica de falha

- manifesto ausente: erro explicito e avaliacao abortada;
- arquivo protegido ausente: falha de integridade;
- hash divergente: falha de integridade;
- arquivo novo dentro do escopo protegido e nao manifestado: falha de integridade.

Quando a integridade falha, a avaliacao competitiva nao roda. Ainda assim, um relatorio Markdown curto deve ser gerado para registrar a causa do bloqueio.

## 6. Execucao do avaliador

### 6.1 CLI

Comando principal:

```bash
python -m avaliador.cli
```

Argumentos iniciais:

- `--seeds 101,202,303`
- `--quantidade-seeds 20`
- `--seed-inicial 1000`
- `--saida docs/relatorios/avaliacao.md`
- `--limite-de-ciclos 5000`
- `--manifesto integridade/manifesto.sha256.json`

Regra:

- se `--seeds` vier, usar exatamente a lista informada;
- caso contrario, gerar a sequencia a partir de `seed-inicial` e `quantidade-seeds`.

### 6.2 Ciclo por seed

Para cada seed, o avaliador deve:

1. reinstanciar um mundo limpo com aquela seed;
2. criar um cliente de avaliacao acoplado a esse mundo;
3. carregar dinamicamente `centrais/avaliacao.py`;
4. chamar `executar_avaliacao(cliente, limite_de_ciclos)`;
5. encerrar a seed quando o mundo publicar `simulacao_encerrada` ou quando a execucao atingir o limite defensivo;
6. coletar as metricas e registrar o status.

### 6.3 Limite de ciclos

O limite de ciclos e um fusivel operacional do avaliador, nao a regra principal de encerramento do mundo.

Se a estrategia nao concluir a operacao antes do limite:

- a seed recebe status `limite_excedido`;
- o avaliador registra o fato e segue para a proxima seed.

## 7. Metricas

### 7.1 Metricas por seed

Cada seed deve produzir um registro com pelo menos:

- `seed`;
- `status` (`ok`, `falha_operacional`, `limite_excedido`, `erro_de_configuracao` quando aplicavel);
- `ciclo_final`;
- `faturamento_total`;
- `energia_encalhada`;
- `erro_operacional` resumido, se houver.

Tambem devem ser coletados contadores derivados dos eventos e do estado final quando disponiveis sem duplicar regra de dominio:

- quantidade de `operacao_invalida`;
- quantidade de autorizacoes emitidas;
- quantidade de cargas entregues;
- quantidade de cargas analisadas;
- quantidade de jazidas esgotadas.

### 7.2 Resultado agregado

O avaliador deve calcular no minimo:

- `faturamento_medio`;
- `faturamento_mediano`;
- `melhor_seed`;
- `pior_seed`;
- `ciclo_medio_de_encerramento`;
- `energia_encalhada_media`;
- `taxa_de_falha_operacional`.

### 7.3 Regra de ordenacao principal

O resultado global deve ser auditavel. Portanto, a primeira versao nao cria um score opaco.

Ordem recomendada para comparacao de resultados:

1. maior `faturamento_medio`;
2. menor `energia_encalhada_media`;
3. menor `taxa_de_falha_operacional`.

Isso aproveita o fato de o proprio `mundo/` ja condensar os principais trade-offs no faturamento final, enquanto preserva sinais auxiliares importantes sobre desperdicio e robustez.

## 8. Relatorio Markdown

### 8.1 Objetivo

Gerar um artefato local legivel por humanos e deterministicamente testavel.

### 8.2 Estrutura

O relatorio deve conter:

1. titulo e data da avaliacao;
2. status da integridade;
3. configuracao da execucao;
4. resumo executivo;
5. tabela de resultados por seed;
6. metricas agregadas;
7. falhas operacionais ou bloqueios;
8. observacoes finais.

### 8.3 Comportamento em falha de integridade

Se a integridade reprovar, o relatorio nao mostra placar competitivo. Em vez disso, mostra:

- status de integridade reprovado;
- manifesto utilizado;
- arquivos divergentes ou ausentes;
- conclusao de que a avaliacao foi abortada.

## 9. Estrutura de codigo proposta

```text
avaliador/
├── __init__.py
├── aplicacao/
│   ├── avaliador_offline.py
│   ├── carregador_de_centrais.py
│   ├── cliente_de_avaliacao.py
│   ├── coletor_de_metricas.py
│   └── renderizador_markdown.py
├── dominio/
│   ├── resultado_da_seed.py
│   ├── relatorio_de_avaliacao.py
│   └── status_de_avaliacao.py
├── cli.py
└── testes/

integridade/
├── __init__.py
├── manifesto.py
├── verificador.py
└── testes/
```

Essa decomposicao e pequena, mas separa claramente:

- orquestracao da avaliacao;
- contrato com `centrais/`;
- coleta e agregacao de metricas;
- renderizacao do relatorio;
- geracao e verificacao do manifesto.

## 10. Tratamento de erro

### 10.1 Falha de integridade

- aborta a avaliacao;
- gera relatorio curto de bloqueio;
- retorna codigo de saida diferente de zero na CLI.

### 10.2 Contrato invalido de `centrais/`

Se `centrais/avaliacao.py` nao existir, nao puder ser importado, ou nao expuser `executar_avaliacao`, isso e erro de configuracao da avaliacao. Nessa situacao:

- a execucao nao roda seeds;
- o relatorio registra o problema como erro global.

### 10.3 Excecao em uma seed

- registrar traceback resumido;
- marcar a seed como `falha_operacional`;
- seguir para as demais seeds.

### 10.4 Limite excedido

- marcar a seed como `limite_excedido`;
- registrar no relatorio;
- seguir para as demais seeds.

## 11. Testes

### 11.1 Integridade

Cobertura minima:

- gera manifesto e verifica sucesso sem alteracoes;
- detecta arquivo protegido alterado;
- ignora `centrais/`;
- detecta arquivo protegido ausente;
- detecta arquivo protegido novo fora do manifesto.

### 11.2 Avaliador

Cobertura minima:

- carrega `centrais/avaliacao.py` valido;
- falha quando `executar_avaliacao` nao existe;
- executa multiplas seeds e agrega resultados;
- continua apos excecao em uma seed;
- produz Markdown com as secoes esperadas;
- aborta quando a integridade falha;
- respeita `limite_de_ciclos`.

### 11.3 Determinismo

O relatorio deve ser deterministicamente renderizado para a mesma configuracao de entrada e os mesmos resultados. O avaliador nao pode introduzir aleatoriedade propria fora da lista de seeds informada.

## 12. Decisoes descartadas

- Subir uma API HTTP real para avaliar: descartado por aumentar custo operacional sem melhorar o objetivo offline.
- Dar acesso direto ao `MotorDeSimulacao` para `centrais/`: descartado por quebrar a fronteira entre estrategia e motor.
- Criar score unico opaco logo na primeira versao: descartado para manter auditabilidade.
- Incluir `centrais/` no manifesto de integridade: descartado porque justamente esse e o codigo que deve variar entre participantes.

## 13. Impacto esperado

Com esse desenho, a plataforma passa a ter:

- uma forma reproduzivel de comparar estrategias;
- uma garantia minima de que o nucleo confiavel nao foi adulterado;
- um contrato offline pequeno para participantes;
- um artefato final legivel sem dependencia de interface grafica.
