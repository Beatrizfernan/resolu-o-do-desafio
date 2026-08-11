# Central de Transporte

Guia tecnico da interface HTTP implementada hoje pela central de transporte.

## Papel atual da central

A central de transporte expõe contratos para consultar rotas, unidades e cargas, carregar uma unidade, iniciar uma viagem, abortar a viagem em andamento, descarregar a carga e liberar a unidade no fim do retorno.

## Dependencias reais entre centrais

- Transporte depende de carga criada pela Extracao ou liberada pela Armazenagem.
- Transporte depende de autorizacao emitida pela Missao para iniciar viagem.
- Transporte entrega carga para as etapas seguintes por meio do evento `carga_disponivel` ou do estado da carga apos `transporte_concluido`.
- Transporte nao revela qualidade real da carga.

### Extracao -> Transporte

- `POST /extracao/iniciar-extracao` agenda a extracao; a carga nova so passa a existir na conclusao, em `EM_JAZIDA`.
- Quando a extracao termina, o mundo publica `extracao_concluida` com o identificador da carga.
- `POST /transporte/iniciar-viagem` aceita cargas em `EM_JAZIDA` e em `NA_MAO`.

### Armazenagem -> Transporte

- A armazenagem pode liberar uma carga para transporte e publicar `carga_disponivel` por `POST /armazenagem/solicitar-transporte`.
- `POST /transporte/iniciar-viagem` rejeita cargas em `EM_ARMAZEM` e em `EM_TRANSITO`.

### Missao -> Transporte

- A viagem exige uma autorizacao emitida antes em `POST /missao/autorizar-missao`.
- Para emitir uma autorizacao compativel com esta viagem, o exemplo de chamada usa `operacao: "iniciar_viagem"` e `central_solicitante: "transporte"`.
- A autorizacao e consumida na execucao do comando e nao pode ser reutilizada.

## Endpoints implementados

### `GET /transporte/rotas`

Retorna todas as rotas cadastradas. A malha e hibrida: `10` rotas fixas equilibradas e `10` rotas variantes distribuidas por seed, cada uma com perfil proprio de custo, degradacao, desgaste e capacidade.

Campos na resposta:

- `identificador`: nome da rota (`rota-1` a `rota-10` para fixas, `rota-alt-1` a `rota-alt-10` para variantes).
- `origem`: setor de partida.
- `destino`: `central-distribuicao`.
- `distancia`: distancia da rota.
- `tempo_base`: ciclos base da viagem antes do modo.
- `perfil`: nome do perfil (`padrao` para fixas; `blindada`, `economica`, `turbo`, etc. para variantes).
- `tipo`: `fixa` ou `variante`.
- `vantagem`, `desvantagem`: descricao textual do trade-off da rota.
- `custo_energia_base`: custo energetico antes do multiplicador do modo.
- `multiplicador_degradacao`: quanto a rota acelera ou retarda a perda de qualidade.
- `multiplicador_desgaste`: quanto a rota castiga a transportadora.
- `capacidade_maxima`: teto de carga que a rota suporta.
- `risco`: probabilidade de eventos adversos na rota.
- `condicao`: `livre` ou `interditada`.

Exemplo de resposta:

```json
[
  {
    "identificador": "rota-1",
    "origem": "setor-1",
    "destino": "central-distribuicao",
    "distancia": 10.0,
    "tempo_base": 5,
    "perfil": "padrao",
    "tipo": "fixa",
    "vantagem": "Equilibrada e previsivel",
    "desvantagem": "Nao se destaca em custo, desgaste nem preservacao",
    "custo_energia_base": 3.0,
    "multiplicador_degradacao": 1.0,
    "multiplicador_desgaste": 1.0,
    "capacidade_maxima": 100.0,
    "risco": 0.05,
    "condicao": "livre"
  },
  {
    "identificador": "rota-alt-1",
    "origem": "setor-1",
    "destino": "central-distribuicao",
    "distancia": 8.0,
    "tempo_base": 4,
    "perfil": "abrasiva",
    "tipo": "variante",
    "vantagem": "E curta e relativamente barata",
    "desvantagem": "Aumenta bastante a degradacao da carga",
    "custo_energia_base": 2.6,
    "multiplicador_degradacao": 1.7,
    "multiplicador_desgaste": 1.0,
    "capacidade_maxima": 110.0,
    "risco": 0.07,
    "condicao": "livre"
  }
]
```

### Perfis variantes de rota

Perfis disponiveis no catalogo (sorteados por seed):

