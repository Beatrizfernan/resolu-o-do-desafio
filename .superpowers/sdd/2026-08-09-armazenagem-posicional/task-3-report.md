# Task 3 — Storage Cost Catalog — DONE

Commit: `d766ca3`

Result: `.venv/bin/pytest mundo/testes -q` → **213 passed** (211 baseline + 2 new).

---

## Implementation

Three files created:

### 1. `CatalogoDeArmazenagem` class

File: `mundo/dominio/armazenagem.py`

Frozen dataclass with four priced operations:
- `custo_de_armazenagem_por_unidade` (storing cost per unit)
- `custo_de_manutencao_por_unidade` (holding cost per unit)
- `custo_por_movimento` (reordering cost per item moved)
- `custo_por_desempilhamento` (unstacking cost per item)

Implements the established pattern: `carregar_de_arquivo(caminho: Path)` classmethod that reads JSON and returns an instance.

### 2. Configuration file

File: `mundo/config/armazenagem.json`

```json
{
  "custo_de_armazenagem_por_unidade": 0.05,
  "custo_de_manutencao_por_unidade": 0.004,
  "custo_por_movimento": 0.3,
  "custo_por_desempilhamento": 0.8
}
```

**Rationale**: Volume pays to keep; item count pays to shuffle. Asymmetry is deliberate — it makes stack order matter without any rule mandating sort. Storing 20 units costs exactly 1.0 (same as the old fixed fee), so the simple case does not get more expensive.

### 3. Test suite

File: `mundo/testes/test_catalogo_de_armazenagem.py`

Two tests:
- `test_carrega_os_quatro_custos_do_arquivo` — verifies all four costs load correctly from the config file
- `test_guardar_vinte_unidades_custa_o_mesmo_que_a_taxa_fixa_antiga` — backward compatibility check; storing 20 units costs exactly 1.0

Both pass. No existing tests broken.

---

## Checklist

- [x] Three files created with correct content (class, config, tests)
- [x] Follows `CatalogoDeModos` pattern (frozen dataclass + carregar_de_arquivo)
- [x] Portuguese domain language (class names, field names, docstrings)
- [x] English commit message matching repo style
- [x] Config values match test expectations exactly
- [x] Full test suite runs: 213 passed
- [x] No existing assertions weakened
- [x] Ready for engine and API integration (next tasks)
