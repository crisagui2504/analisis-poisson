"""
Orquestador de la prediccion de UN partido (sin interfaz). La GUI y el motor
Monte Carlo llaman a predecir_partido(). Encadena: historial -> features ->
lambdas -> matriz de Poisson -> probabilidades 1X2 + mercados.
"""
import json
import os
import numpy as np
import pandas as pd

from rutas import data
from ingest_fbref import (
    descargar_liga,
    construir_historial_equipo,
    obtener_equipos_liga,
    construir_historial_equipo_directo,
    cargar_historial_csv,
    existe_csv_maestro,
    ruta_csv_liga,
    _chequear_dependencia,
    sd,
)
from feature_engineering import procesar_equipo, ultima_fila_valida
from calcular_lambdas import calcular_lambdas, _acota
from matriz_poisson import generar_matriz_poisson
from ligas_config import elo_de, factor_local_de, temporada_de, _limpiar_nombre_rival


def _factor_h2h(df, local, visit, peso=0.04, min_partidos=3):
    """
    Historial directo (head-to-head). Busca en la base los cruces entre los dos
    equipos y devuelve (factor_local, factor_visitante) acotado a +/-peso. Si hay
    'paternidad' clara (un equipo gana la mayoria), inclina sutilmente los lambdas.
    """
    if df is None or getattr(df, "empty", True) or not {"Team", "Opponent"} <= set(df.columns):
        return 1.0, 1.0

    def _norm(s):
        return _limpiar_nombre_rival(str(s)).lower()

    nl, nv = _norm(local), _norm(visit)
    # Normalizacion SIMETRICA: ambas columnas pasan por _norm, no solo Opponent.
    # Asi un espacio/mayuscula colado en Team no rompe el match en silencio.
    team_norm = df["Team"].map(_norm)
    opp_norm = df["Opponent"].map(_norm)
    loc_rows = df[(team_norm == nl) & (opp_norm == nv)]
    vis_rows = df[(team_norm == nv) & (opp_norm == nl)]

    # Resultados desde la optica del local (invertimos los del visitante).
    res = list(loc_rows["Result"])
    res += ["W" if r == "L" else "L" if r == "W" else "D" for r in vis_rows["Result"]]
    n = len(res)
    if n < min_partidos:
        return 1.0, 1.0

    tasa_local = sum(1 for r in res if r == "W") / n   # 1 = domina el local
    aj = _acota(peso * (tasa_local - 0.5) * 2, -peso, peso)
    return 1 + aj, 1 - aj


PROMEDIOS_LIGA_PATH = data("promedios_liga.json")
PROMEDIOS_DEFAULT = {"xg_favor": 1.3, "xg_contra": 1.3, "sot": 4.5}


