"""
Backtest del modelo contra las CUOTAS REALES del mercado (Football-Data.co.uk).

Mide si el modelo Poisson/Dixon-Coles le gana o iguala a las casas de apuestas:
  - Compara su log-loss / Brier / acierto contra las cuotas de cierre de Pinnacle
    (la casa más "sharp"), que son el patrón a vencer.
  - Simula el ROI de apostar solo cuando el modelo detecta "valor".

Clave: el CSV de Football-Data ya trae los goles de cada partido, así que el
historial de cada equipo se construye del MISMO archivo. 100% offline tras la
descarga, sin FBref ni mapeo de nombres. Backtest SIN fuga de datos: cada partido
se predice usando solo los partidos anteriores.

Uso:
    py -3.11 backtest_cuotas.py            # Premier League 2024-25
    py -3.11 backtest_cuotas.py SP1 2425   # La Liga 2024-25
"""
# ── Bootstrap de rutas: permite ejecutar este script directamente ──
import os as _os, sys as _sys
_SRC = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _sub in ("", "modelo", "datos", "interfaz", "analisis"):
    _ruta = _os.path.join(_SRC, _sub)
    if _ruta not in _sys.path:
        _sys.path.insert(0, _ruta)

import sys

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss

from feature_engineering import procesar_equipo, ultima_fila_valida
from calcular_lambdas import calcular_lambdas
from matriz_poisson import generar_matriz_poisson

# Códigos de liga de Football-Data.co.uk
LIGAS_FD = {
    "E0": "Premier League (Inglaterra)", "SP1": "La Liga (España)",
    "I1": "Serie A (Italia)", "D1": "Bundesliga (Alemania)", "F1": "Ligue 1 (Francia)",
}
BASE_URL = "https://www.football-data.co.uk/mmz4281"


def descargar_cuotas(codigo: str = "E0", temporada: str = "2425") -> pd.DataFrame:
    """Descarga el CSV de resultados + cuotas de una liga/temporada."""
    url = f"{BASE_URL}/{temporada}/{codigo}.csv"
    df = pd.read_csv(url)
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    return df.dropna(subset=["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"])


def historial_desde_cuotas(df: pd.DataFrame) -> pd.DataFrame:
    """Construye el historial por equipo (esquema del modelo) desde el CSV."""
    filas = []
    for _, m in df.iterrows():
        gh, ga = int(m["FTHG"]), int(m["FTAG"])
        base = {"Poss": np.nan, "Sh": np.nan, "SoT": np.nan, "xG": np.nan,
                "xGA": np.nan, "Fls": np.nan, "CrdY": 0, "CrdR": 0}
        filas.append({"Date": m["Date"], "Team": m["HomeTeam"], "Opponent": m["AwayTeam"],
                      "Venue": "Home", "Result": "W" if gh > ga else "D" if gh == ga else "L",
                      "GF": gh, "GA": ga, **base})
        filas.append({"Date": m["Date"], "Team": m["AwayTeam"], "Opponent": m["HomeTeam"],
                      "Venue": "Away", "Result": "W" if ga > gh else "D" if gh == ga else "L",
                      "GF": ga, "GA": gh, **base})
    return pd.DataFrame(filas).sort_values("Date").reset_index(drop=True)


def _devig(oh, od, oa):
    """Cuotas decimales -> probabilidades sin margen de la casa (de-vig)."""
    if any(pd.isna(x) or x <= 1 for x in (oh, od, oa)):
        return None
    imp = np.array([1 / oh, 1 / od, 1 / oa])
    return imp / imp.sum()


def _cuotas_cierre(m):
    """Cuotas de cierre por prioridad: Pinnacle -> Bet365 -> promedio."""
    for h, d, a in [("PSCH", "PSCD", "PSCA"), ("B365CH", "B365CD", "B365CA"),
                    ("AvgCH", "AvgCD", "AvgCA"), ("B365H", "B365D", "B365A")]:
        if all(c in m and not pd.isna(m[c]) for c in (h, d, a)):
            return float(m[h]), float(m[d]), float(m[a])
    return None


