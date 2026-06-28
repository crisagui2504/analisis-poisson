"""
Genera (o actualiza) el CSV maestro de una liga de CLUBES, igual que
descargar_datos.py hace para el Mundial. Tras esto, la app predice esa liga
100% offline y al instante (sin volver a parsear FBref).

Uso:
    py -3.11 descargar_liga_csv.py                       # lista las ligas
    py -3.11 descargar_liga_csv.py "ENG-Premier League"  # codigo FBref
    py -3.11 descargar_liga_csv.py "La Liga (España)"    # nombre de la app
    py -3.11 descargar_liga_csv.py "ITA-Serie A" 2025-2026 30
    py -3.11 descargar_liga_csv.py "ENG-Premier League" 2025-2026 20 sin-previa

El 2do argumento (opcional) es la temporada; el 3ro, la pausa en segundos entre
equipos (anti-bloqueo de FBref; sube a 30-45 si te bloquean en la 1a carga).

Por defecto aplica "arranque en frio": a los equipos con pocos partidos en la
temporada actual les concatena la temporada anterior (misma liga) para que el
shrinkage no los trate como promedio. Pasa 'sin-previa' como ultimo argumento
para desactivarlo.
"""
# ── Bootstrap de rutas: permite ejecutar este script directamente ──
import os as _os, sys as _sys
_SRC = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _sub in ("", "modelo", "datos", "interfaz", "analisis"):
    _ruta = _os.path.join(_SRC, _sub)
    if _ruta not in _sys.path:
        _sys.path.insert(0, _ruta)

import sys

from ligas_config import LIGAS, TEMPORADAS
from ingest_fbref import actualizar_liga_csv, ruta_csv_liga


def _resolver(arg):
    """Acepta el nombre de la app ('La Liga (España)') o el codigo FBref
    ('ESP-La Liga') y devuelve (codigo, temporada_por_defecto)."""
    if arg in LIGAS:                       # nombre de la app
        return LIGAS[arg], TEMPORADAS[arg]
    for nombre, codigo in LIGAS.items():   # codigo FBref
        if codigo == arg:
            return codigo, TEMPORADAS[nombre]
    return arg, None                       # codigo desconocido: temporada obligatoria


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Ligas disponibles:")
        for nombre, codigo in LIGAS.items():
            if codigo == "INT-World Cup":
                continue  # el Mundial usa descargar_datos.py
            print(f"  {codigo:22} {nombre}  (temporada {TEMPORADAS[nombre]})")
        raise SystemExit("\nPasa una liga como argumento.")

    args = sys.argv[1:]
    sin_previa = "sin-previa" in args
    args = [a for a in args if a != "sin-previa"]

    liga, temporada_def = _resolver(args[0])
    temporada = args[1] if len(args) > 1 else temporada_def
    pausa = float(args[2]) if len(args) > 2 else 20.0

    if temporada is None:
        raise SystemExit(f"Indica la temporada para '{liga}' (ej. 2025-2026).")

    previa = None if sin_previa else "auto"
    print(f"Generando CSV maestro de {liga} ({temporada}) -> {ruta_csv_liga(liga, temporada)}")
    print(f"Pausa de {pausa:g}s entre equipos | arranque en frio: "
          f"{'desactivado' if sin_previa else 'activado'}\n")
    try:
        actualizar_liga_csv(liga, temporada, pausa=pausa, verbose=True,
                            temporada_previa=previa)
    except Exception as e:
        raise SystemExit(f"No se pudo generar el CSV de la liga: {e}")
    print("\nListo. La app ya predice esta liga offline.")
