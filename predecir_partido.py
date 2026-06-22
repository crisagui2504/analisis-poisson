"""
Logica de prediccion sin interfaz. La GUI llama a predecir_partido().
"""
import json
import os
import numpy as np
import pandas as pd

from ingest_fbref import (
    descargar_liga,
    construir_historial_equipo,
    obtener_equipos_liga,
    construir_historial_equipo_directo,
    cargar_historial_csv,
    existe_csv_maestro,
    _chequear_dependencia,
    sd,
)
from feature_engineering import procesar_equipo, ultima_fila_valida
from calcular_lambdas import calcular_lambdas
from matriz_poisson import generar_matriz_poisson
from ligas_config import elo_de


PROMEDIOS_LIGA_PATH = "promedios_liga.json"
PROMEDIOS_DEFAULT = {"xg_favor": 1.3, "xg_contra": 1.3, "sot": 4.5}


def _cargar_promedios_liga():
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
    rho: float = -0.10,
    k_shrinkage: int = 5,
    no_cache: bool = False,
    n_window: int = 6,
    neutral: bool | None = None,
) -> dict:
    if liga == "INT-World Cup":
        # Ruta preferente: CSV maestro local (100% offline y rapido). Si no
        # existe o se forzo no_cache, caemos a la descarga directa de FBref.
        if existe_csv_maestro() and not no_cache:
            df_maestro = cargar_historial_csv()
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
        df_liga = descargar_liga(liga, temporada, no_cache=no_cache)
        prom_xg_fav = df_liga["xG"].mean() if "xG" in df_liga.columns else 1.2
        prom_xg_con = df_liga["xGA"].mean() if "xGA" in df_liga.columns else 1.2
        prom_tiros = df_liga["SoT"].mean() if "SoT" in df_liga.columns else 4.5
        df_local = construir_historial_equipo(df_liga, equipo_local)
        df_visitante = construir_historial_equipo(df_liga, equipo_visitante)
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
        neutral=neutral,
        elo_local=elo_de(equipo_local),
        elo_visitante=elo_de(equipo_visitante),
    )
    matriz = generar_matriz_poisson(lambda_local, lambda_visitante, rho=rho)

    prob_local = float(np.sum(np.tril(matriz, -1)))
    prob_empate = float(np.sum(np.diag(matriz)))
    prob_visitante = float(np.sum(np.triu(matriz, 1)))

    mercados = calcular_mercados(matriz)

    return {
        "lambda_local": lambda_local,
        "lambda_visitante": lambda_visitante,
        "prob_local": prob_local,
        "prob_empate": prob_empate,
        "prob_visitante": prob_visitante,
        "matriz": matriz,
        "df_liga": pd.DataFrame(),
        **mercados,
    }


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

    # Over/Under 2.5: suma de goles (i + j) mayor que 2.
    prob_over25 = float(matriz[(idx_i + idx_j) > 2].sum())
    prob_under25 = float(matriz[(idx_i + idx_j) <= 2].sum())

    # Porteria a cero (clean sheet): el rival no anota.
    # Local deja la porteria a cero -> visitante marca 0 -> columna 0.
    prob_cs_local = float(matriz[:, 0].sum())
    # Visitante deja la porteria a cero -> local marca 0 -> fila 0.
    prob_cs_visitante = float(matriz[0, :].sum())

    return {
        "prob_btts": prob_btts,
        "prob_over25": prob_over25,
        "prob_under25": prob_under25,
        "prob_cs_local": prob_cs_local,
        "prob_cs_visitante": prob_cs_visitante,
    }


def cargar_equipos(liga: str, temporada: str):
    """Descarga la liga y devuelve la lista de equipos para los desplegables."""
    df_liga = descargar_liga(liga, temporada)
    return obtener_equipos_liga(df_liga), df_liga