def correr(df_cuotas, rho=-0.05, k=2, min_previos=5, suavizado="ewm", ewm_span=10,
           splits=False, half_life_dias=180):  # rho/k calibrados; splits off (empeoran)
    """
    Predice cada partido sin fuga de datos y devuelve arrays alineados:
    probs_modelo, probs_mercado, cuotas, y (0=local,1=empate,2=visitante).
    """
    hist = historial_desde_cuotas(df_cuotas)
    df = df_cuotas.sort_values("Date").reset_index(drop=True)

    pm_modelo, pm_mercado, cuotas, ys = [], [], [], []
    for _, m in df.iterrows():
        oc = _cuotas_cierre(m)
        merc = _devig(*oc) if oc else None
        if merc is None:
            continue

        local, visit, fecha = m["HomeTeam"], m["AwayTeam"], m["Date"]
        h_loc = hist[(hist["Team"] == local) & (hist["Date"] < fecha)]
        h_vis = hist[(hist["Team"] == visit) & (hist["Date"] < fecha)]
        if len(h_loc) < min_previos or len(h_vis) < min_previos:
            continue

        prom_gf = hist[hist["Date"] < fecha]["GF"].mean()  # ~media de goles de local
        v_loc, v_vis = ("Home", "Away") if splits else (None, None)
        f_loc = ultima_fila_valida(procesar_equipo(
            h_loc, prom_gf, prom_gf, 4.5, k_shrinkage=k, suavizado=suavizado,
            ewm_span=ewm_span, venue=v_loc, half_life_dias=half_life_dias))
        f_vis = ultima_fila_valida(procesar_equipo(
            h_vis, prom_gf, prom_gf, 4.5, k_shrinkage=k, suavizado=suavizado,
            ewm_span=ewm_span, venue=v_vis, half_life_dias=half_life_dias))
        if f_loc is None or f_vis is None:
            continue

        # Clubes: SÍ aplica ventaja de localía (neutral=False), sin Elo.
        lam_l, lam_v = calcular_lambdas(f_loc, f_vis, neutral=False)
        mat = generar_matriz_poisson(lam_l, lam_v, rho=rho)
        probs = [float(np.sum(np.tril(mat, -1))), float(np.sum(np.diag(mat))),
                 float(np.sum(np.triu(mat, 1)))]

        y = 0 if m["FTR"] == "H" else 1 if m["FTR"] == "D" else 2
        pm_modelo.append(probs)
        pm_mercado.append(list(merc))
        cuotas.append(oc)
        ys.append(y)

    return (np.array(pm_modelo), np.array(pm_mercado),
            np.array(cuotas), np.array(ys))


def calibrar(dfs, rhos=(-0.20, -0.15, -0.13, -0.10, -0.05, 0.0),
             ks=(3, 5, 8, 12), min_previos=5):
    """
    Barrido de rho y k sobre uno o varios DataFrames de cuotas (varias ligas
    para no sobreajustar). Minimiza el log_loss contra los RESULTADOS reales,
    sin fuga de datos. Las lambdas dependen de k, así que se calculan una sola
    vez por k y luego se reusa al barrer rho (barato). Devuelve un DataFrame
    ordenado por log_loss.
    """
    datos = {k: [] for k in ks}  # k -> [(lam_l, lam_v, y)]
    for df in dfs:
        hist = historial_desde_cuotas(df)
        dfo = df.sort_values("Date").reset_index(drop=True)
        for _, m in dfo.iterrows():
            local, visit, fecha = m["HomeTeam"], m["AwayTeam"], m["Date"]
            h_loc = hist[(hist["Team"] == local) & (hist["Date"] < fecha)]
            h_vis = hist[(hist["Team"] == visit) & (hist["Date"] < fecha)]
            if len(h_loc) < min_previos or len(h_vis) < min_previos:
                continue
            prom = hist[hist["Date"] < fecha]["GF"].mean()
            y = 0 if m["FTR"] == "H" else 1 if m["FTR"] == "D" else 2
            for k in ks:
                f_loc = ultima_fila_valida(procesar_equipo(h_loc, prom, prom, 4.5, k_shrinkage=k))
                f_vis = ultima_fila_valida(procesar_equipo(h_vis, prom, prom, 4.5, k_shrinkage=k))
                if f_loc is None or f_vis is None:
                    continue
                lam_l, lam_v = calcular_lambdas(f_loc, f_vis, neutral=False)
                datos[k].append((lam_l, lam_v, y))

    filas = []
    for rho in rhos:
        for k in ks:
            probs, ys = [], []
            for lam_l, lam_v, y in datos[k]:
                mat = generar_matriz_poisson(lam_l, lam_v, rho=rho)
                probs.append([float(np.sum(np.tril(mat, -1))), float(np.sum(np.diag(mat))),
                              float(np.sum(np.triu(mat, 1)))])
                ys.append(y)
            if probs:
                filas.append({"rho": rho, "k": k, "n": len(ys),
                              "log_loss": log_loss(ys, probs, labels=[0, 1, 2])})
    return pd.DataFrame(filas).sort_values("log_loss").reset_index(drop=True)


def metricas(probs, y):
    """Calidad de unas probabilidades vs el resultado real: log_loss, Brier, RPS
    y % de acierto. `probs` es Nx3 (local/empate/visitante), `y` el indice real.

    RPS (Ranked Probability Score) es la metrica idonea para 1X2 porque respeta
    el ORDEN de los resultados: equivocarse prediciendo 'visitante' cuando gana el
    'local' penaliza mas que predecir 'empate'. Menor = mejor (0 = perfecto)."""
    probs = np.asarray(probs, dtype=float)
    onehot = np.eye(3)[y]
    cum_p = np.cumsum(probs, axis=1)
    cum_o = np.cumsum(onehot, axis=1)
    rps = float(np.mean(np.sum((cum_p - cum_o) ** 2, axis=1) / 2))
    return {"log_loss": log_loss(y, probs, labels=[0, 1, 2]),
            "brier": float(np.mean(np.sum((probs - onehot) ** 2, axis=1))),
            "rps": rps,
            "acierto": float(np.mean(np.argmax(probs, axis=1) == y))}


