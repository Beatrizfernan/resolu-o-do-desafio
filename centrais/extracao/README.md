# Central de Extracao

Esta central consulta jazidas e agenda operacoes de extracao por unidade mineradora.

## Dependencias desta central

- depende de energia previamente alocada pela Missao;
- gera cargas que depois pressionam Transporte, Armazenagem e Pesquisa;
- nao revela qualidade final da carga;
- conclui operacoes por evento futuro, nao na resposta HTTP.

## Endpoints implementados hoje

- `GET /extracao/jazidas`
- `GET /extracao/jazidas/{identificador}`
- `GET /extracao/mineradoras`
- `POST /extracao/iniciar-extracao`
- `POST /extracao/interromper-extracao`
- `POST /extracao/retornar-unidade`

## Consultar mineradoras

`GET /extracao/mineradoras`

Retorna as unidades mineradoras com tipo, estado, localizacao, desgaste e capacidade.

Response JSON:

```json
[
  {
    "identificador": "mineradora-1",
    "estado": "disponivel",
    "localizacao": "base",
    "desgaste": 0.0,
    "capacidade": 35.0,
    "tipo": "leve"
  },
  {
    "identificador": "mineradora-2",
    "estado": "disponivel",
    "localizacao": "base",
    "desgaste": 0.0,
    "capacidade": 25.0,
    "tipo": "precisa"
  }
]
```

Python com `requests`:

```python
import requests

BASE_URL = "http://localhost:8000"

resposta = requests.get(f"{BASE_URL}/extracao/mineradoras")
resposta.raise_for_status()
print(resposta.json())
```

### Tipos de mineradora

O mundo dispoe de dois tipos de mineradora com caracteristicas distintas:

- `leve` (`mineradora-1`): rapida, barata, capacidade `35.0`. Ideal para throughput.
- `precisa` (`mineradora-2`): mais lenta, preserva mais qualidade inicial, capacidade `25.0`. Ideal para minerais valiosos.

Casar o tipo de mineradora com a jazida e o mineral e uma decisao economica real.

## Consultar jazidas

`GET /extracao/jazidas`

Response JSON:

```json
[
  {
    "identificador": "jazida-1",
    "mineral": "hematita",
    "estado": "disponivel",
    "quantidade_disponivel": 120.0
  }
]
```

Python com `requests`:

```python
import requests

BASE_URL = "http://localhost:8000"

resposta = requests.get(f"{BASE_URL}/extracao/jazidas")
resposta.raise_for_status()
print(resposta.json())
```

## Inspecionar uma jazida

`GET /extracao/jazidas/{identificador}`

Response JSON:

```json
{
  "identificador": "jazida-1",
  "localizacao": "setor-1",
  "mineral": "hematita",
  "quantidade_disponivel": 120.0,
  "dificuldade_extracao": 1.0,
  "risco": 0.2,
  "estado": "disponivel"
}
```

Python com `requests`:

```python
import requests

BASE_URL = "http://localhost:8000"

resposta = requests.get(f"{BASE_URL}/extracao/jazidas/jazida-1")
resposta.raise_for_status()
print(resposta.json())
```

Se a jazida nao existir, a API responde `404` com `{"detail": "Jazida não encontrada"}`.

## Iniciar extracao

`POST /extracao/iniciar-extracao`

Request JSON:

```json
{
  "identificador_da_unidade": "mineradora-1",
  "identificador_da_jazida": "jazida-1",
  "quantidade": 20,
  "modo": "normal"
}
```

Campos aceitos:

- `identificador_da_unidade`: unidade mineradora usada na operacao.
- `identificador_da_jazida`: jazida consumida pela operacao.
- `quantidade`: quantidade solicitada para a carga. Nao pode exceder a capacidade da mineradora.
- `modo`: `cuidadoso`, `normal` ou `agressivo`. Quando omitido, o default e `normal`.
- `perfil_de_escavacao`: `superficial` (padrao), `profunda` (+25% energia, +4 de qualidade inicial) ou `mapeadora` (+10% energia, +2 de qualidade inicial).

Response JSON imediata:

```json
{
  "aceito": true
}
```

Python com `requests`:

```python
import requests

BASE_URL = "http://localhost:8000"

resposta = requests.post(f"{BASE_URL}/extracao/iniciar-extracao", json={
    "identificador_da_unidade": "mineradora-1",
    "identificador_da_jazida": "jazida-1",
    "quantidade": 20,
    "modo": "normal",
})
resposta.raise_for_status()
print(resposta.json())
```