| Perfil | Vantagem principal | Desvantagem principal | Custo energia | Mult. degradacao | Mult. desgaste | Capacidade |
| --- | --- | --- | --- | --- | --- | --- |
| `blindada` | Preserva qualidade | Mais energia, menos capacidade | 4.8 | 0.45 | 1.1 | 80 |
| `economica` | Baixo custo energetico | Degrada mais a carga | 2.0 | 1.35 | 0.9 | 100 |
| `turbo` | Chega mais rapido | Desgaste alto na transportadora | 4.2 | 0.75 | 1.8 | 90 |
| `pesada` | Alta capacidade | Mais energia e degradacao | 4.0 | 1.1 | 1.2 | 140 |
| `tecnica` | Minima degradacao | Castiga muito o robo | 4.5 | 0.55 | 2.2 | 70 |
| `abrasiva` | Curta e barata | Muita perda de qualidade | 2.6 | 1.7 | 1.0 | 110 |
| `panoramica` | Poupa o robo | Mais lenta | 3.2 | 0.85 | 0.8 | 100 |
| `corredor_frio` | Bom p/ material sensivel | Energia acima da media | 3.9 | 0.65 | 1.4 | 85 |
| `manutencao_leve` | Reduz desgaste | Viagem mais lenta | 3.4 | 1.1 | 0.55 | 95 |
| `expressa_fragil` | Muito rapida | Capacidade baixa, alta degradacao | 3.6 | 1.45 | 1.9 | 75 |

### `GET /transporte/transportadores`

Retorna apenas robos que possuem `viagens_disponiveis`.

Exemplo de resposta:

```json
[
  {
    "identificador": "transportadora-1",
    "estado": "disponivel",
    "localizacao": "patio"
  }
]
```

### `GET /transporte/cargas-disponiveis`

Retorna as cargas conhecidas pelo motor. O campo `qualidade` so aparece quando a carga ja foi analisada por outra etapa; caso contrario a resposta traz `null`.

Exemplo de resposta:

```json
[
  {
    "identificador": "carga-1",
    "mineral": "hematita",
    "quantidade": 10.0,
    "qualidade": null
  }
]
```

### `GET /transporte/planejar-transporte?identificador_da_carga=carga-1`

Retorna a carga consultada e as rotas com `condicao == "livre"`. Filtra automaticamente:

- rotas cuja `origem` e incompativel com a jazida de origem da carga, quando a carga esta em `EM_JAZIDA`;
- rotas cuja `capacidade_maxima` e menor que a quantidade da carga.

Exemplo de resposta:

```json
{
  "carga": "carga-1",
  "rotas_disponiveis": ["rota-1", "rota-alt-1"]
}
```

Se a carga nao existir, a API retorna `404 Carga nao encontrada`.

### `POST /transporte/carregar`

Payload:

```json
{
  "identificador_da_unidade": "transportadora-1",
  "identificador_da_carga": "carga-1"
}
```

Resposta imediata:

```json
{
  "aceito": true
}
```

Pre-condicoes executadas pelo comando:

- a unidade precisa existir, senao a API retorna `404 Unidade nao encontrada`;
- a unidade precisa estar em `disponivel`;
- a carga nao pode exceder a capacidade da unidade.

Efeito aplicado pelo comando:

- a unidade muda para `aguardando`.

### `POST /transporte/iniciar-viagem`

Payload:

```json
{
  "identificador_da_unidade": "transportadora-1",
  "identificador_da_rota": "rota-1",
  "identificador_da_carga": "carga-1",
  "id_autorizacao": "aut-123",
  "modo": "normal"
}
```

Resposta imediata:

```json
{
  "aceito": true
}
```

Pre-condicoes reais:

- a unidade precisa existir, senao a API retorna `404 Unidade ou rota nao encontrada`;
- a rota precisa existir, senao a API retorna `404 Unidade ou rota nao encontrada`;
- a carga precisa existir, senao a API retorna `404 Carga nao encontrada`;
- a central `transporte` precisa estar operante;
- a autorizacao precisa ser valida para `iniciar_viagem` e nao pode ter sido consumida antes;
- a rota precisa estar com `condicao == "livre"`;
- a unidade precisa ter `viagens_disponiveis > 0`;
- a carga nao pode estar em `EM_ARMAZEM` nem em `EM_TRANSITO`;
- a carga nao pode exceder a capacidade da unidade transportadora;
- a carga nao pode exceder a capacidade maxima da rota;
- se a carga estiver em `EM_JAZIDA`, a `origem` da rota precisa ser compativel com a `localizacao` da jazida de origem.

Efeitos aplicados pelo comando:

