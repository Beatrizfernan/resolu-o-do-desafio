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

Retorna todas as rotas cadastradas.

Exemplo de resposta:

```json
[
  {
    "identificador": "rota-1",
    "origem": "jazida-1",
    "destino": "base-1",
    "distancia": 10,
    "condicao": "livre"
  }
]
```

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

Retorna a carga consultada e as rotas com `condicao == "livre"`.

Exemplo de resposta:

```json
{
  "carga": "carga-1",
  "rotas_disponiveis": ["rota-1"]
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
- a autorizacao precisa existir, ser compativel com `iniciar_viagem` e nao pode ter sido consumida antes;
- a rota precisa estar com `condicao == "livre"`;
- a unidade precisa ter `viagens_disponiveis > 0`;
- a carga nao pode estar em `EM_ARMAZEM` nem em `EM_TRANSITO`.

Efeitos aplicados pelo comando:

- consome a autorizacao;
- debita energia da central `transporte`;
- decrementa `viagens_disponiveis` da unidade;
- move a unidade para `executando`;
- move a carga para `EM_TRANSITO`;
- agenda a conclusao da viagem para um ciclo futuro de acordo com a rota e o `modo`.

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
