import numpy as np
from scipy.stats import poisson


def correccion_dixon_coles(probabilidades, lambda_l, lambda_v, rho=-0.05):
    probabilidades[0, 0] *= max(0, 1 - lambda_l * lambda_v * rho)
    probabilidades[1, 0] *= max(0, 1 + lambda_v * rho)
    probabilidades[0, 1] *= max(0, 1 + lambda_l * rho)
    probabilidades[1, 1] *= max(0, 1 - rho)
    probabilidades /= probabilidades.sum()
    return probabilidades


def generar_matriz_poisson(lambda_local, lambda_visitante, max_goles=5, rho=-0.05):
    goles = np.arange(0, max_goles + 1)
    prob_local = poisson.pmf(goles, lambda_local)
    prob_visitante = poisson.pmf(goles, lambda_visitante)
    matriz_probs = np.outer(prob_local, prob_visitante)
    if rho != 0:
        matriz_corregida = correccion_dixon_coles(matriz_probs, lambda_local, lambda_visitante, rho=rho)
    else:
        # Normalizamos tambien sin Dixon-Coles: como la Poisson se trunca en
        # max_goles, el producto exterior suma <1 y habia que reescalarlo.
        matriz_corregida = matriz_probs / matriz_probs.sum()
    return matriz_corregida
