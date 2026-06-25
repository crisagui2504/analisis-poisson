"""
Capa de proveedores de datos INTERCAMBIABLES (patrón plug-in).

Objetivo: no casarse con ninguna fuente. Cada proveedor implementa el mismo
contrato (`historial_equipo` -> DataFrame en el esquema normalizado) y es
INDEPENDIENTE: si uno falla, no tiene API key o se cae, los demás siguen
funcionando. Puedes agregar APIs nuevas creando otra subclase de
`ProveedorDatos` y registrándola en PROVEEDORES — nada más cambia.

Fuentes incluidas:
  - FBref (vía soccerdata): goles, tiros, posesión, xG. No necesita clave.
  - football-data.org: resultados/goles del Mundial (free). Necesita API key
    gratis (header X-Auth-Token). No trae tiros/xG en el plan gratuito.

Claves de API: se leen de variables de entorno o de un archivo local
`apis.local.json` (NO se sube a git). Ver apis.example.json.
"""
# ── Bootstrap de rutas: permite ejecutar este script directamente ──
import os as _os, sys as _sys
_SRC = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _sub in ("", "modelo", "datos", "interfaz", "analisis"):
    _ruta = _os.path.join(_SRC, _sub)
    if _ruta not in _sys.path:
        _sys.path.insert(0, _ruta)

import json
import os

import numpy as np
import pandas as pd

from rutas import raiz
from ingest_fbref import (
    COLUMNAS_REQUERIDAS, sd, _chequear_dependencia,
    construir_historial_equipo_directo, fusionar_historiales,
    cargar_historial_csv, existe_csv_maestro, CSV_MAESTRO_MUNDIAL,
)

ESQUEMA = COLUMNAS_REQUERIDAS  # esquema normalizado que consume el modelo


def _leer_clave(nombre_env: str, json_key: str) -> str:
    """Lee una API key de variable de entorno o de apis.local.json."""
    valor = os.environ.get(nombre_env, "").strip()
    if valor:
        return valor
    try:
        with open(raiz("apis.local.json"), encoding="utf-8") as f:
            return str(json.load(f).get(json_key, "")).strip()
    except Exception:
        return ""


# ── Contrato común ───────────────────────────────────────────────────────────

class ProveedorDatos:
    nombre = "base"
    prioridad = 0          # mayor = más confiable (gana al fusionar)
    requiere_clave = False
    rapida = False         # True si responde rápido (API REST) vs scraping lento

    def disponible(self) -> bool:
        raise NotImplementedError

    def historial_equipo(self, equipo: str, temporada: str = "2026") -> pd.DataFrame:
        """Devuelve los partidos del equipo en el esquema ESQUEMA."""
        raise NotImplementedError


# ── FBref (soccerdata) ───────────────────────────────────────────────────────

class FBrefProvider(ProveedorDatos):
    nombre = "FBref"
    prioridad = 10  # fuente más rica (xG, tiros) -> prevalece
    requiere_clave = False
    rapida = False   # scraping con rate-limit: lento

    def disponible(self) -> bool:
        return sd is not None

    def historial_equipo(self, equipo, temporada="2026", no_cache=True):
        _chequear_dependencia()
        fbref = sd.FBref(leagues="INT-World Cup", seasons=temporada, no_cache=no_cache)
        df = construir_historial_equipo_directo(fbref, equipo)
        df["Team"] = equipo
        return df


# ── football-data.org ────────────────────────────────────────────────────────

# Nombres de selección que football-data.org escribe distinto a FBref/el modelo.
ALIAS_FDORG = {
    "Bosnia & Herz.": "Bosnia-Herzegovina",
    "Cabo Verde": "Cape Verde Islands",
    "Côte d'Ivoire": "Ivory Coast",
    "IR Iran": "Iran",
    "Korea Republic": "South Korea",
    "Türkiye": "Turkey",
}