def simular_roi(probs, cuotas, y, umbral=0.05, stake=1.0):
    """Apuesta 1 unidad a cada resultado donde prob_modelo*cuota > 1+umbral."""
    ganancia, n = 0.0, 0
    for p, o, real in zip(probs, cuotas, y):
        for k in range(3):
            if p[k] * o[k] > 1 + umbral:  # valor esperado positivo
                n += 1
                ganancia += (o[k] - 1) * stake if real == k else -stake
    roi = (ganancia / (n * stake)) if n else 0.0
    return {"apuestas": n, "ganancia": ganancia, "roi": roi}


def barrer_half_life(df_cuotas, half_lives=(45, 90, 180, 365),
                     rho=-0.05, k=2, min_previos=5, incluir_ewm=True):
    """
    Compara el suavizado por tiempo (Dixon-Coles) con varias vidas medias,
    midiendo el RPS contra los resultados reales (sin fuga de datos). Incluye el
    EWM como linea base. Devuelve un DataFrame ordenado por RPS (menor = mejor).

    Elige el half_life con menor RPS; si ninguno bate al EWM, tu suavizado actual
    ya era suficiente.
    """
    filas = []
    configs = ([("ewm", None)] if incluir_ewm else []) + \
              [("tiempo", hl) for hl in half_lives]
    for suav, hl in configs:
        kw = {"half_life_dias": hl} if hl is not None else {}
        pm, _, _, y = correr(df_cuotas, rho=rho, k=k, min_previos=min_previos,
                             suavizado=suav, **kw)
        if len(y):
            m = metricas(pm, y)
            filas.append({"suavizado": suav, "half_life": hl, "n": len(y),
                          "rps": m["rps"], "log_loss": m["log_loss"],
                          "acierto": m["acierto"]})
    return pd.DataFrame(filas).sort_values("rps").reset_index(drop=True)


if __name__ == "__main__":
    codigo = sys.argv[1] if len(sys.argv) > 1 else "E0"
    temporada = sys.argv[2] if len(sys.argv) > 2 else "2425"
    print(f"Liga: {LIGAS_FD.get(codigo, codigo)} · temporada {temporada}")

    df = descargar_cuotas(codigo, temporada)
    print(f"Partidos descargados: {len(df)}")

    pm, mk, od, y = correr(df)
    print(f"Partidos evaluados (con historial suficiente): {len(y)}\n")

    mo, me = metricas(pm, y), metricas(mk, y)
    print(f"{'':12}{'log_loss':>10}{'brier':>9}{'rps':>9}{'acierto':>9}")
    print(f"{'MERCADO':12}{me['log_loss']:>10.4f}{me['brier']:>9.4f}{me['rps']:>9.4f}{me['acierto']*100:>8.1f}%")
    print(f"{'MODELO':12}{mo['log_loss']:>10.4f}{mo['brier']:>9.4f}{mo['rps']:>9.4f}{mo['acierto']*100:>8.1f}%")
    print("  (menor log_loss/brier/rps = mejor; el mercado es muy dificil de batir)\n")

    roi = simular_roi(pm, od, y)
    print(f"Simulador de ROI (apostando al 'valor' del modelo):")
    print(f"  apuestas con valor: {roi['apuestas']}")
    print(f"  ganancia neta: {roi['ganancia']:+.2f} unidades")
    print(f"  ROI: {roi['roi']*100:+.1f}%")
    print("  (ROI>0 sería ganarle al mercado; lo normal es negativo por el margen)")

    # Barrido opcional de half_life (suavizado por tiempo) por RPS:
    #   py -3.11 src/analisis/backtest_cuotas.py E0 2425 barrido
    if "barrido" in sys.argv:
        print("\nBarrido de half_life (suavizado por tiempo) vs EWM, por RPS:")
        tabla = barrer_half_life(df)
        print(f"{'suavizado':12}{'half_life':>10}{'rps':>9}{'log_loss':>10}{'acierto':>9}")
        for _, r in tabla.iterrows():
            hl = "-" if pd.isna(r["half_life"]) else f"{int(r['half_life'])}d"
            print(f"{r['suavizado']:12}{hl:>10}{r['rps']:>9.4f}"
                  f"{r['log_loss']:>10.4f}{r['acierto']*100:>8.1f}%")
        print("  (menor RPS = mejor; si ninguno bate al EWM, el EWM ya era suficiente)")
