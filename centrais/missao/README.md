# Central de Missao

## Visao geral

A Central de Missao expoe a visao global do mundo e os controles centrais de energia e autorizacao. Hoje ela faz seis coisas:

- reinicia a simulacao com uma nova semente;
- consulta o estado global do mundo;
- lista eventos publicados pelas outras centrais;
- transfere energia da `reserva_estrategica` para uma central;
- emite IDs de autorizacao para operacoes protegidas;
- registra webhooks para receber cada evento publicado pelo barramento.

## Dependencias desta central

As outras centrais dependem desta central de tres formas implementadas hoje:

- energia: `POST /missao/alocar-energia` move saldo da `reserva_estrategica` para `extracao`, `armazenagem`, `transporte`, `pesquisa` ou `missao`;
- autorizacao: operacoes como `iniciar_viagem`, `retirar_carga`, `solicitar_transporte` e `preparar_distribuicao` consomem IDs emitidos por `POST /missao/autorizar-missao`;
- observabilidade global: `GET /missao/eventos` e `POST /missao/registrar-webhook` entregam os eventos produzidos pelas demais centrais.

## O que esta central consegue fazer hoje

- Consultar `ciclo_atual`, saldo de energia por central e `faturamento_total`.
- Consultar eventos a partir de um ciclo com `desde_ciclo`.
- Aceitar uma alocacao de energia de forma assincrona com resposta `{"aceito": true}`.
- Emitir um `id_autorizacao` de forma sincrona.
- Registrar a mesma URL de webhook mais de uma vez sem duplicar o cadastro.
- Entregar webhooks por `POST` com timeout de 2 segundos por tentativa.

## O que esta central nao consegue fazer hoje

- Nao remove webhooks registrados.
- Nao lista webhooks registrados.
- Nao filtra eventos por tipo no cadastro de webhook.
- Nao reenvia webhooks com politica de retry exposta por API.
- Nao executa extracao, transporte, armazenagem ou pesquisa diretamente.
- Nao aplica a alocacao de energia na mesma resposta HTTP: a mutacao acontece no tick seguinte.

## Endpoints disponiveis

### `POST /missao/resetar-mundo`

Reinicia a simulacao e retorna o ciclo em zero.

Request JSON:

```json
{
  "semente": 7,
  "duracao_maxima": 100
}
```

Response JSON:

```json
{
  "ciclo_atual": 0
}
```

### `GET /missao/estado`

Retorna o estado global atual.

Response JSON de exemplo:

```json
{
  "ciclo_atual": 0,
  "energia": {
    "extracao": 10.0,
    "armazenagem": 10.0,
    "transporte": 10.0,
    "pesquisa": 10.0,
    "missao": 10.0,
    "reserva_estrategica": 950.0
  },
  "faturamento_total": 0.0
}
```

### `GET /missao/eventos?desde_ciclo=0`

Retorna a lista de eventos publicados a partir do ciclo informado.

Response JSON de exemplo:

```json
[
  {
    "identificador": "evt-1",
    "tipo": "carga_disponivel",
    "ciclo": 3,
    "dados": {
      "carga": "carga-1"
    }
  }
]
```

### `POST /missao/alocar-energia`

Aceita uma transferencia de energia da `reserva_estrategica` para outra central. A alteracao de saldo entra no tick seguinte.

Suporta **politicas de repasse**:

- `pulso` (padrao): transfere exatamente a quantidade pedida.
- `contingencia`: mantem um colchao minimo de `5.0` na Missao. Se o repasse pedido esgotaria esse colchao, a quantidade e reduzida automaticamente. Nao se aplica quando o destino e a propria `missao` — repor a si mesma nunca e limitado.

Request JSON:

```json
{
  "destino": "transporte",
  "quantidade": 50,
  "politica": "contingencia"
}
```

Response JSON:

```json
{
  "aceito": true
}
```

### `POST /missao/autorizar-missao`

Emite um identificador de autorizacao para a operacao e central solicitante. Agora suporta **classes de autorizacao** com custos distintos.

Campos aceitos:

- `operacao`: nome da operacao que consumira a autorizacao (ex: `iniciar_viagem`, `receber_carga`).
- `central_solicitante`: central que usara a autorizacao (ex: `transporte`, `armazenagem`).
- `classe`: `rapida` (custo `0.2`, padrao), `segura` (custo `0.5`) ou `lote` (custo `0.8`).

Request JSON:

```json
{
  "operacao": "iniciar_viagem",
  "central_solicitante": "transporte",
  "classe": "segura"
}
```

Response JSON:

```json
{
  "id_autorizacao": "aut-1"
}
```

Erros atuais:

- `400` quando a Central de Missao esta dormente;
- `400` quando nao ha energia suficiente para pagar o custo da classe de autorizacao;
- `422` quando `classe` nao e um valor valido.

### `POST /missao/registrar-webhook`

Registra uma URL para receber todos os eventos publicados no barramento global.

Request JSON:

```json
{
  "url": "http://localhost:9000/webhooks/eventos"
}
```

Response JSON:

