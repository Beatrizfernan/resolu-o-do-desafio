# Central de Pesquisa

Guia tecnico da implementacao atual da central de Pesquisa.

## Endpoints implementados

- `GET /pesquisa/em-andamento`
- `GET /pesquisa/fila`
- `POST /pesquisa/iniciar-analise`
- `POST /pesquisa/sondar-jazida`
- `GET /pesquisa/jazidas/{identificador}/estimativa`
- `POST /pesquisa/classificar-carga`
- `POST /pesquisa/aprovar-carga`
- `POST /pesquisa/rejeitar-carga`
- `POST /pesquisa/preparar-distribuicao`

`GET /pesquisa/em-andamento` e `GET /pesquisa/fila` retornam a mesma lista `analises_em_andamento`.

## Capacidade e dependencia de energia

- Pesquisa depende de energia alocada pela Missao.
- A central usa a configuracao atual `capacidade_paralela = 1`.
- Analise e sondagem competem pela mesma capacidade da central.
- Quando o unico slot esta ocupado, novas requisicoes de analise ou sondagem entram na fila de comandos, mas a execucao publica `operacao_invalida` com motivo de central ocupada.

## Contratos atuais

### `POST /pesquisa/iniciar-analise`

Pre-condicoes implementadas:

- a carga precisa existir;
- a central `pesquisa` precisa estar operante;
- precisa haver slot livre na capacidade compartilhada;
- a energia debitada depende de `custo_base_de_analise * mineral.custo_extracao * ajuste_do_tipo`.

Suporta **tipos de analise**:

- `rapida`: metade da duracao, 80% do custo. Libera caixa antes, mas nao altera a qualidade.
- `completa`: padrao, duracao e custo normais.
- `forense`: 50% mais longa, 140% do custo. Pode justificar-se em minerais raros.

Comportamento implementado:

- a carga entra em `analises_em_andamento`;
- a duracao depende de `mineral.ciclos_de_analise` e do `tipo_de_analise`;
- ao concluir, a carga fica com `analisada = True`;
- ao concluir, a central publica `analise_concluida`.

Payload de requisicao:

```json
{
  "identificador_da_carga": "carga-1",
  "tipo_de_analise": "rapida"
}
```

### `POST /pesquisa/sondar-jazida`

Pre-condicoes implementadas:

- a jazida precisa existir;
- a central `pesquisa` precisa estar operante;
- precisa haver slot livre na mesma capacidade compartilhada de analise;
- a jazida nao pode ter sido sondada antes.

Comportamento implementado:

- a energia debitada e `custo_base_de_analise`;
- a jazida entra em `analises_em_andamento` com o identificador `jazida:<id>`;
- a sondagem conclui em 2 ciclos;
- a estimativa de composicao e persistida em `jazida.composicao_estimada`;
- ao concluir, a central publica `sondagem_de_jazida_concluida`.

Payload de requisicao:

```json
{
  "identificador_da_jazida": "jazida-1"
}
```

### `GET /pesquisa/jazidas/{identificador}/estimativa`

Comportamento implementado:

- retorna `404` se a jazida nao existir;
- retorna `404` se a jazida existir, mas ainda nao tiver sido sondada;
- retorna `jazida`, `mineral_predominante` e `estimativa_de_composicao` quando a sondagem ja concluiu.

### `POST /pesquisa/classificar-carga`

Comportamento implementado:

- retorna `404` se a carga nao existir;
- `classificar-carga` so expoe qualidade quando a carga ja foi analisada;
- antes da analise concluir, o campo `qualidade` retorna `null`.

Payload de requisicao:

```json
{
  "identificador_da_carga": "carga-1"
}
```

### `POST /pesquisa/aprovar-carga`

Pre-condicoes implementadas:

- a carga precisa existir no momento da execucao do comando;
- a carga precisa ter sido analisada;
- a qualidade precisa ser maior ou igual ao limiar da politica escolhida.

Suporta **politicas de aprovacao**:

- `comercial` (limiar `40.0`, padrao): aprova material com qualidade moderada.
- `estrita` (limiar `70.0`): barra material degradado que passaria na comercial.
- `premium` (limiar `85.0`): so aprova lotes de altissima qualidade.

Payload de requisicao:

```json
{
  "identificador_da_carga": "carga-1",
  "politica": "estrita"
}
```