def _parsear_fdorg(data: dict, equipo: str, nombre_busqueda: str = None) -> pd.DataFrame:
    """Convierte la respuesta de /competitions/WC/matches al esquema normalizado
    desde la perspectiva de `equipo`. `nombre_busqueda` es el nombre tal como lo
    escribe football-data.org (puede diferir del nombre del modelo); por defecto
    se usa `equipo`. La columna Team siempre guarda `equipo` (nombre del modelo).
    Función pura (testeable sin red)."""
    busca = (nombre_busqueda or equipo).lower()
    filas = []
    for m in data.get("matches", []):
        if m.get("status") != "FINISHED":
            continue
        home = (m.get("homeTeam") or {}).get("name") or ""
        away = (m.get("awayTeam") or {}).get("name") or ""
        ft = (m.get("score") or {}).get("fullTime") or {}
        gh, ga = ft.get("home"), ft.get("away")
        if gh is None or ga is None:
            continue
        if busca == home.lower():
            rival, gf, gc, venue = away, gh, ga, "Home"
        elif busca == away.lower():
            rival, gf, gc, venue = home, ga, gh, "Away"
        else:
            continue
        res = "W" if gf > gc else ("L" if gf < gc else "D")
        filas.append({
            "Date": m["utcDate"][:10], "Team": equipo, "Opponent": rival,
            "Venue": venue, "Result": res, "GF": gf, "GA": gc,
            "Poss": 0, "Sh": 0, "SoT": 0, "xG": np.nan, "xGA": np.nan,
            "Fls": 0, "CrdY": 0, "CrdR": 0,
        })
    df = pd.DataFrame(filas, columns=ESQUEMA)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
    return df


class FootballDataOrgProvider(ProveedorDatos):
    nombre = "football-data.org"
    prioridad = 5  # solo goles/resultados -> cede ante FBref
    requiere_clave = True
    rapida = True   # API REST: responde en segundos
    BASE = "https://api.football-data.org/v4"

    def __init__(self):
        self.clave = _leer_clave("FOOTBALL_DATA_ORG_KEY", "football_data_org")
        self._cache_matches = None

    def disponible(self) -> bool:
        return bool(self.clave)

    def _matches_mundial(self) -> dict:
        if self._cache_matches is None:
            import requests
            r = requests.get(f"{self.BASE}/competitions/WC/matches",
                             headers={"X-Auth-Token": self.clave}, timeout=20)
            r.raise_for_status()
            self._cache_matches = r.json()
        return self._cache_matches

    def historial_equipo(self, equipo, temporada="2026"):
        fd_nombre = ALIAS_FDORG.get(equipo, equipo)
        return _parsear_fdorg(self._matches_mundial(), equipo, nombre_busqueda=fd_nombre)


# ── Registro de proveedores (agrega aquí nuevas APIs) ────────────────────────

PROVEEDORES = [
    FBrefProvider(),
    FootballDataOrgProvider(),
]


def proveedores_disponibles():
    """Lista de proveedores configurados y usables, de mayor a menor prioridad."""
    return sorted([p for p in PROVEEDORES if p.disponible()],
                  key=lambda x: -x.prioridad)


def diagnostico():
    """Imprime qué proveedores están disponibles (para que sepas qué tienes)."""
    print("Proveedores de datos registrados:")
    for p in sorted(PROVEEDORES, key=lambda x: -x.prioridad):
        if p.disponible():
            estado = "[disponible]"
        elif p.requiere_clave:
            estado = "[falta API key]"
        else:
            estado = "[no instalado]"
        print(f"  - {p.nombre:<20} (prioridad {p.prioridad:>2})  {estado}")


def historial_equipo(equipo, temporada="2026", proveedor=None):
    """
    Devuelve (DataFrame, nombre_fuente) del PRIMER proveedor que responda, en
    orden de prioridad. Cada proveedor está aislado: si uno lanza error, se
    intenta el siguiente — uno no descompone a los demás.
    """
    candidatos = [proveedor] if proveedor else proveedores_disponibles()
    errores = []
    for p in candidatos:
        try:
            df = p.historial_equipo(equipo, temporada)
            if df is not None and not df.empty:
                return df, p.nombre
        except Exception as e:
            errores.append(f"{p.nombre}: {e}")
    raise RuntimeError(f"Ningún proveedor devolvió datos para '{equipo}'. {errores}")


