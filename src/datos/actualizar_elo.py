"""
Recalcula el Elo de las SELECCIONES a partir de los resultados del Mundial y lo
guarda en data/elo_override.json, que ligas_config funde sobre ELO_RANKING.

Cierra el hueco de que ELO_RANKING es un prior fijo: con esto, un mal grupo de
Argentina o un Brasil en racha se reflejan en el Elo (y por tanto en SoS, el
empuje al favorito, el Monte Carlo y los penales).

Parte SIEMPRE de ELO_RANKING_BASE (el prior pre-torneo), asi que correrlo varias
veces no acumula: recalcula desde cero con todos los partidos desde `desde`.

Uso:
    py -3.11 actualizar_elo.py                 # desde el inicio del torneo
    py -3.11 actualizar_elo.py 2026-06-11      # desde una fecha
    py -3.11 actualizar_elo.py 2026-06-11 40   # ... y con factor K=40
"""
# ── Bootstrap de rutas: permite ejecutar este script directamente ──
import os as _os, sys as _sys
_SRC = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _sub in ("", "modelo", "datos", "interfaz", "analisis"):
    _ruta = _os.path.join(_SRC, _sub)
    if _ruta not in _sys.path:
        _sys.path.insert(0, _ruta)

import json

import pandas as pd

from ligas_config import (ELO_RANKING_BASE, ELO_REFERENCIA, ELO_ALIAS,
                          ELO_OVERRIDE_PATH, EQUIPOS_MUNDIAL, _limpiar_nombre_rival)
from ingest_fbref import cargar_historial_csv

INICIO_MUNDIAL = "2026-06-11"  # arranque asumido del torneo (ajustable por arg)


def _clave(nombre):
    """Nombre del CSV -> clave canonica de ELO_RANKING (quita codigo + alias)."""
    n = _limpiar_nombre_rival(nombre)
    return ELO_ALIAS.get(n, n)


def calcular_elo_actualizado(desde=INICIO_MUNDIAL, k=30, factor_margen=True):
    """
    Devuelve (ratings, jugados): el Elo recalculado por la formula estandar
    Elo (con bono por margen de victoria si factor_margen) y cuantos partidos
    jugo cada equipo en la ventana. Sin fuga: parte de ELO_RANKING_BASE.

    Cada partido se procesa UNA vez (el CSV trae una fila por equipo, asi que se
    deduplica por fecha + pareja).
    """
    df = cargar_historial_csv().copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")
    if desde:
        df = df[df["Date"] >= pd.to_datetime(desde)]

    ratings = dict(ELO_RANKING_BASE)
    jugados, vistos = {}, set()
    for _, r in df.iterrows():
        res = r.get("Result")
        if res not in ("W", "D", "L"):
            continue
        a, b = _clave(r["Team"]), _clave(r["Opponent"])
        if not a or not b or a == b:
            continue
        clave = (r["Date"], frozenset((a, b)))
        if clave in vistos:
            continue
        vistos.add(clave)

        sa = 1.0 if res == "W" else 0.5 if res == "D" else 0.0
        ra = ratings.get(a, ELO_REFERENCIA)
        rb = ratings.get(b, ELO_REFERENCIA)
        ea = 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))   # expectativa de a
        kk = k
        if factor_margen:
            try:
                margen = abs(float(r["GF"]) - float(r["GA"]))
            except (TypeError, ValueError):
                margen = 1.0
            kk = k * (1.0 + 0.5 * max(0.0, margen - 1.0))  # +50% por gol extra
        delta = kk * (sa - ea)
        ratings[a], ratings[b] = ra + delta, rb - delta
        jugados[a] = jugados.get(a, 0) + 1
        jugados[b] = jugados.get(b, 0) + 1

    return {t: round(v) for t, v in ratings.items()}, jugados


def guardar_override(ratings):
    """Guarda en elo_override.json solo las selecciones del Mundial que cambiaron
    respecto al prior. Devuelve ese dict de cambios."""
    cambios = {t: ratings[t] for t in EQUIPOS_MUNDIAL
               if t in ratings and ratings[t] != ELO_RANKING_BASE.get(t)}
    with open(ELO_OVERRIDE_PATH, "w", encoding="utf-8") as f:
        json.dump(cambios, f, ensure_ascii=False, indent=2)
    return cambios


if __name__ == "__main__":
    desde = _sys.argv[1] if len(_sys.argv) > 1 else INICIO_MUNDIAL
    k = float(_sys.argv[2]) if len(_sys.argv) > 2 else 30

    ratings, jugados = calcular_elo_actualizado(desde=desde, k=k)
    cambios = guardar_override(ratings)

    print(f"Elo recalculado desde {desde} (K={k:g}). Selecciones que cambiaron:")
    if not cambios:
        print("  (ninguna: no hay partidos del Mundial en la ventana)")
    else:
        print(f"  {'Equipo':<18}{'antes':>7}{'ahora':>7}{'dif':>6}{'PJ':>4}")
        for t in sorted(cambios, key=lambda x: cambios[x] - ELO_RANKING_BASE[x]):
            base, nuevo = ELO_RANKING_BASE[t], cambios[t]
            print(f"  {t:<18}{base:>7}{nuevo:>7}{nuevo - base:>+6}{jugados.get(t, 0):>4}")
    print(f"\nGuardado en {ELO_OVERRIDE_PATH}. ligas_config lo aplicara al importar.")
