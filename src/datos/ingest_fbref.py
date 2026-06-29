"""
Ingesta automatica de datos desde FBref usando soccerdata.

Para el Mundial, la ruta rapida evita read_schedule() y pide shooting/misc por
equipo, igual que descargar_datos.py. soccerdata cachea por firma exacta de
peticion, asi que esto reutiliza el cache local ya descargado.
"""
import os
import re
from typing import List, Sequence

import pandas as pd
import numpy as np

from rutas import data

try:
    import soccerdata as sd
except ImportError:
    sd = None


COLUMNAS_REQUERIDAS = [
    "Date", "Team", "Opponent", "Venue", "Result", "GF", "GA",
    "Poss", "Sh", "SoT", "xG", "xGA", "Fls", "CrdY", "CrdR",
]

# Archivo maestro limpio del Mundial. Se genera con descargar_datos.py y permite
# que la prediccion sea 100% offline y rapida (sin tocar el cache de soccerdata).
CSV_MAESTRO_MUNDIAL = data("base_mundial_2026.csv")


def ruta_csv_liga(liga: str, temporada: str) -> str:
    """
    Ruta del CSV maestro de una liga de clubes: data/liga_<slug>_<temporada>.csv.

    Mismo esquema y proposito que base_mundial_2026.csv pero por liga: permite que
    la prediccion de clubes sea 100% offline (sin volver a parsear FBref cada vez).
    El prefijo 'liga_' lo separa del 'base_mundial_' en .gitignore.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", str(liga).lower()).strip("-")
    return data(f"liga_{slug}_{temporada}.csv")


def existe_csv_liga(liga: str, temporada: str) -> bool:
    """True si ya hay un CSV maestro local para esa liga y temporada."""
    return os.path.exists(ruta_csv_liga(liga, temporada))


def _temporada_anterior(temporada: str):
    """
    Devuelve la temporada inmediatamente anterior, o None si no se puede inferir.
    '2025-2026' -> '2024-2025'; '2026' -> '2025'.
    """
    t = str(temporada).strip()
    if "-" in t:
        a, b = t.split("-", 1)
        if a.isdigit() and b.isdigit():
            return f"{int(a) - 1}-{int(b) - 1}"
    elif t.isdigit():
        return str(int(t) - 1)
    return None


def _chequear_dependencia():
    """Lanza un error claro si soccerdata no esta instalado."""
    if sd is None:
        raise ImportError("Falta instalar 'soccerdata'. Ejecuta: pip install soccerdata")


def _aplanar_columnas(df):
    """Aplana columnas MultiIndex de FBref a nombres simples."""
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        nuevas = []
        for col in df.columns:
            partes = [str(c).strip() for c in col if c and "Unnamed" not in str(c)]
            nuevas.append("_".join(partes) if partes else str(col[-1]).strip())
        df.columns = nuevas
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _buscar_columna(df, *posibles_nombres):
    """Busca por coincidencia exacta o por sufijo tras aplanar MultiIndex."""
    cols_lower = {c.lower(): c for c in df.columns}

    for nombre in posibles_nombres:
        encontrado = cols_lower.get(nombre.lower())
        if encontrado is not None:
            return encontrado

    for nombre in posibles_nombres:
        objetivo = nombre.lower()
        for c_lower, c_original in cols_lower.items():
            partes = c_lower.replace("-", "_").replace(" ", "_").split("_")
            if objetivo in partes or c_lower.endswith("_" + objetivo):
                return c_original

    return None


def _copiar_columna_si_falta(origen, destino, *nombres):
    """Copia una columna de `origen` a `destino` si existe alli y aun no esta."""
    col_origen = _buscar_columna(origen, *nombres)
    if col_origen is None:
        return
    col_destino = col_origen
    if col_destino not in destino.columns:
        destino[col_destino] = origen[col_origen].values


def exportar_historiales_csv(fbref, equipos: Sequence[str],
                             ruta: str = CSV_MAESTRO_MUNDIAL) -> pd.DataFrame:
    """
    Construye el historial normalizado de cada equipo y lo guarda en un unico
    CSV maestro limpio. El predictor luego lo lee directamente, sin depender del
    cache interno de soccerdata.
    """
    historiales: List[pd.DataFrame] = []
    for equipo in equipos:
        try:
            df = construir_historial_equipo_directo(fbref, equipo)
            df["Team"] = equipo
            historiales.append(df)
        except Exception as exc:
            print(f"  Aviso: no se pudo normalizar '{equipo}': {exc}")

    if not historiales:
        raise RuntimeError("No se pudo construir el historial de ningun equipo.")

    maestro = pd.concat(historiales, ignore_index=True)
    maestro.to_csv(ruta, index=False, encoding="utf-8")
    print(f"CSV maestro guardado en '{ruta}' ({len(maestro)} filas, "
          f"{maestro['Team'].nunique()} equipos).")
    return maestro


def cargar_historial_csv(ruta: str = CSV_MAESTRO_MUNDIAL) -> pd.DataFrame:
    """Carga el CSV maestro y normaliza la columna de fecha. Sin red."""
    df = pd.read_csv(ruta, encoding="utf-8")
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df


def promedios_desde_csv(equipos=None, ruta: str = CSV_MAESTRO_MUNDIAL) -> dict:
    """
    Calcula los promedios del torneo (xg_favor / xg_contra / sot) desde la base
    maestra, opcionalmente solo para `equipos`. 100% offline (no toca el cache
    HTML). Usa xG si existe y si no GF/GA, igual que el shrinkage del modelo.

    Util en eliminatorias: pasando solo los equipos clasificados, la media deja
    de estar contaminada por los equipos debiles ya eliminados.
    """
    df = cargar_historial_csv(ruta)
    if equipos is not None:
        df = df[df["Team"].isin(set(equipos))]
    favor = df["xG"].where(df["xG"].notna(), df["GF"]) if "xG" in df else df["GF"]
    contra = df["xGA"].where(df["xGA"].notna(), df["GA"]) if "xGA" in df else df["GA"]
    sot = pd.to_numeric(df.get("SoT"), errors="coerce")
    sot = sot[sot > 0]  # los 0 son placeholders de FBref para selecciones
    return {
        "xg_favor": round(float(favor.mean()), 4) if favor.notna().any() else 1.3,
        "xg_contra": round(float(contra.mean()), 4) if contra.notna().any() else 1.3,
        "sot": round(float(sot.mean()), 4) if not sot.empty else 4.5,
    }


CLAVES_PARTIDO = ["Team", "Date", "Opponent"]


def fusionar_historiales(df_existente: pd.DataFrame, df_nuevo: pd.DataFrame,
                         claves: Sequence[str] = CLAVES_PARTIDO) -> pd.DataFrame:
    """
    Une el historial existente con datos nuevos SIN duplicar partidos. Si un
    partido aparece en ambos (misma clave Team+Date+Opponent), conserva la
    version nueva (datos mas recientes/corregidos). Devuelve el historial
    completo, ordenado.
    """
    if df_existente is None or df_existente.empty:
        combinado = df_nuevo.copy()
    elif df_nuevo is None or df_nuevo.empty:
        combinado = df_existente.copy()
    else:
        combinado = pd.concat([df_existente, df_nuevo], ignore_index=True)

    if "Date" in combinado.columns:
        combinado["Date"] = pd.to_datetime(combinado["Date"], errors="coerce")

    claves_presentes = [c for c in claves if c in combinado.columns]
    # keep="last" => prevalece df_nuevo, que va despues en el concat.
    combinado = combinado.drop_duplicates(subset=claves_presentes, keep="last")
    orden = [c for c in ["Team", "Date"] if c in combinado.columns]
    if orden:
        combinado = combinado.sort_values(orden)
    return combinado.reset_index(drop=True)


def actualizar_csv_maestro(fbref, equipos: Sequence[str],
                           ruta: str = CSV_MAESTRO_MUNDIAL,
                           pausa: float = 0.0, verbose: bool = False,
                           callback=None) -> dict:
    """
    Actualiza el CSV maestro incrementalmente: descarga el historial actual de
    cada equipo, lo fusiona con el CSV existente y guarda solo el resultado. No
    borra nada; solo agrega los partidos nuevos. Devuelve un resumen.

    pausa:    segundos a esperar entre equipos (anti-bloqueo de FBref).
    callback: funcion opcional callback(i, total, equipo) para reportar avance.
    """
    import time

    existente = cargar_historial_csv(ruta) if os.path.exists(ruta) else pd.DataFrame()
    filas_antes = len(existente)

    nuevos = []
    total = len(equipos)
    for i, equipo in enumerate(equipos, 1):
        if verbose:
            print(f"[{i}/{total}] {equipo}...")
        if callback is not None:
            callback(i, total, equipo)
        try:
            df = construir_historial_equipo_directo(fbref, equipo)
            df["Team"] = equipo
            nuevos.append(df)
        except Exception as exc:
            print(f"  Aviso: no se pudo actualizar '{equipo}': {exc}")
        if pausa and i < total:
            time.sleep(pausa)

    df_nuevo = pd.concat(nuevos, ignore_index=True) if nuevos else pd.DataFrame()
    maestro = fusionar_historiales(existente, df_nuevo)
    maestro.to_csv(ruta, index=False, encoding="utf-8")

    resumen = {
        "filas_antes": filas_antes,
        "filas_despues": len(maestro),
        "partidos_nuevos": len(maestro) - filas_antes,
        "equipos": int(maestro["Team"].nunique()) if "Team" in maestro else 0,
    }
    print(f"Actualizado '{ruta}': {resumen['partidos_nuevos']} partidos nuevos "
          f"({filas_antes} -> {resumen['filas_despues']} filas, "
          f"{resumen['equipos']} equipos).")
    return resumen


def existe_csv_maestro(ruta: str = CSV_MAESTRO_MUNDIAL) -> bool:
    """True si existe la base maestra del Mundial (data/base_mundial_2026.csv)."""
    return os.path.exists(ruta)


def construir_historial_equipo_directo(fbref, nombre_equipo: str) -> pd.DataFrame:
    """
    Lee shooting y misc para un solo equipo y normaliza columnas para
    feature_engineering.py. No llama read_schedule().
    """
    _chequear_dependencia()

    tiros = _aplanar_columnas(
        fbref.read_team_match_stats(stat_type="shooting", team=nombre_equipo).reset_index()
    )

    try:
        misc = _aplanar_columnas(
            fbref.read_team_match_stats(stat_type="misc", team=nombre_equipo).reset_index()
        )
    except Exception:
        misc = pd.DataFrame()

    combinado = tiros.copy()
    if not misc.empty:
        posibles_claves = ["league", "season", "game", "date", "team"]
        claves = [c for c in posibles_claves if c in combinado.columns and c in misc.columns]
        if claves:
            combinado = combinado.merge(misc, on=claves, how="left", suffixes=("", "_misc"))
        elif len(combinado) == len(misc):
            for nombres in [("Fls", "fls"), ("CrdY", "crdy"), ("CrdR", "crdr")]:
                _copiar_columna_si_falta(misc, combinado, *nombres)

    resultado = pd.DataFrame()
    mapa_destino = {
        "Date": ("date",),
        "Team": ("team",),
        "Result": ("result",),
        "Opponent": ("opponent",),
        "Venue": ("venue",),
        "GF": ("gf",),
        "GA": ("ga",),
        "Poss": ("poss",),
        "Sh": ("sh",),
        "SoT": ("sot",),
        "xG": ("xg",),
        "xGA": ("xga",),
        "Fls": ("fls",),
        "CrdY": ("crdy",),
        "CrdR": ("crdr",),
    }

    faltantes = []
    for destino, posibles in mapa_destino.items():
        col_real = _buscar_columna(combinado, *posibles)
        if col_real is not None:
            resultado[destino] = combinado[col_real]
        else:
            faltantes.append(destino)

    if "Team" not in resultado.columns:
        resultado["Team"] = nombre_equipo

    obligatorias_faltantes = [c for c in ["Date", "Result", "GF", "GA"] if c in faltantes]
    if obligatorias_faltantes:
        raise KeyError(
            f"No se pudieron mapear columnas obligatorias {obligatorias_faltantes} "
            f"para '{nombre_equipo}'. Columnas disponibles: {list(combinado.columns)}"
        )

    for col in ["Poss", "Sh", "SoT", "xG", "xGA", "Fls", "CrdY", "CrdR"]:
        if col not in resultado.columns:
            resultado[col] = np.nan if col in ["xG", "xGA"] else 0

    resultado["Date"] = pd.to_datetime(resultado["Date"])
    return resultado.sort_values("Date").reset_index(drop=True)


def descargar_liga(liga, temporada, no_cache=False):
    """Descarga calendario de una liga; se conserva para cargar equipos de clubes."""
    _chequear_dependencia()
    fbref = sd.FBref(leagues=liga, seasons=temporada, no_cache=no_cache)
    return _aplanar_columnas(fbref.read_schedule().reset_index())


def descargar_stats_equipo(liga, temporada, equipo, no_cache=False):
    """Compatibilidad: descarga/lee stats de un equipo sin read_schedule()."""
    _chequear_dependencia()
    fbref = sd.FBref(leagues=liga, seasons=temporada, no_cache=no_cache)
    return construir_historial_equipo_directo(fbref, equipo)


def actualizar_mundial(temporada: str = "2026", equipos: Sequence[str] = None,
                       pausa: float = 0.0, verbose: bool = False,
                       callback=None) -> dict:
    """
    Atajo: actualiza incrementalmente el CSV maestro del Mundial trayendo los
    partidos recientes de FBref. Lo usa tanto la GUI como actualizar_datos.py.

    equipos: lista de selecciones a actualizar. Si es None, actualiza las 48
    (lento). Para actualizar solo las que vas a predecir, pasa esos 2-3 nombres
    y la descarga baja de ~96 peticiones a unas pocas.
    """
    _chequear_dependencia()
    from ligas_config import EQUIPOS_MUNDIAL
    if equipos is None:
        equipos = EQUIPOS_MUNDIAL
    fbref = sd.FBref(leagues="INT-World Cup", seasons=temporada, no_cache=True)
    return actualizar_csv_maestro(fbref, equipos, pausa=pausa, verbose=verbose,
                                  callback=callback)


def actualizar_liga_csv(liga: str, temporada: str, equipos: Sequence[str] = None,
                        no_cache: bool = True, pausa: float = 0.0,
                        verbose: bool = False, callback=None,
                        temporada_previa: str = "auto",
                        min_partidos: int = 5) -> dict:
    """
    Genera o actualiza incrementalmente el CSV maestro de una liga de CLUBES
    (espejo de actualizar_mundial). Construye el historial normalizado de cada
    equipo a partir de shooting/misc y lo fusiona con el CSV existente sin
    duplicar partidos. A partir de ahi la prediccion lee el CSV (offline).

    equipos: si es None, se enumeran del calendario de la liga (read_schedule).
    pausa:   segundos entre equipos (anti-bloqueo de FBref); util en la 1a carga.

    Arranque en frio (cold start): los equipos con menos de `min_partidos` en la
    temporada actual se completan con su historial de `temporada_previa` (misma
    liga), para que el shrinkage no los empuje al promedio. "auto" infiere la
    temporada anterior; None lo desactiva. Nota: un ascendido cuya temporada
    previa fue en OTRA division no tendra datos aqui y se omite.
    """
    import time

    _chequear_dependencia()
    fbref = sd.FBref(leagues=liga, seasons=temporada, no_cache=no_cache)
    if equipos is None:
        sched = _aplanar_columnas(fbref.read_schedule().reset_index())
        equipos = obtener_equipos_liga(sched)
    ruta = ruta_csv_liga(liga, temporada)
    resumen = actualizar_csv_maestro(fbref, equipos, ruta=ruta, pausa=pausa,
                                     verbose=verbose, callback=callback)

    if temporada_previa == "auto":
        temporada_previa = _temporada_anterior(temporada)
    if not temporada_previa:
        return resumen

    # Equipos con pocos partidos en la temporada actual -> traer la anterior.
    df = cargar_historial_csv(ruta)
    conteo = (df.groupby("Team").size()
              if ("Team" in df.columns and not df.empty) else pd.Series(dtype=int))
    pocos = [eq for eq in equipos if int(conteo.get(eq, 0)) < min_partidos]
    if not pocos:
        return resumen

    if verbose:
        print(f"Arranque en frio: {len(pocos)} equipo(s) con <{min_partidos} "
              f"partidos; completando con la temporada {temporada_previa}...")
    fbref_prev = sd.FBref(leagues=liga, seasons=temporada_previa, no_cache=no_cache)
    previos = []
    for i, eq in enumerate(pocos, 1):
        try:
            dprev = construir_historial_equipo_directo(fbref_prev, eq)
            dprev["Team"] = eq
            previos.append(dprev)
        except Exception as exc:
            if verbose:
                print(f"  (previa) sin datos para '{eq}': {exc}")
        if pausa and i < len(pocos):
            time.sleep(pausa)

    if previos:
        maestro = fusionar_historiales(cargar_historial_csv(ruta),
                                       pd.concat(previos, ignore_index=True))
        maestro.to_csv(ruta, index=False, encoding="utf-8")
        resumen["cold_start_equipos"] = pocos
        resumen["filas_con_previa"] = len(maestro)
        if verbose:
            print(f"Cold-start: CSV ampliado a {len(maestro)} filas "
                  f"({len(previos)}/{len(pocos)} equipos con datos previos).")
    return resumen


def construir_historial_equipo(df_liga, nombre_equipo):
    """Filtra y normaliza el historial de un equipo a partir de un DataFrame de
    liga ya cargado (p. ej. la base maestra del Mundial). Devuelve sus partidos
    en el esquema normalizado, ordenados por fecha."""
    if "team" in df_liga.columns:
        equipo_df = df_liga[df_liga["team"] == nombre_equipo].copy()
    elif "Team" in df_liga.columns:
        equipo_df = df_liga[df_liga["Team"] == nombre_equipo].copy()
    else:
        equipo_df = df_liga.copy()
        equipo_df["Team"] = nombre_equipo

    if equipo_df.empty:
        raise ValueError(
            f"No se encontraron partidos para '{nombre_equipo}'. "
            f"Verifica el nombre exacto tal como aparece en FBref."
        )

    mapeo = {
        "date": "Date", "Date": "Date",
        "team": "Team", "Team": "Team",
        "result": "Result", "Result": "Result",
        "opponent": "Opponent", "Opponent": "Opponent",
        "venue": "Venue", "Venue": "Venue",
        "GF": "GF", "gf": "GF",
        "GA": "GA", "ga": "GA",
        "Poss": "Poss", "poss": "Poss",
        "Sh": "Sh", "sh": "Sh",
        "SoT": "SoT", "sot": "SoT",
        "xG": "xG", "xg": "xG",
        "xGA": "xGA", "xga": "xGA",
        "Fls": "Fls", "fls": "Fls",
        "CrdY": "CrdY", "crdy": "CrdY",
        "CrdR": "CrdR", "crdr": "CrdR",
    }
    equipo_df = equipo_df.rename(columns={c: mapeo[c] for c in equipo_df.columns if c in mapeo})

    faltantes = [c for c in ["Date", "Result", "GF", "GA"] if c not in equipo_df.columns]
    if faltantes:
        raise KeyError(
            f"Faltan columnas esperadas tras el mapeo: {faltantes}. "
            f"Columnas disponibles: {list(equipo_df.columns)}."
        )

    for c in ["Poss", "SoT", "xG", "xGA", "Fls", "CrdY", "CrdR"]:
        if c not in equipo_df.columns:
            equipo_df[c] = np.nan if c in ["xG", "xGA"] else 0

    return equipo_df.sort_values("Date").reset_index(drop=True)


def obtener_equipos_liga(df_liga):
    """Devuelve lista ordenada de equipos unicos en el DataFrame de liga."""
    for col in ["team", "Team"]:
        if col in df_liga.columns:
            return sorted(df_liga[col].dropna().unique().tolist())

    equipos = set()
    if "home_team" in df_liga.columns:
        equipos.update(df_liga["home_team"].dropna().unique())
    if "away_team" in df_liga.columns:
        equipos.update(df_liga["away_team"].dropna().unique())
    return sorted(equipos)
