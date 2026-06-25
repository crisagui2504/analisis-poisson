"""
Calcula promedios del Mundial leyendo directamente el cache HTML de soccerdata.

No importa soccerdata ni abre Chrome. Lee archivos como:
    C:\\Users\\<usuario>\\soccerdata\\data\\FBref\\matchlogs_Spain_2026_shooting.html

Genera data/promedios_liga.json, que usa el shrinkage del modelo.
"""
# ── Bootstrap de rutas: permite ejecutar este script directamente ──
import os as _os, sys as _sys
_SRC = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _sub in ("", "modelo", "datos", "interfaz", "analisis"):
    _ruta = _os.path.join(_SRC, _sub)
    if _ruta not in _sys.path:
        _sys.path.insert(0, _ruta)

import json
from pathlib import Path

import numpy as np
import pandas as pd

from rutas import data

CACHE_BASE = Path.home() / "soccerdata" / "data" / "FBref"
SALIDA = Path(data("promedios_liga.json"))


def _aplanar_columnas(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            "_".join(str(x) for x in col if str(x) and "Unnamed" not in str(x)).strip()
            for col in df.columns
        ]
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _buscar_columna(df, *nombres):
    cols = {c.lower(): c for c in df.columns}
    for nombre in nombres:
        objetivo = nombre.lower()
        for col_lower, col_original in cols.items():
            partes = col_lower.replace("-", "_").replace(" ", "_").split("_")
            if objetivo == col_lower or objetivo in partes or col_lower.endswith("_" + objetivo):
                return col_original
    return None


def _tabla_matchlog(ruta, table_id):
    tablas = pd.read_html(ruta, attrs={"id": table_id})
    if not tablas:
        return None
    return _aplanar_columnas(tablas[0])


def _agregar_numericos(destino, df, *columnas):
    for columna in columnas:
        col = _buscar_columna(df, columna)
        if col:
            vals = pd.to_numeric(df[col], errors="coerce").dropna()
            if not vals.empty:
                destino.extend(vals.tolist())
                return True
    return False


print(f"Buscando cache HTML en: {CACHE_BASE}")
if not CACHE_BASE.exists():
    raise SystemExit(f"No se encontro la carpeta de cache: {CACHE_BASE}")

archivos_shooting = sorted(CACHE_BASE.glob("matchlogs_*_2026_shooting.html"))
print(f"Encontrados {len(archivos_shooting)} archivos shooting en cache")

if not archivos_shooting:
    raise SystemExit("No se encontraron archivos matchlogs_*_2026_shooting.html")

xg_vals = []
xga_vals = []
sot_vals = []
leidos = 0
fallidos = 0

for ruta in archivos_shooting:
    equipo = ruta.name.removeprefix("matchlogs_").removesuffix("_2026_shooting.html")
    try:
        tabla_for = _tabla_matchlog(ruta, "matchlogs_for")
        tabla_against = _tabla_matchlog(ruta, "matchlogs_against")

        if tabla_for is None:
            raise ValueError("no se encontro tabla 'For'")

        # Los HTML cacheados de selecciones pueden no traer xG. En ese caso,
        # GF/GA son el fallback mas estable para evitar tocar red.
        _agregar_numericos(xg_vals, tabla_for, "xg") or _agregar_numericos(xg_vals, tabla_for, "gf")
        _agregar_numericos(sot_vals, tabla_for, "sot")

        if tabla_against is not None:
            _agregar_numericos(xga_vals, tabla_against, "xga") or _agregar_numericos(xga_vals, tabla_for, "ga")
        else:
            _agregar_numericos(xga_vals, tabla_for, "xga") or _agregar_numericos(xga_vals, tabla_for, "ga")

        leidos += 1
    except Exception as exc:
        fallidos += 1
        if fallidos <= 5:
            print(f"  Advertencia: no se pudo leer {ruta.name}: {exc}")

promedios = {
    "xg_favor": round(float(np.mean(xg_vals)), 4) if xg_vals else 1.3,
    "xg_contra": round(float(np.mean(xga_vals)), 4) if xga_vals else 1.3,
    "sot": round(float(np.mean(sot_vals)), 4) if sot_vals else 4.5,
}

with open(SALIDA, "w", encoding="utf-8") as f:
    json.dump(promedios, f, indent=2)

print(f"\nArchivos leidos: {leidos} | Fallos: {fallidos}")
print(f"Valores favor: {len(xg_vals)} | contra: {len(xga_vals)} | SoT: {len(sot_vals)}")
print("\nListo. Promedios del torneo:")
print(json.dumps(promedios, indent=2))
print(f"\nGuardado en {SALIDA.resolve()}")
print("Ya puedes abrir la app con: py app_gui.py")
