"""
Descarga el snapshot de Elo de clubes de ClubElo y lo cachea en
data/club_elo.csv. Ejecutalo cuando quieras refrescar la fuerza de los clubes
(p. ej. una vez por semana durante la temporada).

Uso:
    py -3.11 descargar_club_elo.py            # snapshot de hoy
    py -3.11 descargar_club_elo.py 2026-01-15 # snapshot de una fecha
"""
# ── Bootstrap de rutas: permite ejecutar este script directamente ──
import os as _os, sys as _sys
_SRC = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _sub in ("", "modelo", "datos", "interfaz", "analisis"):
    _ruta = _os.path.join(_SRC, _sub)
    if _ruta not in _sys.path:
        _sys.path.insert(0, _ruta)

import sys

from club_elo import descargar_club_elo

if __name__ == "__main__":
    fecha = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        descargar_club_elo(fecha)
    except Exception as e:
        raise SystemExit(f"No se pudo descargar ClubElo: {e}")