```json
{
  "registrado": true
}
```

## Eventos para escutar

`GET /missao/eventos` e os webhooks registrados entregam o mesmo formato de payload:

```json
{
  "identificador": "evt-7",
  "tipo": "extracao_concluida",
  "ciclo": 12,
  "dados": {
    "unidade": "mineradora-1",
    "jazida": "jazida-1",
    "quantidade": 40,
    "quantidade_consumida_da_jazida": 44.0,
    "modo": "preciso",
    "carga": "carga-jazida-1-mineradora-1-12",
    "desgaste_da_unidade": 0.4
  }
}
```

Tipos de evento implementados hoje e observaveis por esta central incluem:

- `extracao_concluida`
- `extracao_interrompida`
- `cargas_armazenadas`
- `cargas_desempilhadas`
- `carga_disponivel`
- `carga_descartada`
- `carga_contaminada`
- `armazem_lotado`
- `armazem_proximo_da_capacidade`
- `transporte_concluido`
- `viagem_abortada`
- `analise_concluida`
- `sondagem_de_jazida_concluida`
- `carga_aprovada`
- `carga_rejeitada`
- `carga_entregue`

O conteudo de `dados` varia conforme o `tipo` do evento.

## Como escutar eventos em Python

Exemplo de listener HTTP compativel com `POST /missao/registrar-webhook`:

```python
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", "0"))
        corpo = self.rfile.read(tamanho)
        evento = json.loads(corpo.decode("utf-8"))

        print("Evento recebido:")
        print(json.dumps(evento, indent=2, ensure_ascii=False))

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")


servidor = HTTPServer(("0.0.0.0", 9000), WebhookHandler)
servidor.serve_forever()
```

Depois registre a URL do listener:

```python
import requests

BASE_URL = "http://localhost:8000"

resposta = requests.post(
    f"{BASE_URL}/missao/registrar-webhook",
    json={"url": "http://localhost:9000/webhooks/eventos"},
)

print(resposta.json())
```

O dispatcher envia um `POST` para cada URL registrada com timeout de 2 segundos e nao exige cabecalho especifico alem do JSON do corpo.

## Exemplos de chamadas em Python

```python
import requests

BASE_URL = "http://localhost:8000"

requests.post(
    f"{BASE_URL}/missao/alocar-energia",
    json={
        "destino": "transporte",
        "quantidade": 50,
    },
)

resposta = requests.post(
    f"{BASE_URL}/missao/autorizar-missao",
    json={
        "operacao": "iniciar_viagem",
        "central_solicitante": "transporte",
    },
)

print(resposta.json())
```

Consultar estado global:

```python
import requests

BASE_URL = "http://localhost:8000"

resposta = requests.get(f"{BASE_URL}/missao/estado")
print(resposta.json())
```

Consultar eventos desde um ciclo:

```python
import requests

BASE_URL = "http://localhost:8000"

resposta = requests.get(f"{BASE_URL}/missao/eventos", params={"desde_ciclo": 10})
print(resposta.json())
```

Resetar o mundo:

```python
import requests

BASE_URL = "http://localhost:8000"

resposta = requests.post(
    f"{BASE_URL}/missao/resetar-mundo",
    json={"semente": 7, "duracao_maxima": 100},
)

print(resposta.json())
```

## Fluxos comuns envolvendo esta central

### Liberar uma viagem de transporte

1. Opcionalmente, chamar `POST /missao/alocar-energia` para transferir saldo da `reserva_estrategica` para `transporte`.
2. Chamar `POST /missao/autorizar-missao` com `operacao: "iniciar_viagem"` e `central_solicitante: "transporte"`.
3. Entregar o `id_autorizacao` retornado para `POST /transporte/iniciar-viagem`.
4. Observar `transporte_concluido` ou `viagem_abortada` por `GET /missao/eventos` ou webhook.

### Liberar retirada ou distribuicao de carga

1. Chamar `POST /missao/autorizar-missao` para `retirar_carga`, `solicitar_transporte` ou `preparar_distribuicao`.
2. Repassar o `id_autorizacao` para a central solicitante.
3. Acompanhar `cargas_desempilhadas`, `carga_disponivel` e `carga_entregue` pelos canais de evento.

### Monitorar o mundo em tempo real

1. Consultar `GET /missao/estado` para energia e faturamento.
2. Registrar uma URL em `POST /missao/registrar-webhook` para receber eventos sem polling.
3. Usar `GET /missao/eventos?desde_ciclo=N` para recuperar historico a partir de um ciclo conhecido.

## Custos, limites e pressao do mundo

- Cada central comeca com `10.0` de energia.
- A `reserva_estrategica` comeca com `950.0` de energia.
- Cada central consome `0.05` de energia por ciclo enquanto estiver operante.
- Cada autorizacao emitida por `POST /missao/autorizar-missao` custa `0.2` de energia da central `missao`.
- Uma central sem saldo fica dormente e deixa de operar.
- Se a central `missao` ficar dormente, ela deixa de autorizar e de alocar energia para as outras centrais.
