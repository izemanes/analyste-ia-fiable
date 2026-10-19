"""Couche sémantique : transforme une demande structurée (JSON) en SQL, de façon déterministe.

L'IA n'écrit jamais de SQL ici. Elle choisit des indicateurs et des axes parmi un catalogue
validé ; le compilateur refuse tout ce qui n'y figure pas. Les valeurs sont passées en
paramètres (jamais concaténées), ce qui empêche l'injection SQL.
"""
from __future__ import annotations

import datetime as dt
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CATALOG_PATH = Path(__file__).resolve().parents[2] / "semantic" / "catalog.yml"
OPS = {"=", "!=", ">", ">=", "<", "<=", "in", "not in", "between"}
MAX_METRICS, MAX_DIMS, MAX_FILTERS, MAX_LIMIT = 5, 3, 8, 1000


class SemanticError(ValueError):
    """Demande invalide au regard du catalogue."""


@lru_cache(maxsize=1)
def load_catalog(path: str | None = None) -> dict[str, Any]:
    with open(path or CATALOG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _check_value(dim_name: str, dim: dict, value: Any) -> Any:
    kind = dim["type"]
    if kind == "integer" and isinstance(value, str) and value.strip().isdigit():
        value = int(value)                      # « 2025 » écrit comme texte : simple détail de forme
    if kind == "integer":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
            raise SemanticError(f"'{dim_name}' attend un entier, reçu {value!r}")
        return int(value)
    if kind == "date":
        try:
            return dt.date.fromisoformat(str(value)).isoformat()
        except ValueError:
            raise SemanticError(f"'{dim_name}' attend une date AAAA-MM-JJ, reçu {value!r}") from None
    if not isinstance(value, str):
        raise SemanticError(f"'{dim_name}' attend du texte, reçu {value!r}")
    allowed = dim.get("values")
    if allowed and value not in allowed:
        raise SemanticError(f"Valeur inconnue pour '{dim_name}' : {value!r}. Valeurs possibles : {allowed}")
    return value


def compile_spec(spec: dict[str, Any], catalog: dict[str, Any] | None = None) -> tuple[str, list[Any]]:
    """Retourne (sql, paramètres) pour une demande de statut « ok »."""
    cat = catalog or load_catalog()
    metrics, dims = cat["metrics"], cat["dimensions"]

    if not isinstance(spec, dict):
        raise SemanticError("La demande doit être un objet JSON")
    wanted_metrics = spec.get("metrics") or []
    wanted_dims = spec.get("dimensions") or []
    filters = spec.get("filters") or []
    if not wanted_metrics or len(wanted_metrics) > MAX_METRICS:
        raise SemanticError(f"Il faut entre 1 et {MAX_METRICS} indicateurs")
    if len(wanted_dims) > MAX_DIMS or len(filters) > MAX_FILTERS:
        raise SemanticError("Trop d'axes ou de filtres")
    for m in wanted_metrics:
        if m not in metrics:
            raise SemanticError(f"Indicateur inconnu : {m!r}. Disponibles : {sorted(metrics)}")
    for d in wanted_dims:
        if d not in dims:
            raise SemanticError(f"Axe inconnu : {d!r}. Disponibles : {sorted(dims)}")
    if len(set(wanted_metrics)) != len(wanted_metrics) or len(set(wanted_dims)) != len(wanted_dims):
        raise SemanticError("Indicateurs ou axes en double")

    where, params = [], []
    for f in filters:
        if not isinstance(f, dict) or f.get("dimension") not in dims:
            raise SemanticError(f"Filtre invalide : {f!r}")
        name, op, value = f["dimension"], str(f.get("op", "=")).lower(), f.get("value")
        if op not in OPS:
            raise SemanticError(f"Opérateur inconnu : {op!r}")
        col = dims[name]["sql"]
        if op in ("in", "not in"):
            if not isinstance(value, list) or not value:
                raise SemanticError(f"'{op}' attend une liste non vide")
            vals = [_check_value(name, dims[name], v) for v in value]
            where.append(f"{col} {op.upper()} ({', '.join('?' for _ in vals)})")
            params += vals
        elif op == "between":
            if not isinstance(value, list) or len(value) != 2:
                raise SemanticError("'between' attend une liste de deux valeurs")
            lo, hi = (_check_value(name, dims[name], v) for v in value)
            where.append(f"{col} BETWEEN ? AND ?")
            params += [lo, hi]
        else:
            where.append(f"{col} {op} ?")
            params.append(_check_value(name, dims[name], value))

    select = [f"{dims[d]['sql']} AS {d}" for d in wanted_dims]
    select += [f"{metrics[m]['sql']} AS {m}" for m in wanted_metrics]
    sql = f"SELECT {', '.join(select)}\nFROM {cat['table']}"
    if where:
        sql += "\nWHERE " + " AND ".join(where)
    if wanted_dims:
        sql += "\nGROUP BY " + ", ".join(dims[d]["sql"] for d in wanted_dims)

    order = spec.get("order_by")
    if order:
        field, direction = order.get("field"), str(order.get("direction", "desc")).lower()
        if field not in wanted_metrics and field not in wanted_dims:
            raise SemanticError("order_by doit désigner un indicateur ou un axe demandé")
        if direction not in ("asc", "desc"):
            raise SemanticError("direction doit valoir asc ou desc")
        sql += f"\nORDER BY {field} {direction.upper()}"
    elif wanted_dims:
        sql += "\nORDER BY " + ", ".join(wanted_dims)
    limit = spec.get("limit")
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
            raise SemanticError(f"limit doit être un entier entre 1 et {MAX_LIMIT}")
        sql += f"\nLIMIT {limit}"
    return sql, params


def render_catalog_for_prompt(cat: dict[str, Any] | None = None) -> str:
    """Texte compact du catalogue, destiné au prompt de l'assistant."""
    cat = cat or load_catalog()
    lines = ["INDICATEURS DISPONIBLES :"]
    for name, m in cat["metrics"].items():
        syn = ", ".join(m.get("synonyms", []))
        lines.append(f"- {name} ({m['label']}, unité : {m['unit']}) : {' '.join(m['description'].split())}"
                     + (f" Synonymes : {syn}." if syn else ""))
    lines.append("\nAXES (dimensions) DISPONIBLES :")
    for name, d in cat["dimensions"].items():
        vals = f" Valeurs possibles : {d['values']}." if d.get("values") else ""
        lines.append(f"- {name} ({d['type']}) : {d['description']}{vals}")
    return "\n".join(lines)
