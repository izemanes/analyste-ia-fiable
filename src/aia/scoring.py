"""Comparaison d'un résultat avec la référence.

Règles (volontairement indulgentes sur la forme, strictes sur le fond) :
- l'ordre des lignes et des colonnes n'a pas d'importance ;
- le résultat peut contenir des colonnes en plus (ex. le nom de la région à côté du chiffre) ;
- le nombre de lignes doit être exactement celui attendu ;
- les entiers (comptages) doivent être exacts ; les montants tolèrent un arrondi à l'euro ;
- pour un taux, une valeur en pourcentage (x100) est acceptée.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal


def _is_number(x) -> bool:
    return isinstance(x, (int, float, Decimal)) and not isinstance(x, bool)


def cell_equal(gold, got, ratio_ok: bool = False) -> bool:
    if gold is None or got is None:
        return gold is None and got is None
    if _is_number(gold) and _is_number(got):
        g, r = float(gold), float(got)
        if isinstance(gold, int):                       # comptage, année : exact
            return r == g
        if ratio_ok:
            return abs(g - r) <= 0.0005 or abs(g - r / 100.0) <= 0.0005
        return abs(g - r) <= max(0.51, 1e-4 * abs(g))   # montant : arrondi à l'euro toléré
    if isinstance(gold, (dt.date, dt.datetime)) or isinstance(got, (dt.date, dt.datetime)):
        return str(gold)[:10] == str(got)[:10]
    return str(gold).strip().lower() == str(got).strip().lower()


def _row_matches(gold_row: tuple, got_row: tuple, ratio_ok: bool) -> bool:
    used = [False] * len(got_row)
    for g in gold_row:
        for j, r in enumerate(got_row):
            if not used[j] and cell_equal(g, r, ratio_ok):
                used[j] = True
                break
        else:
            return False
    return True


def results_match(gold_rows: list[tuple], got_rows: list[tuple], ratio_ok: bool = False) -> bool:
    if len(gold_rows) != len(got_rows):
        return False
    used = [False] * len(got_rows)
    for g in gold_rows:
        for j, r in enumerate(got_rows):
            if not used[j] and len(r) >= len(g) and _row_matches(g, r, ratio_ok):
                used[j] = True
                break
        else:
            return False
    return True
