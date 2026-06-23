"""
Simulacion de Monte Carlo del Mundial 2026.

Juega el torneo completo miles de veces (fase de grupos + eliminatorias) usando
las probabilidades del modelo Poisson/Dixon-Coles, y estima la probabilidad de
que cada seleccion sea campeona.

Uso:
    py -3.11 montecarlo_mundial.py [n_simulaciones] [semilla]
    py -3.11 montecarlo_mundial.py 10000

Optimizacion clave: las caracteristicas de cada equipo se calculan UNA sola vez
y la distribucion de marcadores de cada cruce se memoriza. Asi millones de
partidos simulados se resuelven en segundos, sin volver a tocar el CSV ni la red.
"""
import sys

import numpy as np
import pandas as pd

from ligas_config import GRUPOS_MUNDIAL, cargar_grupos, elo_de
from ingest_fbref import cargar_historial_csv, construir_historial_equipo, existe_csv_maestro
from feature_engineering import procesar_equipo, ultima_fila_valida
from calcular_lambdas import calcular_lambdas
from matriz_poisson import generar_matriz_poisson
from predecir_partido import _cargar_promedios_liga

RONDAS = ["16avos", "Octavos", "Cuartos", "Semis", "Final", "Campeon"]
SALIDA_CSV = "montecarlo_resultados.csv"


def construir_modelo(grupos=None, rho: float = -0.05, k_shrinkage: int = 5):
    """Calcula la fila de features y el Elo de cada seleccion UNA sola vez."""
    if not existe_csv_maestro():
        raise SystemExit(
            "Falta base_mundial_2026.csv. Ejecuta descargar_datos.py "
            "(o actualizar_datos.py) para generarlo."
        )

    if grupos is None:
        grupos = cargar_grupos()
    df = cargar_historial_csv()
    prom = _cargar_promedios_liga()
    feats, elos = {}, {}
    faltantes = []
    for equipos in grupos.values():
        for eq in equipos:
            if eq in feats:
                continue
            try:
                hist = construir_historial_equipo(df, eq)
                fila = ultima_fila_valida(
                    procesar_equipo(hist, prom["xg_favor"], prom["xg_contra"],
                                    prom["sot"], k_shrinkage=k_shrinkage)
                )
            except Exception:
                fila = None
            if fila is None:
                faltantes.append(eq)
            else:
                feats[eq] = fila
                elos[eq] = elo_de(eq)
    if faltantes:
        print(f"Aviso: sin datos suficientes para {faltantes}. Se usara Elo de respaldo.")
    return feats, elos, rho


def crear_sampler(feats, elos, rho):
    """Devuelve dist(a, b) -> distribucion acumulada de marcadores (memorizada)."""
    cache = {}

    def dist(a, b):
        clave = (a, b)
        if clave not in cache:
            if a in feats and b in feats:
                ll, lv = calcular_lambdas(
                    feats[a], feats[b], neutral=True,
                    elo_local=elos.get(a), elo_visitante=elos.get(b),
                )
            else:
                # Respaldo si falta historial: lambdas a partir del Elo puro.
                ea, eb = elo_de(a), elo_de(b)
                e = 1.0 / (1.0 + 10 ** ((eb - ea) / 400.0))
                ll, lv = 0.8 + e, 0.8 + (1 - e)
            matriz = generar_matriz_poisson(ll, lv, rho=rho)
            flat = matriz.ravel()
            cache[clave] = (np.cumsum(flat), matriz.shape[0])
        return cache[clave]

    return dist


def _marcador(rng, dist, a, b):
    acum, n = dist(a, b)
    idx = int(np.searchsorted(acum, rng.random() * acum[-1]))
    return divmod(idx, n)


def _ganador(rng, dist, a, b):
    gi, gj = _marcador(rng, dist, a, b)
    if gi > gj:
        return a
    if gj > gi:
        return b
    return a if rng.random() < 0.5 else b  # penales