def _cargar_promedios_liga():
    """Carga los promedios del torneo (data/promedios_liga.json) para el
    shrinkage; si no existe, avisa y usa los valores por defecto."""
    if os.path.exists(PROMEDIOS_LIGA_PATH):
        with open(PROMEDIOS_LIGA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    print(
        f"Aviso: no se encontro {PROMEDIOS_LIGA_PATH}. Usando promedios por defecto. "
        "Ejecuta calcular_promedios_liga.py una vez para generarlo desde el cache local."
    )
    return PROMEDIOS_DEFAULT


def predecir_partido(
    equipo_local: str,
    equipo_visitante: str,
    liga: str,
    temporada: str,
    rho: float = -0.05,
    k_shrinkage: int = 5,
    no_cache: bool = False,
    n_window: int = 6,
    neutral: bool | None = None,
) -> dict:
    """
    Predice un partido de principio a fin. Es la funcion central del proyecto:
    la llaman la interfaz y el motor Monte Carlo.

    Pasos: obtiene el historial de cada equipo (CSV maestro para el Mundial, o
    FBref en vivo para clubes) -> features -> lambdas -> matriz de Poisson ->
    probabilidades 1X2 -> mercados. Aplica el factor head-to-head si hay datos.

    Parametros
    ----------
    equipo_local, equipo_visitante : str  Nombres tal como aparecen en la fuente.
    liga : str        "INT-World Cup" o el codigo de liga de FBref.
    temporada : str   Temporada ("2026", "2025-2026"...).
    rho, k_shrinkage, n_window : parametros del modelo.
    no_cache : bool   Fuerza descarga en vivo (ignora el CSV maestro).
    neutral : bool    Sede neutral (sin localia). None = automatico (True Mundial).

    Devuelve un dict con: prob_local/empate/visitante, lambda_*, la matriz, los
    mercados (BTTS, Over/Under, porteria a cero), forma, descanso y metricas.
    """
    df_h2h = None  # base para el historial directo (solo Mundial vía CSV)
    if liga == "INT-World Cup":
        # Ruta preferente: CSV maestro local (100% offline y rapido). Si no
        # existe o se forzo no_cache, caemos a la descarga directa de FBref.
        if existe_csv_maestro() and not no_cache:
            df_maestro = cargar_historial_csv()
            df_h2h = df_maestro
            df_local = construir_historial_equipo(df_maestro, equipo_local)
            df_visitante = construir_historial_equipo(df_maestro, equipo_visitante)
        else:
            _chequear_dependencia()
            fbref = sd.FBref(leagues=liga, seasons=temporada, no_cache=no_cache)
            df_local = construir_historial_equipo_directo(fbref, equipo_local)
            df_visitante = construir_historial_equipo_directo(fbref, equipo_visitante)

        promedios = _cargar_promedios_liga()
        prom_xg_fav = promedios.get("xg_favor", PROMEDIOS_DEFAULT["xg_favor"])
        prom_xg_con = promedios.get("xg_contra", PROMEDIOS_DEFAULT["xg_contra"])
        prom_tiros = promedios.get("sot", PROMEDIOS_DEFAULT["sot"])
        if neutral is None:
            neutral = True
    else:
        ruta_liga = ruta_csv_liga(liga, temporada)
        if os.path.exists(ruta_liga) and not no_cache:
            # Ruta rapida offline: CSV maestro de la liga (espejo del Mundial).
            df_maestro = cargar_historial_csv(ruta_liga)
            df_h2h = df_maestro
            df_local = construir_historial_equipo(df_maestro, equipo_local)
            df_visitante = construir_historial_equipo(df_maestro, equipo_visitante)
            df_promedios = df_maestro
        else:
            # Respaldo: descarga/parseo en vivo desde FBref (lento la 1a vez).
            df_promedios = descargar_liga(liga, temporada, no_cache=no_cache)
            df_local = construir_historial_equipo(df_promedios, equipo_local)
            df_visitante = construir_historial_equipo(df_promedios, equipo_visitante)
        prom_xg_fav = df_promedios["xG"].mean() if "xG" in df_promedios.columns else 1.2
        prom_xg_con = df_promedios["xGA"].mean() if "xGA" in df_promedios.columns else 1.2
        prom_tiros = df_promedios["SoT"].mean() if "SoT" in df_promedios.columns else 4.5
        if neutral is None:
            neutral = False

    feats_local = procesar_equipo(
        df_local,
        prom_xg_fav,
        prom_xg_con,
        prom_tiros,
        n_window=n_window,
        k_shrinkage=k_shrinkage,
    )
    feats_visitante = procesar_equipo(
        df_visitante,
        prom_xg_fav,
        prom_xg_con,
        prom_tiros,
        n_window=n_window,
        k_shrinkage=k_shrinkage,
    )

    fila_local = ultima_fila_valida(feats_local)
    fila_visitante = ultima_fila_valida(feats_visitante)

    if fila_local is None or fila_visitante is None:
        raise ValueError(
            f"No hay suficientes partidos completos para calcular ({equipo_local}: "
            f"{len(df_local)} partidos, {equipo_visitante}: {len(df_visitante)} partidos)."
        )

    lambda_local, lambda_visitante = calcular_lambdas(
        fila_local,
        fila_visitante,
        factor_local=factor_local_de(liga),
        neutral=neutral,
        elo_local=elo_de(equipo_local),
        elo_visitante=elo_de(equipo_visitante),
    )

    # Historial directo (head-to-head): inclina sutilmente si hay paternidad.
    f_loc, f_vis = _factor_h2h(df_h2h, equipo_local, equipo_visitante)
    lambda_local *= f_loc
    lambda_visitante *= f_vis

    return _ensamblar_resultado(lambda_local, lambda_visitante, rho,
                                df_local, df_visitante, fila_local, fila_visitante)


def _ensamblar_resultado(lambda_local, lambda_visitante, rho,
                         df_local, df_visitante, fila_local, fila_visitante) -> dict:
    """
    A partir de los goles esperados ya calculados, construye la matriz de Poisson,
    las probabilidades 1X2, los mercados y el dict de salida que consume la GUI.
    Lo comparten predecir_partido() y predecir_partido_interligas().
    """
    matriz = generar_matriz_poisson(lambda_local, lambda_visitante, rho=rho)

    prob_local = float(np.sum(np.tril(matriz, -1)))
    prob_empate = float(np.sum(np.diag(matriz)))
    prob_visitante = float(np.sum(np.triu(matriz, 1)))

    mercados = calcular_mercados(matriz)

    def _forma(df):
        """Ultimos 5 resultados (W/D/L) del equipo, para los circulos de forma."""
        return list(df.sort_values("Date")["Result"].dropna().tail(5))

    def _num(fila, col):
        """Lee un numero de la fila; 0.0 si falta o es NaN (evita romper la UI)."""
        v = fila.get(col)
        return float(v) if (v is not None and pd.notna(v)) else 0.0

    def _metricas(fila):
        """Las 5 metricas del radar (ataque, defensa, tiros, posesion, disciplina)."""
        return {
            "ataque": _num(fila, "xg_favor_adj"),
            "defensa": _num(fila, "xg_contra_adj"),
            "tiros": _num(fila, "tiros_puerta_adj"),
            "posesion": _num(fila, "posesion_prom"),
            "disciplina": _num(fila, "disciplina_prom"),
        }

    return {
        "lambda_local": lambda_local,
        "lambda_visitante": lambda_visitante,
        "prob_local": prob_local,
        "prob_empate": prob_empate,
        "prob_visitante": prob_visitante,
        "matriz": matriz,
        "df_liga": pd.DataFrame(),
        "forma_local": _forma(df_local),
        "forma_visitante": _forma(df_visitante),
        "descanso_local": _num(fila_local, "dias_descanso"),
        "descanso_visitante": _num(fila_visitante, "dias_descanso"),
        "metricas_local": _metricas(fila_local),
        "metricas_visitante": _metricas(fila_visitante),
        **mercados,
    }


def _historial_y_promedios(equipo, liga, temporada, no_cache=False):
    """
    Carga el historial normalizado de UN equipo y los promedios de su liga (para
    el shrinkage): usa el CSV maestro local (Mundial o liga) si existe, o FBref.
    Devuelve (df_equipo, (prom_xg_favor, prom_xg_contra, prom_tiros)).
    Pensado para predicciones inter-ligas, donde cada equipo viene de una fuente.
    """
    if liga == "INT-World Cup":
        if existe_csv_maestro() and not no_cache:
            df_equipo = construir_historial_equipo(cargar_historial_csv(), equipo)
        else:
            _chequear_dependencia()
            fbref = sd.FBref(leagues=liga, seasons=temporada, no_cache=no_cache)
            df_equipo = construir_historial_equipo_directo(fbref, equipo)
        prom = _cargar_promedios_liga()
        return df_equipo, (
            prom.get("xg_favor", PROMEDIOS_DEFAULT["xg_favor"]),
            prom.get("xg_contra", PROMEDIOS_DEFAULT["xg_contra"]),
            prom.get("sot", PROMEDIOS_DEFAULT["sot"]),
        )

    ruta = ruta_csv_liga(liga, temporada)
    if os.path.exists(ruta) and not no_cache:
        df_liga = cargar_historial_csv(ruta)
    else:
        df_liga = descargar_liga(liga, temporada, no_cache=no_cache)
    df_equipo = construir_historial_equipo(df_liga, equipo)
    return df_equipo, (
        df_liga["xG"].mean() if "xG" in df_liga.columns else 1.2,
        df_liga["xGA"].mean() if "xGA" in df_liga.columns else 1.2,
        df_liga["SoT"].mean() if "SoT" in df_liga.columns else 4.5,
    )


def predecir_partido_interligas(
    equipo_local: str,
    liga_local: str,
    equipo_visitante: str,
    liga_visitante: str,
    temporada_local: str | None = None,
    temporada_visitante: str | None = None,
    rho: float = -0.05,
    k_shrinkage: int = 5,
    no_cache: bool = False,
    n_window: int = 6,
    neutral: bool = True,
) -> dict:
    """
    Predice un cruce entre equipos de DOS ligas distintas (Champions, Mundial de
    Clubes, amistosos...). Cada equipo se evalua con los datos y promedios de SU
    propia liga; el puente de fuerza entre ligas lo aporta el Elo de ClubElo
    (via elo_de), comparable entre ligas europeas. Devuelve el mismo dict que
    predecir_partido().

    neutral=True por defecto (sede neutral). Con neutral=False se aplica la
    localia de la liga del equipo local. No se aplica head-to-head: dos equipos
    de ligas distintas rara vez aparecen enfrentados en los datos de liga.
    """
    if temporada_local is None:
        temporada_local = temporada_de(liga_local)
    if temporada_visitante is None:
        temporada_visitante = temporada_de(liga_visitante)

    df_local, prom_local = _historial_y_promedios(
        equipo_local, liga_local, temporada_local, no_cache)
    df_visitante, prom_visit = _historial_y_promedios(
        equipo_visitante, liga_visitante, temporada_visitante, no_cache)

    feats_local = procesar_equipo(df_local, *prom_local,
                                  n_window=n_window, k_shrinkage=k_shrinkage)
    feats_visitante = procesar_equipo(df_visitante, *prom_visit,
                                      n_window=n_window, k_shrinkage=k_shrinkage)

    fila_local = ultima_fila_valida(feats_local)
    fila_visitante = ultima_fila_valida(feats_visitante)
    if fila_local is None or fila_visitante is None:
        raise ValueError(
            f"No hay suficientes partidos completos para calcular ({equipo_local}: "
            f"{len(df_local)} partidos, {equipo_visitante}: {len(df_visitante)} partidos)."
        )

    lambda_local, lambda_visitante = calcular_lambdas(
        fila_local,
        fila_visitante,
        factor_local=factor_local_de(liga_local),
        neutral=neutral,
        elo_local=elo_de(equipo_local),
        elo_visitante=elo_de(equipo_visitante),
    )

    return _ensamblar_resultado(lambda_local, lambda_visitante, rho,
                                df_local, df_visitante, fila_local, fila_visitante)


def calcular_mercados(matriz: np.ndarray) -> dict:
    """
    Deriva metricas tipo casa de apuestas de la matriz de Poisson, sin tocar la
    matematica base. Filas = goles del local (i), columnas = goles del
    visitante (j).
    """
    n = matriz.shape[0]
    idx_i, idx_j = np.indices((n, n))

    # Ambos anotan (BTTS): ambos marcan >= 1 gol -> excluye fila 0 y columna 0.
    prob_btts = float(matriz[1:, 1:].sum())

    # Over/Under por linea de goles totales (i + j). Mercados "asiaticos".
    total = idx_i + idx_j
    prob_over15 = float(matriz[total > 1].sum())
    prob_under15 = float(matriz[total <= 1].sum())
    prob_over25 = float(matriz[total > 2].sum())
    prob_under25 = float(matriz[total <= 2].sum())
    prob_over35 = float(matriz[total > 3].sum())
    prob_under35 = float(matriz[total <= 3].sum())

    # Porteria a cero (clean sheet): el rival no anota.
    # Local deja la porteria a cero -> visitante marca 0 -> columna 0.
    prob_cs_local = float(matriz[:, 0].sum())
    # Visitante deja la porteria a cero -> local marca 0 -> fila 0.
    prob_cs_visitante = float(matriz[0, :].sum())

    return {
        "prob_btts": prob_btts,
        "prob_over15": prob_over15,
        "prob_under15": prob_under15,
        "prob_over25": prob_over25,
        "prob_under25": prob_under25,
        "prob_over35": prob_over35,
        "prob_under35": prob_under35,
        "prob_cs_local": prob_cs_local,
        "prob_cs_visitante": prob_cs_visitante,
    }


def cargar_equipos(liga: str, temporada: str):
    """
    Lista de equipos para los desplegables (+ el DataFrame de la liga). Usa el
    CSV maestro local si existe (offline e instantaneo); si no, descarga el
    calendario desde FBref.
    """
    ruta = ruta_csv_liga(liga, temporada)
    if os.path.exists(ruta):
        df_liga = cargar_historial_csv(ruta)
    else:
        df_liga = descargar_liga(liga, temporada)
    return obtener_equipos_liga(df_liga), df_liga
