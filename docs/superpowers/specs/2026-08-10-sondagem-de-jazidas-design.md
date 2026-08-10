# Sondagem De Jazidas Design

## Objetivo

Adicionar uma nova capacidade na Central de Pesquisa para revelar uma estimativa da composicao de cada jazida em faixas qualitativas, permitindo que a Central de Transporte e a Central de Missao tomem decisoes melhores sobre prioridade, modo de transporte e alocacao de energia sem transformar a Pesquisa em um oraculo exato.

## Contexto Atual

- O mundo atual trata cada `jazida` como uma fonte com `mineral` predominante conhecido.
- A extracao gera `CargaMineral` de um unico mineral por operacao.
- A Central de Pesquisa hoje so opera sobre `carga`, com um unico gargalo (`capacidade_paralela = 1`).
- O `README.md` ja documenta as mecanicas gerais do desafio e substitui o antigo `INSTRUCOES.md`.

## Decisao

Implementar a abordagem de composicao estimada por faixas.

Cada jazida passara a carregar tres visoes diferentes:

1. `mineral`: o mineral predominante, que continua visivel e preserva o fluxo atual de extracao.
2. `composicao_real`: a mistura interna verdadeira da jazida, armazenada no dominio e usada como fonte para a sondagem.
3. `composicao_estimada`: a leitura parcial e persistida pela Central de Pesquisa apos a conclusao da sondagem.

Essa mudanca e deliberadamente parcial: ela melhora a assimetria de informacao para os participantes sem exigir uma refatoracao completa do fluxo de extracao para misturas reais de cargas neste momento.

## Abordagens Consideradas

### 1. Composicao estimada por faixas

Retornar categorias como `ausente`, `tracos`, `baixa`, `media` e `alta` por mineral.

Vantagens:

- entrega informacao suficiente para estrategia;
- preserva incerteza e espaco para heuristica;
- exige mudanca moderada no dominio existente.

Desvantagens:

- exige introduzir composicao no dominio mesmo sem alterar a extracao para mistura real.

### 2. Composicao percentual aproximada

Retornar valores percentuais por mineral.

Vantagens:

- aumenta o poder de decisao dos algoritmos;
- facilita comparacao direta entre jazidas.

Desvantagens:

- reduz demais a incerteza;
- aproxima a Pesquisa de uma resposta exata demais para o desafio.

### 3. Score economico sintetico

Retornar apenas um score agregado da jazida.

Vantagens:

- mudanca pequena;
- baixo impacto na API.

Desvantagens:

- nao atende o requisito explicito de estimativa de composicao;
- oferece menos transparencia ao participante.

## Modelo De Dominio

### Jazida

Adicionar os seguintes campos em `mundo/dominio/jazidas.py`:

- `composicao_real: dict[str, float] | None = None`
- `composicao_estimada: dict[str, str] | None = None`

Regras:

- `composicao_real` representa pesos ou fracoes internas por mineral.
- `composicao_estimada` representa a leitura revelada ao participante em faixas qualitativas.
- `mineral` continua sendo o mineral predominante e nao deixa de existir.
- se `composicao_real` nao vier preenchida, o dominio gera uma composicao coerente a partir do mineral predominante.

### Geracao do mundo

No `MotorDeSimulacao`, cada jazida passa a nascer com uma composicao real:

- o mineral predominante recebe a maior participacao;
- minerais secundarios podem aparecer em menor peso;
- minerais raros podem surgir como `tracos` ou `baixa` participacao;
- a geracao continua deterministica pela semente do motor.

### Conversao para faixas

Introduzir uma regra simples e estatica de conversao, por exemplo:

- `0%` -> `ausente`
- `> 0% e <= 5%` -> `tracos`
- `> 5% e <= 20%` -> `baixa`
- `> 20% e <= 50%` -> `media`
- `> 50%` -> `alta`

Esses limiares ficam no codigo por enquanto para manter a mudanca pequena, a menos que testes mostrem necessidade real de configuracao externa.

## API Da Pesquisa

### Novo comando

Criar `POST /pesquisa/sondar-jazida` com payload:

```json
{
  "identificador_da_jazida": "jazida-3"
}
```

Fluxo:

1. a requisicao valida a existencia da jazida;
2. o comando e enfileirado na Central de Pesquisa;
3. quando executado, consome energia da Pesquisa;
4. ocupa o mesmo slot de `iniciar-analise`;
5. agenda a conclusao para alguns ciclos a frente;
6. ao concluir, grava `composicao_estimada` na jazida e publica `sondagem_de_jazida_concluida`.

### Nova consulta

