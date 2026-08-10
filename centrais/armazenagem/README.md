# Central de Armazenagem

Guia tecnico da implementacao atual da Central de Armazenagem.

## Endpoints implementados

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `GET` | `/armazenagem/armazens` | Lista os armazens com capacidade, ocupacao, localizacao, condicoes e `pilha`. |
| `POST` | `/armazenagem/receber-carga` | Enfileira o recebimento de uma ou mais cargas em um armazem. |
| `POST` | `/armazenagem/retirar-carga` | Enfileira a retirada de uma carga e de tudo que estiver acima dela. |
| `POST` | `/armazenagem/descartar-carga` | Enfileira o descarte de uma carga que esteja na mao. |
| `POST` | `/armazenagem/solicitar-transporte` | Enfileira a publicacao de `carga_disponivel` para recolocar a carga no fluxo externo. |

## Semantica de execucao

- `GET /armazenagem/armazens` responde imediatamente com o estado atual.
- Todas as rotas `POST` retornam `{"aceito": true}` e enfileiram um comando.
- Validacoes executadas dentro do comando nao alteram o HTTP de aceite. Quando falham, a simulacao registra `operacao_invalida` no ciclo em que o comando roda.
- `GET /armazenagem/armazens` devolve `pilha` do fundo para o topo.

## Dependencias de autorizacao

Autorizacoes sao emitidas por `POST /missao/autorizar-missao` com o payload:

```json
{
  "operacao": "receber_carga",
  "central_solicitante": "armazenagem"
}
```

Cada autorizacao custa energia para a central de Missao e e consumida uma unica vez.

| Operacao | Exige `id_autorizacao` | Valor de `operacao` |
| --- | --- | --- |
| `POST /armazenagem/receber-carga` | Sim | `receber_carga` |
| `POST /armazenagem/retirar-carga` | Sim | `retirar_carga` |
| `POST /armazenagem/solicitar-transporte` | Sim | `solicitar_transporte` |
| `POST /armazenagem/descartar-carga` | Nao | - |
| `GET /armazenagem/armazens` | Nao | - |

## Contrato de pilha

- A pilha e posicional e o topo e o ultimo item da lista.
- Receber carga sem `nova_ordem` empilha as novas cargas no fim da lista, na ordem informada em `identificadores_das_cargas`.
- Receber carga com `nova_ordem` calcula deslocamentos sobre a pilha resultante e depois aplica a reordenacao.
- Retirar uma carga remove o alvo e todas as cargas acima dele. Todas elas passam para `NA_MAO`.
- Descartar nao remove carga do armazem diretamente: a carga precisa ja estar `NA_MAO`.
- Solicitar transporte nao muda o local da carga. A rota apenas publica `carga_disponivel`.

## Custos implementados hoje

Os valores atuais estao em `mundo/config/armazenagem.json`.

| Custo | Valor | Quando e cobrado |
| --- | --- | --- |
| `custo_de_armazenagem_por_unidade` | `0.05` | Em `receber-carga`, multiplicado pela quantidade total recebida. |
| `custo_por_movimento` | `0.3` | Em `receber-carga`, multiplicado pelos movimentos calculados por `nova_ordem`. |
| `custo_por_desempilhamento` | `0.8` | Em `retirar-carga`, multiplicado pela profundidade do alvo. Retirar o topo custa `0`. |
| `custo_de_manutencao_por_unidade` | `0.004` | A cada ciclo, para cada unidade armazenada. |

## Preconditions e validacoes reais

### `GET /armazenagem/armazens`

- Nao exige autorizacao.
- Retorna uma lista de objetos com `identificador`, `capacidade`, `ocupacao`, `localizacao`, `condicoes` e `pilha`.

Exemplo de resposta:

```json
[
  {
    "identificador": "armazem-1",
    "capacidade": 500.0,
    "ocupacao": 30.0,
    "localizacao": "setor-1",
    "condicoes": "normal",
    "pilha": ["carga-1", "carga-2"]
  }
]
```

### `POST /armazenagem/receber-carga`

Payload minimo:

```json
{
  "identificador_do_armazem": "armazem-1",
  "identificadores_das_cargas": ["carga-1"],
  "nova_ordem": ["carga-1"],
  "id_autorizacao": "aut-123"
}
```

Validacoes reais:

