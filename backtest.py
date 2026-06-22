"""
Fase 6: Backtest / calibración de rho (Dixon-Coles) y k (shrinkage).

Corrige respecto a la versión anterior:
  1. Data leakage: el promedio de liga usado en el shrinkage ahora se calcula
     SOLO con partidos anteriores a la fecha de corte de cada predicción
     (antes se pasaba un promedio fijo, calculado con toda la temporada,
     lo cual filtraba información "del futuro" al backtest).
  2. NaN-check explícito antes de calcular lambdas.
  3. Conversión de fechas centralizada al inicio, no dispersa en cada función.
  4. Excepciones logueadas en vez de silenciadas con `pass`.
  5. Soporta correr sobre MUCHOS partidos/equipos de liga, no solo un par fijo.
"""
import pandas as pd
import numpy as np
from sklearn.metrics import log_loss

from feature_engineering import procesar_equipo, ultima_fila_valida
from calcular_lambdas import calcular_lambdas
from matriz_poisson import generar_matriz_poisson


def calcular_brier_score(preds, trues):
    """Error cuadrático medio entre probabilidades predichas y resultado real (one-hot)."""
    preds = np.array(preds)
    trues = np.array(trues)
    return np.mean((preds - trues) ** 2)


def df_hasta(df, fecha_corte):
    """Filtra el dataframe para simular que solo vemos datos anteriores al partido."""
    return df[df['Date'] < fecha_corte].copy()


def promedio_liga_hasta(df_liga, fecha_corte, columna):
    """
    Promedio de liga calculado SOLO con partidos jugados antes de fecha_corte.
    Evita el data leakage de usar un promedio de temporada completa para
    predecir un partido de mitad de temporada.
    """
    subset = df_liga[df_liga['Date'] < fecha_corte]
    if subset.empty or columna not in subset.columns:
        return np.nan
    return subset[columna].mean()


def correr_backtest(partidos_historicos, df_liga_completo,
                     rho_test=(-0.1, -0.13, -0.15, -0.2), k_test=(3, 5, 10),
                     min_partidos_previos=5, verbose=False):
    """
    Recorre el histórico simulando predicciones antes de cada partido y compara
    contra el resultado real, para distintas combinaciones de rho y k.

    Parámetros
    ----------
    partidos_historicos : DataFrame con columnas ['Date', 'Team', 'Opponent', 'Result', ...]
        Cada fila es un partido ya jugado que se usará como caso de prueba.
    df_liga_completo : DataFrame con el historial completo de TODOS los equipos de la liga
        (columnas: Date, Team, GF, GA, xG, xGA, SoT, Poss, Fls, CrdY, CrdR, Result).
        Se usa tanto para construir el historial de cada equipo como para los
        promedios de liga dinámicos.
    """
    print("Iniciando backtest...")
    df_liga_completo = df_liga_completo.copy()
    df_liga_completo['Date'] = pd.to_datetime(df_liga_completo['Date'])
    partidos_historicos = partidos_historicos.copy()
    partidos_historicos['Date'] = pd.to_datetime(partidos_historicos['Date'])

    resultados = []

    for r in rho_test:
        for k in k_test:
            log_losses, briers = [], []
            errores = 0

            for _, partido in partidos_historicos.iterrows():
                fecha_corte = partido['Date']
                equipo_local = partido['Team']
                equipo_visitante = partido['Opponent']
                resultado_real_str = partido['Result']  # 'W' = local, 'D' = empate, 'L' = visitante

                df_local = df_hasta(df_liga_completo[df_liga_completo['Team'] == equipo_local], fecha_corte)
                df_vis = df_hasta(df_liga_completo[df_liga_completo['Team'] == equipo_visitante], fecha_corte)

                if len(df_local) < min_partidos_previos or len(df_vis) < min_partidos_previos:
                    continue

                # Promedios de liga calculados SOLO con datos previos a este partido
                prom_xg_fav = promedio_liga_hasta(df_liga_completo, fecha_corte, 'xG')
                prom_xg_con = promedio_liga_hasta(df_liga_completo, fecha_corte, 'xGA')
                prom_tiros = promedio_liga_hasta(df_liga_completo, fecha_corte, 'SoT')

                if any(pd.isna(v) for v in [prom_xg_fav, prom_xg_con, prom_tiros]):
                    continue

                feats_local = procesar_equipo(df_local, prom_xg_fav, prom_xg_con, prom_tiros, k_shrinkage=k)
                feats_vis = procesar_equipo(df_vis, prom_xg_fav, prom_xg_con, prom_tiros, k_shrinkage=k)

                fila_local = ultima_fila_valida(feats_local)
                fila_vis = ultima_fila_valida(feats_vis)

                # NaN-check explícito: si no hay una fila completa para alguno de los dos
                # equipos, se descarta el partido en vez de dejar pasar NaN silenciosamente
                # (comparaciones tipo `NaN < 4` no lanzan error en Python, devuelven False).
                if fila_local is None or fila_vis is None:
                    continue

                try:
                    lam_l, lam_v = calcular_lambdas(fila_local, fila_vis)
                    matriz = generar_matriz_poisson(lam_l, lam_v, rho=r)

                    prob_local = float(np.sum(np.tril(matriz, -1)))
                    prob_empate = float(np.sum(np.diag(matriz)))
                    prob_visitante = float(np.sum(np.triu(matriz, 1)))
                    probs = [prob_local, prob_empate, prob_visitante]

                    # sklearn.log_loss espera la etiqueta real como índice de clase
                    # (0/1/2), no en formato one-hot -- ese era el bug.
                    clase_real = (
                        0 if resultado_real_str == 'W'
                        else 1 if resultado_real_str == 'D'
                        else 2
                    )
                    real_onehot = [1, 0, 0] if clase_real == 0 else [0, 1, 0] if clase_real == 1 else [0, 0, 1]

                    loss = log_loss([clase_real], [probs], labels=[0, 1, 2])
                    brier = calcular_brier_score(probs, real_onehot)

                    log_losses.append(loss)
                    briers.append(brier)

                except Exception as e:
                    errores += 1
                    if verbose:
                        print(f"  [rho={r}, k={k}] error en partido {equipo_local} vs "
                              f"{equipo_visitante} ({fecha_corte.date()}): {e}")
                    continue

            if log_losses:
                resultados.append({
                    'rho': r, 'k': k,
                    'log_loss': np.mean(log_losses),
                    'brier_score': np.mean(briers),
                    'n_partidos_validos': len(log_losses),
                    'n_errores': errores,
                })
            elif verbose:
                print(f"  [rho={r}, k={k}] sin partidos válidos (errores: {errores})")

    df_resultados = pd.DataFrame(resultados)
    if not df_resultados.empty:
        df_resultados = df_resultados.sort_values(by='log_loss')
        print("\nMejores combinaciones de parámetros (menor log_loss primero):")
        print(df_resultados.head(5).to_string(index=False))
        df_resultados.to_csv("resultados_backtest.csv", index=False)
        print("\nResultados completos guardados en resultados_backtest.csv")
    else:
        print("No se calcularon resultados. Revisar formato de datos y columnas requeridas.")

    return df_resultados


if __name__ == "__main__":
    print("Módulo de backtest listo.")
    print("Uso esperado:")
    print("  correr_backtest(partidos_historicos_df, df_liga_completo_df)")
    print("Donde partidos_historicos_df tiene una fila por partido a evaluar (Team, Opponent, Date, Result)")
    print("y df_liga_completo_df tiene el historial de TODOS los equipos de la liga.")
