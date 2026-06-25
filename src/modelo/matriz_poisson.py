"""
Construye la matriz de probabilidad de marcadores exactos a partir de los goles
esperados (lambda) de cada equipo, con la correccion Dixon-Coles.
"""
import numpy as np
from scipy.stats import poisson


def correccion_dixon_coles(probabilidades, lambda_l, lambda_v, rho=-0.05):
    """
    Aplica la correccion Dixon-Coles a la matriz de Poisson.

    Reajusta las celdas de pocos goles —(0,0), (1,0), (0,1), (1,1)— para modelar
    la correlacion que el Poisson puro ignora (en el futbol real hay mas empates
    bajos de lo que predice la independencia). Renormaliza para que sume 1.

    Parametros
    ----------
    probabilidades : np.ndarray  Matriz NxN del producto de dos Poisson.
    lambda_l, lambda_v : float   Goles esperados de local y visitante.
    rho : float                  Fuerza de la correccion (negativo = mas empates bajos).

    Devuelve la misma matriz corregida y normalizada.
    """
    probabilidades[0, 0] *= max(0, 1 - lambda_l * lambda_v * rho)
    probabilidades[1, 0] *= max(0, 1 + lambda_v * rho)
    probabilidades[0, 1] *= max(0, 1 + lambda_l * rho)
    probabilidades[1, 1] *= max(0, 1 - rho)
    probabilidades /= probabilidades.sum()
    return probabilidades


def generar_matriz_poisson(lambda_local, lambda_visitante, max_goles=5, rho=-0.05):
    """
    Genera la matriz (max_goles+1)x(max_goles+1) con la probabilidad de cada
    marcador exacto. Filas = goles del local (i), columnas = del visitante (j).

    Multiplica dos distribuciones de Poisson independientes (una por equipo) y
    aplica la correccion Dixon-Coles si rho != 0. La matriz siempre suma 1.

    Parametros
    ----------
    lambda_local, lambda_visitante : float  Goles esperados de cada equipo.
    max_goles : int   Tope de goles por equipo (5 -> matriz 6x6).
    rho : float       Parametro Dixon-Coles.

    Devuelve la matriz np.ndarray normalizada.
    """
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