- o armazem informado precisa existir;
- todas as cargas informadas precisam existir;
- a central `armazenagem` precisa estar operante no momento da execucao;
- `id_autorizacao` precisa ser valido para `receber_carga`;
- o mesmo identificador nao pode se repetir no mesmo pedido;
- a carga nao pode ja estar na pilha do armazem;
- o volume total do pedido nao pode exceder a capacidade restante;
- cada carga precisa ser compativel com o armazem;
- se `nova_ordem` for enviada, ela precisa ser uma permutacao valida da pilha resultante;
- a central precisa ter energia para armazenamento e eventual reordenacao.

Exemplo com `requests`:

```python
import requests

BASE_URL = "http://localhost:8000"

autorizacao = requests.post(f"{BASE_URL}/missao/autorizar-missao", json={
    "operacao": "receber_carga",
    "central_solicitante": "armazenagem",
}).json()["id_autorizacao"]

requests.post(f"{BASE_URL}/armazenagem/receber-carga", json={
    "identificador_do_armazem": "armazem-1",
    "identificadores_das_cargas": ["carga-1"],
    "nova_ordem": ["carga-1"],
    "id_autorizacao": autorizacao,
})
```

### `POST /armazenagem/retirar-carga`

Payload:

```json
{
  "identificador_do_armazem": "armazem-1",
  "identificador_da_carga": "carga-1",
  "id_autorizacao": "aut-456"
}
```

Validacoes reais:

- o armazem informado precisa existir;
- a carga informada precisa existir;
- a central `armazenagem` precisa estar operante no momento da execucao;
- `id_autorizacao` precisa ser valido para `retirar_carga`;
- a carga alvo precisa estar na pilha do armazem;
- a central precisa ter energia para o custo de desempilhamento, quando houver.

Exemplo com `requests`:

```python
import requests

BASE_URL = "http://localhost:8000"

autorizacao = requests.post(f"{BASE_URL}/missao/autorizar-missao", json={
    "operacao": "retirar_carga",
    "central_solicitante": "armazenagem",
}).json()["id_autorizacao"]

requests.post(f"{BASE_URL}/armazenagem/retirar-carga", json={
    "identificador_do_armazem": "armazem-1",
    "identificador_da_carga": "carga-1",
    "id_autorizacao": autorizacao,
})
```

### `POST /armazenagem/descartar-carga`

Payload:

```json
{
  "identificador_da_carga": "carga-1"
}
```

Validacoes reais:

- a carga informada precisa existir;
- a carga precisa estar `NA_MAO` no momento da execucao.

### `POST /armazenagem/solicitar-transporte`

Payload:

```json
{
  "identificador_da_carga": "carga-1",
  "id_autorizacao": "aut-789"
}
```

Validacoes reais:

- a carga informada precisa existir;
- `id_autorizacao` precisa ser valido para `solicitar_transporte`.

Exemplo com `requests`:

```python
import requests

BASE_URL = "http://localhost:8000"

autorizacao = requests.post(f"{BASE_URL}/missao/autorizar-missao", json={
    "operacao": "solicitar_transporte",
    "central_solicitante": "armazenagem",
}).json()["id_autorizacao"]

requests.post(f"{BASE_URL}/armazenagem/solicitar-transporte", json={
    "identificador_da_carga": "carga-1",
    "id_autorizacao": autorizacao,
})
```

## Eventos publicados pela central

### `cargas_armazenadas`

Publicado por `receber-carga` quando a operacao conclui.

```json
{
  "armazem": "armazem-1",
  "cargas": ["carga-1"],
  "movimentos": 0,
  "custo": 1.0
}
```

### `armazem_lotado`

Publicado por `receber-carga` quando a ocupacao chega a `capacidade`.

```json
{
  "armazem": "armazem-1"
}
```

### `armazem_proximo_da_capacidade`

Publicado por `receber-carga` quando a ocupacao fica maior ou igual a `90%` da capacidade, sem lotar.

```json
{
  "armazem": "armazem-1"
}
```

### `carga_contaminada`

Publicado por `receber-carga` antes de rejeitar mineral incompativel.

```json
{
  "carga": "carga-1",
  "armazem": "armazem-1"
}
```

### `cargas_desempilhadas`

Publicado por `retirar-carga` quando o alvo e tudo que estiver acima dele saem da pilha.

```json
{
  "armazem": "armazem-1",
  "alvo": "carga-1",
  "cargas": ["carga-2", "carga-1"],
  "profundidade": 1,
  "custo": 0.8
}
```

### `carga_descartada`

Publicado por `descartar-carga` quando a carga e removida de `motor.cargas`.

```json
{
  "carga": "carga-1"
}
```

### `carga_disponivel`

Publicado por `solicitar-transporte`.

```json
{
  "carga": "carga-1"
}
```
