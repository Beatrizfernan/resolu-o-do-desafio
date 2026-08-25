from __future__ import annotations

from .modelos import ModoTransporte, PerfilMineral


MINERAIS: dict[str, PerfilMineral] = {
    "hematita": PerfilMineral("hematita", 5.0, 0.10, 0.20, 0.10, 4, ("economico", "normal"), (0.50, 0.10, 0.15, 0.15, 0.10)),
    "silica_de_alta_pureza": PerfilMineral("silica_de_alta_pureza", 20.0, 0.30, 0.40, 0.30, 3, ("normal",), (0.35, 0.25, 0.15, 0.15, 0.10)),
    "jarosita": PerfilMineral("jarosita", 35.0, 0.60, 0.70, 0.60, 2, ("rapido", "normal"), (0.15, 0.35, 0.25, 0.10, 0.15)),
    "gelo_de_agua": PerfilMineral("gelo_de_agua", 40.0, 0.50, 0.90, 0.50, 1, ("rapido",), (0.10, 0.40, 0.25, 0.10, 0.15)),
    "cristal_marciano_raro": PerfilMineral("cristal_marciano_raro", 200.0, 0.95, 0.30, 0.40, 0, ("rapido",), (0.05, 0.40, 0.30, 0.05, 0.20)),
}

MODOS: dict[str, ModoTransporte] = {
    "economico": ModoTransporte("economico", 0.85, 2.0, 2.5),
    "normal": ModoTransporte("normal", 1.0, 1.0, 1.0),
    "rapido": ModoTransporte("rapido", 1.05, 0.5, 0.5),
}

PERFIS_PROIBIDOS_CRISTAL = {"abrasiva", "economica", "expressa_fragil", "pesada", "turbo"}
RISCO_PREFERENCIAL = {0: 0.06, 1: 0.07, 2: 0.07, 3: 0.09, 4: 0.09}
DEGRADACAO_PREFERENCIAL = {0: 0.85, 1: 1.10, 2: 1.10, 3: 1.35, 4: 1.35}
