"""
Descarga datos del Mundial equipo por equipo con pausas anti-bloqueo.
"""
import soccerdata as sd
import time
import pandas as pd

PAUSA = 45  # segundos entre cada equipo (evita bloqueo de FBref)

print("Iniciando descarga por equipos...")
fbref = sd.FBref(leagues="INT-World Cup", seasons="2026")

from ligas_config import EQUIPOS_MUNDIAL
equipos = EQUIPOS_MUNDIAL
print(f"  {len(equipos)} equipos a descargar: {equipos[:5]}...")

tiros_lista = []
misc_lista  = []
total = len(equipos)

for i, equipo in enumerate(equipos, 1):
    print(f"\n[{i}/{total}] {equipo}...")
    
    try:
        t = fbref.read_team_match_stats(stat_type='shooting', team=equipo)
        tiros_lista.append(t)
        print(f"  tiros OK ({len(t)} partidos)")
    except Exception as e:
        print(f"  tiros FALLÓ: {e}")

    time.sleep(8)

    try:
        m = fbref.read_team_match_stats(stat_type='misc', team=equipo)
        misc_lista.append(m)
        print(f"  misc OK ({len(m)} partidos)")
    except Exception as e:
        print(f"  misc FALLÓ: {e}")

    if i < total:
        print(f"  Pausa de {PAUSA}s antes del siguiente equipo...")
        time.sleep(PAUSA)

print("\n¡Descarga completada!")

# Exportar un CSV maestro limpio y normalizado. A partir de aqui el predictor
# lee este archivo directamente: 100% offline, rapido y sin depender del cache
# interno de soccerdata.
from ingest_fbref import exportar_historiales_csv, CSV_MAESTRO_MUNDIAL

print(f"\nGenerando archivo maestro '{CSV_MAESTRO_MUNDIAL}'...")
try:
    exportar_historiales_csv(fbref, equipos)
except Exception as e:
    print(f"No se pudo generar el CSV maestro: {e}")

print("Ahora abre app_gui.py normalmente.")
input("Presiona Enter para cerrar...")