def simular_torneo(rng, dist, grupos):
    """Juega un Mundial completo y devuelve dict equipo -> etapa mas avanzada."""
    primeros_segundos, terceros = [], []

    for equipos in grupos.values():
        pts = {t: 0 for t in equipos}
        gd = {t: 0 for t in equipos}
        gf = {t: 0 for t in equipos}
        for i in range(len(equipos)):
            for j in range(i + 1, len(equipos)):
                a, b = equipos[i], equipos[j]
                gi, gj = _marcador(rng, dist, a, b)
                gf[a] += gi; gf[b] += gj
                gd[a] += gi - gj; gd[b] += gj - gi
                if gi > gj:
                    pts[a] += 3
                elif gj > gi:
                    pts[b] += 3
                else:
                    pts[a] += 1; pts[b] += 1
        clasif = sorted(equipos, key=lambda t: (pts[t], gd[t], gf[t], rng.random()),
                        reverse=True)
        primeros_segundos.append((clasif[0], pts[clasif[0]], gd[clasif[0]], gf[clasif[0]]))
        primeros_segundos.append((clasif[1], pts[clasif[1]], gd[clasif[1]], gf[clasif[1]]))
        terceros.append((clasif[2], pts[clasif[2]], gd[clasif[2]], gf[clasif[2]]))

    # 8 mejores terceros completan los 32 clasificados.
    terceros.sort(key=lambda x: (x[1], x[2], x[3], rng.random()), reverse=True)
    clasificados = primeros_segundos + terceros[:8]
    clasificados.sort(key=lambda x: (x[1], x[2], x[3], rng.random()), reverse=True)

    etapa = {}
    ronda = [c[0] for c in clasificados]  # 32 sembrados
    for t in ronda:
        etapa[t] = "16avos"

    nombre_idx = 1  # siguiente etiqueta tras 16avos
    while len(ronda) > 1:
        siguiente = []
        for i in range(len(ronda) // 2):
            a, b = ronda[i], ronda[len(ronda) - 1 - i]
            g = _ganador(rng, dist, a, b)
            siguiente.append(g)
            etapa[g] = RONDAS[nombre_idx]
        ronda = siguiente
        nombre_idx += 1
    return etapa


def correr(n_sim: int = 10000, semilla: int = 42, grupos=None) -> pd.DataFrame:
    if grupos is None:
        grupos = cargar_grupos()
    feats, elos, rho = construir_modelo(grupos)
    dist = crear_sampler(feats, elos, rho)
    rng = np.random.default_rng(semilla)

    equipos = [t for g in grupos.values() for t in g]
    cont = {t: {r: 0 for r in RONDAS} for t in equipos}

    for _ in range(n_sim):
        etapa = simular_torneo(rng, dist, grupos)
        for t, e in etapa.items():
            # Llegar a la etapa e implica haber alcanzado todas las rondas
            # previas (un semifinalista tambien jugo cuartos, etc.), pero NO las
            # posteriores. Acreditamos las rondas con indice <= indice de e.
            ie = RONDAS.index(e)
            for r in RONDAS:
                if RONDAS.index(r) <= ie:
                    cont[t][r] += 1

    filas = []
    for t in equipos:
        filas.append({
            "Equipo": t,
            "Campeon": cont[t]["Campeon"],
            "Campeon_%": round(100 * cont[t]["Campeon"] / n_sim, 2),
            "Final_%": round(100 * cont[t]["Final"] / n_sim, 2),
            "Semis_%": round(100 * cont[t]["Semis"] / n_sim, 2),
            "Cuartos_%": round(100 * cont[t]["Cuartos"] / n_sim, 2),
        })
    df = pd.DataFrame(filas).sort_values("Campeon", ascending=False).reset_index(drop=True)
    df.to_csv(SALIDA_CSV, index=False, encoding="utf-8")
    return df


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42

    print(f"Simulando el Mundial 2026 {n:,} veces (semilla={seed})...")
    df = correr(n_sim=n, semilla=seed)

    print(f"\nTop 12 candidatos al titulo ({n:,} simulaciones):")
    print(f"  {'Equipo':<16}{'Campeon':>9}{'Final':>8}{'Semis':>8}")
    for _, r in df.head(12).iterrows():
        print(f"  {r['Equipo']:<16}{r['Campeon_%']:>8.1f}%{r['Final_%']:>7.1f}%{r['Semis_%']:>7.1f}%")
    print(f"\nResultados completos guardados en '{SALIDA_CSV}'.")
