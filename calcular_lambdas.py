"""
Convierte las caracteristicas de cada equipo en los goles esperados (lambda).

Todos los pesos y umbrales viven en PESOS_MODELO (ligas_config.py); aqui solo
estan las formulas. Para recalibrar el modelo, edita el diccionario alli.
"""
from typing import Any, Mapping, Tuple

import pandas as pd

from ligas_config import PESOS_MODELO


def calcular_lambdas(
    features_local: "pd.Series | Mapping[str, Any]",
    features_visitante: "pd.Series | Mapping[str, Any]",
    factor_local: float | None = None,
    neutral: bool = True,
    pesos: Mapping[str, Any] = PESOS_MODELO,
    elo_local: float | None = None,
    elo_visitante: float | None = None,
) -> Tuple[float, float]:
    """
    Calcula los lambdas (goles esperados) de local y visitante.

    neutral=True no aplica ventaja de localia, adecuado para la mayoria de
    partidos de Mundial. neutral=False aplica factor_local.

    Si se pasan elo_local y elo_visitante, se aplica un empuje hacia el favorito
    segun la diferencia de Elo (ponderado por pesos["peso_elo"]).
    """
    if factor_local is None:
        factor_local = pesos["factor_local"]

    lambda_local_base = (
        features_local["xg_favor_adj"] + features_visitante["xg_contra_adj"]
    ) / 2
    lambda_visitante_base = (
        features_visitante["xg_favor_adj"] + features_local["xg_contra_adj"]
    ) / 2

    lambda_local = lambda_local_base if neutral else lambda_local_base * factor_local
    lambda_visitante = lambda_visitante_base

    # Fatiga
    descanso_local = features_local["dias_descanso"]
    descanso_visit = features_visitante["dias_descanso"]
    if (descanso_local < pesos["umbral_descanso_bajo"]
            and descanso_visit > pesos["umbral_descanso_alto"]):
        lambda_local *= pesos["factor_descanso"]
    elif (descanso_visit < pesos["umbral_descanso_bajo"]
            and descanso_local > pesos["umbral_descanso_alto"]):
        lambda_visitante *= pesos["factor_descanso"]

    # Forma reciente
    racha_local = features_local.get("racha_puntos_prom", pesos["default_racha"])
    if racha_local > pesos["umbral_racha_alta"]:
        lambda_local *= pesos["bonus_racha"]
    elif racha_local < pesos["umbral_racha_baja"]:
        lambda_local *= pesos["penal_racha"]

    racha_visit = features_visitante.get("racha_puntos_prom", pesos["default_racha"])
    if racha_visit > pesos["umbral_racha_alta"]:
        lambda_visitante *= pesos["bonus_racha"]
    elif racha_visit < pesos["umbral_racha_baja"]:
        lambda_visitante *= pesos["penal_racha"]

    # Posesion
    if features_local.get("posesion_prom", pesos["default_posesion"]) > pesos["umbral_posesion"]:
        lambda_local *= pesos["bonus_posesion"]
    if features_visitante.get("posesion_prom", pesos["default_posesion"]) > pesos["umbral_posesion"]:
        lambda_visitante *= pesos["bonus_posesion"]

    # Disciplina (un equipo indisciplinado concede algo mas al rival)
    if features_local.get("disciplina_prom", pesos["default_disciplina"]) > pesos["umbral_disciplina"]:
        lambda_visitante *= pesos["bonus_disciplina"]
    if features_visitante.get("disciplina_prom", pesos["default_disciplina"]) > pesos["umbral_disciplina"]:
        lambda_local *= pesos["bonus_disciplina"]

    # Diferencia de fuerza Elo entre ambos equipos (head-to-head). Expectativa
    # Elo estandar: E_local = 1 / (1 + 10**((elo_v - elo_l)/400)). Empujamos los
    # lambdas hacia el favorito de forma simetrica y acotada.
    peso_elo = pesos.get("peso_elo", 0.0)
    if peso_elo and elo_local is not None and elo_visitante is not None:
        e_local = 1.0 / (1.0 + 10 ** ((elo_visitante - elo_local) / 400.0))
        lambda_local *= 1.0 + peso_elo * (e_local - 0.5)
        lambda_visitante *= 1.0 + peso_elo * ((1.0 - e_local) - 0.5)

    return float(lambda_local), float(lambda_visitante)