Comportamento implementado:

- quando as pre-condicoes sao atendidas, a carga fica com `aprovada = True` e a central publica `carga_aprovada`.
- quando a qualidade e insuficiente para a politica, publica `operacao_invalida`.

### `POST /pesquisa/rejeitar-carga`

Pre-condicoes implementadas:

- a carga precisa existir no momento da execucao do comando;
- a carga precisa ter sido analisada.

Comportamento implementado:

- quando as pre-condicoes sao atendidas, a central publica `carga_rejeitada`.

### `POST /pesquisa/preparar-distribuicao`

Pre-condicoes implementadas:

- `preparar-distribuicao` depende de autorizacao da Missao;
- a autorizacao precisa ser valida, nao reutilizada e emitida para a operacao `preparar_distribuicao`;
- a carga precisa existir no momento da execucao do comando;
- a carga precisa ter sido analisada;
- a carga precisa ter sido aprovada (`POST /pesquisa/aprovar-carga` executado com sucesso);
- a carga nao pode estar `EM_ARMAZEM` nem `EM_TRANSITO`.

Comportamento implementado:

- o valor entregue e somado em `faturamento_total`;
- a central publica `carga_entregue` com o valor entregue;
- distribuicao remove a carga do mundo apos `carga_entregue`.

Payload de requisicao:

```json
{
  "identificador_da_carga": "carga-1",
  "id_autorizacao": "aut-789"
}
```

## Eventos publicados

Eventos reais publicados pela central:

- `analise_concluida`
- `sondagem_de_jazida_concluida`
- `carga_aprovada`
- `carga_rejeitada`
- `carga_entregue`

Relacao entre operacao e evento:

- `POST /pesquisa/iniciar-analise` publica `analise_concluida` quando a analise termina;
- `POST /pesquisa/sondar-jazida` publica `sondagem_de_jazida_concluida` quando a sondagem termina;
- `POST /pesquisa/aprovar-carga` publica `carga_aprovada` quando a carga analisada atende ao limiar;
- `POST /pesquisa/rejeitar-carga` publica `carga_rejeitada` quando a carga analisada e rejeitada;
- `POST /pesquisa/preparar-distribuicao` publica `carga_entregue` antes de remover a carga do mundo.

Envelope observado por `GET /missao/eventos` e por webhook:

```json
{
  "identificador": "evt-21",
  "tipo": "analise_concluida",
  "ciclo": 12,
  "dados": {
    "carga": "carga-1"
  }
}
```

```json
{
  "identificador": "evt-22",
  "tipo": "sondagem_de_jazida_concluida",
  "ciclo": 15,
  "dados": {
    "jazida": "jazida-1",
    "estimativa_de_composicao": {
      "hematita": "alta"
    }
  }
}
```

```json
{
  "identificador": "evt-23",
  "tipo": "carga_aprovada",
  "ciclo": 16,
  "dados": {
    "carga": "carga-1"
  }
}
```

```json
{
  "identificador": "evt-24",
  "tipo": "carga_rejeitada",
  "ciclo": 16,
  "dados": {
    "carga": "carga-1"
  }
}
```

```json
{
  "identificador": "evt-25",
  "tipo": "carga_entregue",
  "ciclo": 18,
  "dados": {
    "carga": "carga-1",
    "valor_entregue": 50.0
  }
}
```

## Exemplo em Python com `requests`

```python
import requests

BASE_URL = "http://localhost:8000"

resposta = requests.post(f"{BASE_URL}/pesquisa/iniciar-analise", json={
    "identificador_da_carga": "carga-1",
})

print(resposta.json())
```

Depois que a carga aparecer como analisada em `POST /pesquisa/classificar-carga` ou depois de observar `analise_concluida`, a distribuicao pode ser preparada:

```python
import requests

BASE_URL = "http://localhost:8000"

autorizacao = requests.post(f"{BASE_URL}/missao/autorizar-missao", json={
    "operacao": "preparar_distribuicao",
    "central_solicitante": "pesquisa",
}).json()["id_autorizacao"]

resposta = requests.post(f"{BASE_URL}/pesquisa/preparar-distribuicao", json={
    "identificador_da_carga": "carga-1",
    "id_autorizacao": autorizacao,
})

print(resposta.json())
```
