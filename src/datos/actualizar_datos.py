"""
Actualizacion INCREMENTAL de la base del Mundial.

A diferencia de descargar_datos.py (que descarga todo de cero), este script trae
los partidos recientes de FBref y los fusiona con base_mundial_2026.csv SIN
borrarlo: agrega unicamente los partidos nuevos.

IMPORTANTE sobre el tiempo: FBref no permite pedir "solo lo nuevo"; cada equipo
baja su temporada completa, y FBref limita a los scrapers (soccerdata espacia las
peticiones). Por eso actualizar las 48 selecciones tarda varios minutos. Si solo
jugaron unos pocos equipos, actualiza SOLO esos pasandolos como argumento:

    py -3.11 actualizar_datos.py                       # las 48 (lento)
    py -3.11 actualizar_datos.py Spain Brazil Mexico   # solo esos (rapido)
"""
# ── Bootstrap de rutas: permite ejecutar este script directamente ──
import os as _os, sys as _sys
_SRC = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _sub in ("", "modelo", "datos", "interfaz", "analisis"):
    _ruta = _os.path.join(_SRC, _sub)
    if _ruta not in _sys.path:
        _sys.path.insert(0, _ruta)

import sys

import soccerdata as sd

from ingest_fbref import actualizar_csv_maestro, CSV_MAESTRO_MUNDIAL
from ligas_config import EQUIPOS_MUNDIAL

# Equipos a actualizar: los pasados por argumento, o las 48 si no se pasa ninguno.
equipos = sys.argv[1:] if len(sys.argv) > 1 else EQUIPOS_MUNDIAL

desconocidos = [e for e in equipos if e not in EQUIPOS_MUNDIAL]
if desconocidos:
    print(f"Aviso: estos nombres no estan en la lista del Mundial (revisa "
          f"el nombre exacto de FBref): {desconocidos}")

# Sin equipos pasados -> actualizacion completa, con pausa anti-bloqueo.
# Con pocos equipos -> sin pausa, es rapido.
pausa = 6 if equipos is EQUIPOS_MUNDIAL else 0

print("Actualizacion incremental del Mundial 2026")
print(f"Equipos a actualizar: {len(equipos)}"
      + (" (TODOS, puede tardar varios minutos)" if pausa else ""))

# no_cache=True para que FBref traiga los partidos mas recientes, no la copia vieja.
fbref = sd.FBref(leagues="INT-World Cup", seasons="2026", no_cache=True)
resumen = actualizar_csv_maestro(fbref, equipos, pausa=pausa, verbose=True)

print("\nResumen:")
print(f"  Partidos nuevos agregados: {resumen['partidos_nuevos']}")
print(f"  Total de partidos ahora:   {resumen['filas_despues']}")
print(f"  Equipos en la base:        {resumen['equipos']}")
print(f"\nListo. '{CSV_MAESTRO_MUNDIAL}' actualizado. Abre la app normalmente.")
input("Presiona Enter para cerrar...")