def historial_combinado(equipo, temporada="2026", provs=None) -> pd.DataFrame:
    """
    Fusiona el historial de los proveedores indicados (o todos los disponibles).
    Cruza fuentes para más cobertura/precisión: se aplican de menor a mayor
    prioridad, así la fuente más confiable (FBref) prevalece. Aislado: un
    proveedor que falle no rompe a los demás. Deduplica por Team+Date.
    """
    if provs is None:
        provs = proveedores_disponibles()
    combinado = pd.DataFrame()
    for p in sorted(provs, key=lambda x: x.prioridad):
        try:
            df = p.historial_equipo(equipo, temporada)
            if df is not None and not df.empty:
                combinado = fusionar_historiales(combinado, df, claves=["Team", "Date"])
        except Exception:
            continue
    return combinado


def actualizar_csv(equipos=None, temporada="2026", ruta=CSV_MAESTRO_MUNDIAL,
                   verbose=False, callback=None, solo_rapidas=False) -> dict:
    """
    Actualiza el CSV maestro combinando proveedores, sin borrarlo (fusión
    incremental). Si solo hay FBref, equivale al updater normal; si además hay
    football-data.org, cruza ambas fuentes.

    solo_rapidas=True usa solo fuentes rápidas (API REST, p. ej. football-data.org)
    y evita el scraping lento de FBref — ideal para actualizar justo antes de
    predecir. Si no hay ninguna fuente rápida, cae a usar todas las disponibles.
    """
    if equipos is None:
        from ligas_config import EQUIPOS_MUNDIAL
        equipos = EQUIPOS_MUNDIAL

    disponibles = proveedores_disponibles()
    if solo_rapidas:
        rapidas = [p for p in disponibles if p.rapida]
        usar = rapidas if rapidas else disponibles
    else:
        usar = disponibles

    existente = cargar_historial_csv(ruta) if existe_csv_maestro(ruta) else pd.DataFrame()
    antes = len(existente)

    nuevos = []
    total = len(equipos)
    for i, eq in enumerate(equipos, 1):
        if callback is not None:
            callback(i, total, eq)
        if verbose:
            print(f"[{i}/{total}] {eq}...")
        try:
            df = historial_combinado(eq, temporada, provs=usar)
            if not df.empty:
                nuevos.append(df)
        except Exception as e:
            print(f"  Aviso: {eq}: {e}")

    df_nuevo = pd.concat(nuevos, ignore_index=True) if nuevos else pd.DataFrame()
    maestro = fusionar_historiales(existente, df_nuevo, claves=["Team", "Date"])
    maestro.to_csv(ruta, index=False, encoding="utf-8")
    resumen = {"filas_antes": antes, "filas_despues": len(maestro),
               "partidos_nuevos": len(maestro) - antes,
               "equipos": int(maestro["Team"].nunique()) if "Team" in maestro else 0,
               "fuentes": [p.nombre for p in usar]}
    print(f"Actualizado '{ruta}': +{resumen['partidos_nuevos']} partidos "
          f"(fuentes: {', '.join(resumen['fuentes']) or 'ninguna'}).")
    return resumen


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "update":
        # py proveedores.py update            -> todas las selecciones (multi-fuente)
        # py proveedores.py update Spain Brazil -> solo esas (rapido)
        equipos = sys.argv[2:] or None
        diagnostico()
        print()
        actualizar_csv(equipos=equipos, verbose=True)
    else:
        diagnostico()
        print("\nUso: py proveedores.py            (diagnostico)")
        print("     py proveedores.py update [Equipo1 Equipo2 ...]  (actualizar)")
