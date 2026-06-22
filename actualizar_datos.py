"""
Actualizacion INCREMENTAL de la base del Mundial.

A diferencia de descargar_datos.py (que descarga todo de cero con pausas largas),
este script solo trae los partidos recientes de FBref y los fusiona con
base_mundial_2026.csv SIN borrarlo: agrega unicamente los partidos nuevos.

Uso:
    py -3.11 actualizar_datos.py

Pensado para correrlo periodicamente segun se van jugando partidos.
"""
import soccerdata as sd

from ingest_fbref import actualizar_csv_maestro, CSV_MAESTRO_MUNDIAL
from ligas_config import EQUIPOS_MUNDIAL

PAUSA = 6  # segundos entre equipos (suave; ya tenemos la mayoria en cache)

print("Actualizacion incremental del Mundial 2026")
print(f"Equipos a revisar: {len(EQUIPOS_MUNDIAL)}")

# no_cache=True para que FBref traiga los partidos mas recientes, no la copia vieja.
fbref = sd.FBref(leagues="INT-World Cup", seasons="2026", no_cache=True)

resumen = actualizar_csv_maestro(fbref, EQUIPOS_MUNDIAL, pausa=PAUSA, verbose=True)

print("\nResumen:")
print(f"  Partidos nuevos agregados: {resumen['partidos_nuevos']}")
print(f"  Total de partidos ahora:   {resumen['filas_despues']}")
print(f"  Equipos:                   {resumen['equipos']}")
print(f"\nListo. '{CSV_MAESTRO_MUNDIAL}' actualizado. Abre la app normalmente.")
input("Presiona Enter para cerrar...")