O `200` com `{"aceito": true}` significa apenas que o comando foi enfileirado. A operacao real depende de energia disponivel para a central e e concluida em ciclo futuro.

Validacoes implementadas durante a execucao do comando:

- a central precisa estar operante na energia;
- a unidade precisa estar `disponivel`;
- a jazida precisa estar `disponivel`;
- a quantidade nao pode exceder a capacidade da unidade;
- o consumo previsto da jazida precisa caber no saldo atual.

Request JSON de exemplo com todos os campos:

```json
{
  "identificador_da_unidade": "mineradora-1",
  "identificador_da_jazida": "jazida-1",
  "quantidade": 20,
  "modo": "normal",
  "perfil_de_escavacao": "profunda"
}
```

Se a unidade ou a jazida nao existirem, a API responde `404` com `{"detail": "Unidade ou jazida não encontrada"}`.

## Interromper extracao

`POST /extracao/interromper-extracao`

Request JSON:

```json
{
  "identificador_da_unidade": "mineradora-1"
}
```

Response JSON:

```json
{
  "aceito": true
}
```

Python com `requests`:

```python
import requests

BASE_URL = "http://localhost:8000"

resposta = requests.post(f"{BASE_URL}/extracao/interromper-extracao", json={
    "identificador_da_unidade": "mineradora-1"
})
resposta.raise_for_status()
print(resposta.json())
```

No ciclo em que o comando for processado, a unidade passa para `retornando`. Quando a conclusao agendada da extracao acontecer, o motor publica `extracao_interrompida` em vez de criar carga.

Se a unidade nao existir, a API responde `404` com `{"detail": "Unidade não encontrada"}`.

## Retornar unidade

`POST /extracao/retornar-unidade`

Request JSON:

```json
{
  "identificador_da_unidade": "mineradora-1"
}
```

Response JSON:

```json
{
  "aceito": true
}
```

Python com `requests`:

```python
import requests

BASE_URL = "http://localhost:8000"

resposta = requests.post(f"{BASE_URL}/extracao/retornar-unidade", json={
    "identificador_da_unidade": "mineradora-1"
})
resposta.raise_for_status()
print(resposta.json())
```

No ciclo em que o comando for processado, a unidade passa para `disponivel`.

## Conclusao assincrona

A extracao nao termina na resposta HTTP. O fluxo implementado hoje e:

1. `POST /extracao/iniciar-extracao` enfileira o comando e responde `{"aceito": true}`.
2. No ciclo em que o comando e processado, a energia e debitada e a unidade passa para `executando`.
3. A conclusao e agendada para um ciclo futuro com base na duracao do modo.
4. Na conclusao, o motor publica um evento.

Efeitos de conclusao implementados hoje:

- se a unidade ainda estiver `executando`, a jazida e consumida, a unidade vai para `aguardando` e uma carga e criada em `em_jazida`;
- se a unidade nao estiver mais `executando`, nenhuma carga e criada e o evento publicado e `extracao_interrompida`.

## Eventos e webhooks

Os eventos desta central seguem o envelope padrao do mundo com `identificador`, `tipo`, `ciclo` e `dados`. Eles podem ser observados por polling em Missao e tambem pelos webhooks registrados na central de Missao.

### Evento `extracao_concluida`

Payload:

```json
{
  "identificador": "evt-123",
  "tipo": "extracao_concluida",
  "ciclo": 12,
  "dados": {
    "unidade": "mineradora-1",
    "jazida": "jazida-1",
    "quantidade": 20,
    "quantidade_consumida_da_jazida": 20,
    "modo": "normal",
    "carga": "carga-jazida-1-mineradora-1-12",
    "desgaste_da_unidade": 1.0
  }
}
```

Campos relevantes em `dados`:

- `quantidade`: quantidade entregue na carga criada.
- `quantidade_consumida_da_jazida`: quanto a jazida perdeu de fato, considerando o desperdicio do modo.
- `carga`: identificador da carga criada para Transporte, Armazenagem e Pesquisa.
- `desgaste_da_unidade`: desgaste acumulado da unidade apos a operacao.

### Evento `extracao_interrompida`

Payload:

```json
{
  "identificador": "evt-124",
  "tipo": "extracao_interrompida",
  "ciclo": 12,
  "dados": {
    "unidade": "mineradora-1",
    "jazida": "jazida-1"
  }
}
```

Esse evento indica que a conclusao agendada chegou, mas a unidade ja nao estava em `executando`.