Criar `GET /pesquisa/jazidas/{identificador}/estimativa`.

Resposta esperada apos a sondagem:

```json
{
  "jazida": "jazida-3",
  "mineral_predominante": "hematita",
  "estimativa_de_composicao": {
    "hematita": "alta",
    "jarosita": "media",
    "cristal_raro": "tracos"
  }
}
```

Comportamento antes de sondar:

- retornar `404` com mensagem explicita informando que a jazida ainda nao possui estimativa conhecida.

## Regras Operacionais

### Gargalo compartilhado

A sondagem compartilha o mesmo gargalo da Central de Pesquisa com as analises de carga.

Consequencias:

- nao e possivel sondar uma jazida enquanto outra analise ou outra sondagem estiver em andamento;
- o participante precisa decidir entre usar a Pesquisa para descobrir composicao ou para destravar faturamento de cargas.

### Repeticao de sondagem

Se a jazida ja tiver `composicao_estimada`, uma nova tentativa de sondagem deve ser rejeitada via `operacao_invalida` com motivo explicito.

Motivo da decisao:

- evita spam;
- evita custo inutil;
- deixa claro que a descoberta e um conhecimento persistido.

### Energia e falhas

- central dormente: rejeitar como qualquer outra operacao da Pesquisa;
- slot ocupado: rejeitar com a mesma semantica usada hoje para analise;
- jazida inexistente: `404`;
- erros de negocio continuam indo para `operacao_invalida` quando o comando falha dentro do ciclo.

## Eventos

Adicionar um novo evento operacional:

- `sondagem_de_jazida_concluida`

Envelope esperado:

```json
{
  "tipo": "sondagem_de_jazida_concluida",
  "ciclo": 12,
  "dados": {
    "jazida": "jazida-3",
    "estimativa_de_composicao": {
      "hematita": "alta",
      "jarosita": "media",
      "cristal_raro": "tracos"
    }
  }
}
```

## Documentacao Para Participantes

### README raiz

Atualizar o `README.md` para:

- explicar a nova sondagem da Pesquisa;
- mostrar que o Transporte pode usar estimativa de composicao para decidir `economico`, `padrao` ou `urgente`;
- reforcar que a Pesquisa continua sendo gargalo unico.

### Diretorios das centrais

Criar os diretorios vazios dos participantes com um `README.md` detalhado em cada um:

- `centrais/extracao/README.md`
- `centrais/transporte/README.md`
- `centrais/armazenagem/README.md`
- `centrais/pesquisa/README.md`
- `centrais/missao/README.md`

Cada documento deve cobrir:

- responsabilidade da central;
- APIs que mais importam para ela;
- informacoes observaveis e informacoes ocultas;
- vantagens e desvantagens da frente;
- erros e mecanicas que pedem estrategia valida;
- como a central coopera com as demais.

## Estrategia De Implementacao

1. expandir o dominio de `Jazida` e sua geracao deterministica;
2. adicionar testes do dominio para composicao real e estimada;
3. adicionar a API de sondagem e a consulta de estimativa;
4. cobrir o novo fluxo nos testes da Pesquisa;
5. atualizar `README.md` e criar os `README.md` das centrais.

## Testes Necessarios

### Dominio

- jazida nasce com composicao real coerente;
- conversao de composicao real para faixas funciona;
- jazida sem estimativa falha na consulta apropriada da API;
- estimativa persistida continua disponivel apos a conclusao.

### API de Pesquisa

- sondagem aceita quando ha energia e slot;
- sondagem entra em disputa com `iniciar-analise`;
- evento `sondagem_de_jazida_concluida` e emitido;
- consulta retorna as faixas esperadas;
- repetir sondagem da mesma jazida gera `operacao_invalida`.

### Regressao

- `iniciar-analise` continua funcional;
- `classificar-carga` nao muda de comportamento;
- o gargalo de capacidade 1 continua verdadeiro para a Central de Pesquisa.

## Fora De Escopo

- transformar extracao em mistura real por carga;
- alterar faturamento com base na composicao sondada;
- criar percentuais precisos na API publica;
- adicionar nova infraestrutura ou novo subsistema para fila.

## Riscos E Mitigacoes

### Risco: vazamento excessivo de informacao

Mitigacao:

- usar faixas qualitativas em vez de percentuais.

### Risco: dominio ficar incoerente com extracao atual

Mitigacao:

- manter `mineral` como predominante e usar `composicao_real` apenas para sondagem nesta iteracao.

### Risco: documentacao dos participantes ficar superficial

Mitigacao:

- escrever um `README.md` por central com foco em estrategia, limites e armadilhas reais do mundo.
