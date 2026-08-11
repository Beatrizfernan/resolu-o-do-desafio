# Task 3 - Tipos de Mineradora na Extracao

## Escopo implementado

- Adicionado o atributo de dominio `tipo` em `UnidadeMineradora` com valor padrao `"leve"`.
- Diferenciadas as duas mineradoras iniciais da simulacao:
  - `mineradora-1`: `tipo="leve"`, `capacidade=35.0`
  - `mineradora-2`: `tipo="precisa"`, `capacidade=25.0`
- Exposto `tipo` no retorno de `GET /extracao/mineradoras`.

## TDD executado

### RED

- Teste adicionado em `mundo/testes/test_api_extracao.py`:

```python
def test_consultar_mineradoras_expoe_tipos_distintos():
    app = criar_app(com_loop_real_time=False)
    with TestClient(app) as cliente:
        tipos = {item["tipo"] for item in cliente.get("/extracao/mineradoras").json()}
        assert tipos == {"leve", "precisa"}
```

- Comando executado:

```bash
pytest mundo/testes/test_api_extracao.py::test_consultar_mineradoras_expoe_tipos_distintos -v
```

- Resultado observado: `FAILED` com `KeyError: 'tipo'`, confirmando que a API ainda nao expunha o campo requerido.

### GREEN

- Implementacao minima aplicada nos arquivos do brief:
  - `mundo/dominio/robos.py`
  - `mundo/motor/motor_de_simulacao.py`
  - `mundo/api/extracao.py`

- Comando executado:

```bash
pytest mundo/testes/test_api_extracao.py -v
```

- Resultado observado: `19 passed`.

## Self-review

- Dominio mantido em portugues; apenas os valores de `tipo` seguem os nomes definidos no brief (`leve` e `precisa`).
- Nenhuma formula de custo energetico foi alterada.
- Nenhuma regra de mutacao por ciclo foi alterada; apenas a configuracao inicial das mineradoras e a serializacao da API.
- Determinismo por seed preservado; nao houve mudanca em RNG nem em ordem de eventos do ciclo.
- Escopo mantido em Extracao; nenhuma mudanca em Armazenagem ou integracoes cruzadas.
- O arquivo `mundo/motor/motor_de_simulacao.py` ja possuia outras alteracoes locais no worktree antes desta task; a implementacao desta task ficou restrita ao trecho de inicializacao das mineradoras.

## Arquivos alterados

- `mundo/dominio/robos.py`
- `mundo/motor/motor_de_simulacao.py`
- `mundo/api/extracao.py`
- `mundo/testes/test_api_extracao.py`
- `.superpowers/sdd/task-3-report.md`

## Testes executados

```bash
pytest mundo/testes/test_api_extracao.py::test_consultar_mineradoras_expoe_tipos_distintos -v
pytest mundo/testes/test_api_extracao.py -v
```

## Observacoes

- Os comandos de pytest emitiram warnings preexistentes de configuracao (`asyncio_mode`) e deprecacao do `TestClient`/`httpx`; nao estao relacionados a esta task.
