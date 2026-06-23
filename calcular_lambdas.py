"""
Convierte las caracteristicas de cada equipo en los goles esperados (lambda).

Todos los pesos y umbrales viven en PESOS_MODELO (ligas_config.py); aqui solo
estan las formulas. Para recalibrar el modelo, edita el diccionario alli.
"""
from typing import Any, Mapping, Tuple

import pandas as pd

from ligas_config import PESOS_MODELO, ELO_REFERENCIA


def _acota(x, lo, hi):
    return max(lo, min(hi, x))


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

    # Tiros a puerta: ajuste CONTINUO (no escalon). Un equipo que remata mas que
    # la media gana algo de lambda, proporcional a cuanto supera la media.
    def _ajuste_tiros(feats, lam):
        t = feats.get("tiros_puerta_adj")
        if t is None or pd.isna(t) or t <= 0:
            return lam
        ratio = _acota(t / pesos["default_tiros"], 0.5, 1.5)
        return lam * (1 + (ratio - 1) * pesos["peso_tiros"])

    lambda_local = _ajuste_tiros(features_local, lambda_local)
    lambda_visitante = _ajuste_tiros(features_visitante, lambda_visitante)

    # Fuerza del Calendario (SoS): stats logradas contra rivales fuertes valen
    # mas; contra debiles, menos. Acotado a +/-3%.
    def _ajuste_sos(feats, lam):
        sos = feats.get("sos_prom")
        if sos is None or pd.isna(sos):
            return lam
        aj = _acota(pesos["peso_sos"] * (sos - ELO_REFERENCIA) / 100.0, -0.03, 0.03)
        return lam * (1 + aj)

    lambda_local = _ajuste_sos(features_local, lambda_local)
    lambda_visitante = _ajuste_sos(features_visitante, lambda_visitante)

    # Tasa de conversion: premia al hiper-efectivo, penaliza al inofensivo.
    def _ajuste_conversion(feats, lam):
        c = feats.get("conversion_prom")
        if c is None or pd.isna(c) or c <= 0:
            return lam
        ratio = c / pesos["default_conversion"]
        if ratio > pesos["umbral_conversion"]:
            return lam * pesos["bonus_conversion"]
        if ratio < (2 - pesos["umbral_conversion"]):
            return lam * (2 - pesos["bonus_conversion"])
        return lam

    lambda_local = _ajuste_conversion(features_local, lambda_local)
    lambda_visitante = _ajuste_conversion(features_visitante, lambda_visitante)

    # Diferencial de xG (xGD): bono de dominio, acotado a +/-3%.
    def _ajuste_xgd(feats, lam):
        x = feats.get("xgd_prom")
        if x is None or pd.isna(x):
            return lam
        return lam * (1 + _acota(pesos["peso_xgd"] * x, -0.03, 0.03))

    lambda_local = _ajuste_xgd(features_local, lambda_local)
    lambda_visitante = _ajuste_xgd(features_visitante, lambda_visitante)

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