- consome a autorizacao;
- debita energia da central `transporte` usando `custo_energia_base` da rota;
- acumula desgaste na unidade considerando o `multiplicador_desgaste` da rota;
- decrementa `viagens_disponiveis` da unidade;
- move a unidade para `executando`;
- move a carga para `EM_TRANSITO` com degradacao que combina o modo e o `multiplicador_degradacao` da rota;
- agenda a conclusao da viagem para um ciclo futuro de acordo com o `tempo_base` da rota e o `modo`.

Quando a viagem conclui sem aborto:

- a carga volta para `NA_MAO`;
- a unidade muda para `retornando`;
- o mundo publica `transporte_concluido`.

Exemplo do evento publicado:

```json
{
  "tipo": "transporte_concluido",
  "dados": {
    "unidade": "transportadora-1",
    "carga": "carga-1",
    "modo": "normal",
    "desgaste_da_unidade": 0.5
  }
}
```

### `POST /transporte/abortar-viagem`

Payload:

```json
{
  "identificador_da_unidade": "transportadora-1"
}
```

Resposta imediata:

```json
{
  "aceito": true
}
```

Pre-condicao real:

- a unidade precisa existir, senao a API retorna `404 Unidade nao encontrada`.

Efeito aplicado pelo comando:

- a unidade muda para `retornando`.

Quando a conclusao agendada encontra a unidade fora de `executando`:

- a carga volta para o local de origem da viagem;
- o mundo publica `viagem_abortada`.

Exemplo do evento publicado:

```json
{
  "tipo": "viagem_abortada",
  "dados": {
    "unidade": "transportadora-1",
    "carga": "carga-1"
  }
}
```

### `POST /transporte/descarregar`

Payload:

```json
{
  "identificador_da_unidade": "transportadora-1",
  "identificador_da_carga": "carga-1"
}
```

Resposta imediata:

```json
{
  "aceito": true
}
```

Efeito aplicado pelo comando:

- publica `carga_disponivel` com o identificador da carga.

Exemplo do evento publicado:

```json
{
  "tipo": "carga_disponivel",
  "dados": {
    "carga": "carga-1"
  }
}
```

### `POST /transporte/retornar-unidade`

Payload:

```json
{
  "identificador_da_unidade": "transportadora-1"
}
```

Resposta imediata:

```json
{
  "aceito": true
}
```

Pre-condicao real:

- a unidade precisa existir, senao a API retorna `404 Unidade nao encontrada`.

Efeito aplicado pelo comando:

- a unidade muda para `disponivel`.

## Fluxo real de transporte

1. A extracao conclui uma operacao e publica `extracao_concluida` com uma carga nova em `EM_JAZIDA`.
2. Opcionalmente, a armazenagem retira a carga para `NA_MAO` e pode publicar `carga_disponivel` ao solicitar transporte.
3. A missao emite uma autorizacao para `iniciar_viagem`.
4. O transporte carrega a unidade, inicia a viagem e move a carga para `EM_TRANSITO`.
5. Se a viagem terminar normalmente, o mundo publica `transporte_concluido` e a carga volta para `NA_MAO`.
6. Se a viagem for abortada antes da chegada, o mundo publica `viagem_abortada` e devolve a carga ao local de origem.
7. Quando a central descarrega a carga, o mundo publica `carga_disponivel` para a etapa seguinte.

## Exemplos em Python com `requests`

### Emitir autorizacao na Missao e iniciar a viagem

```python
import requests

BASE_URL = "http://localhost:8000"

autorizacao = requests.post(f"{BASE_URL}/missao/autorizar-missao", json={
    "operacao": "iniciar_viagem",
    "central_solicitante": "transporte",
}).json()["id_autorizacao"]

resposta = requests.post(f"{BASE_URL}/transporte/iniciar-viagem", json={
    "identificador_da_unidade": "transportadora-1",
    "identificador_da_rota": "rota-1",
    "identificador_da_carga": "carga-1",
    "id_autorizacao": autorizacao,
    "modo": "normal",
})

print(resposta.json())
```

### Consultar rotas livres para uma carga

```python
import requests

BASE_URL = "http://localhost:8000"

resposta = requests.get(
    f"{BASE_URL}/transporte/planejar-transporte",
    params={"identificador_da_carga": "carga-1"},
)

print(resposta.json())
```

### Descarregar a carga e liberar a unidade

```python
import requests

BASE_URL = "http://localhost:8000"

requests.post(f"{BASE_URL}/transporte/descarregar", json={
    "identificador_da_unidade": "transportadora-1",
    "identificador_da_carga": "carga-1",
})

requests.post(f"{BASE_URL}/transporte/retornar-unidade", json={
    "identificador_da_unidade": "transportadora-1",
})
```
