"""
Fases 1-3: ingeniería de características, ponderación por fuerza del rival
(Elo / Strength of Schedule) y shrinkage.
"""
import pandas as pd
import numpy as np

from ligas_config import elo_de, ELO_REFERENCIA


def aplicar_shrinkage(promedio_equipo, promedio_liga, n_partidos, k=5):
    """
    Regulariza el promedio de un equipo hacia el promedio de la liga/torneo.

    Mezcla ambos ponderando por el numero de partidos: con pocos partidos pesa
    mas el promedio de liga (evita sobre-interpretar muestras chicas); con muchos
    pesa mas el del equipo. `k` controla la fuerza del "tiron" hacia la media.
    """
    return (n_partidos * promedio_equipo + k * promedio_liga) / (n_partidos + k)


def procesar_equipo(df_partidos, promedio_liga_xg_favor, promedio_liga_xg_contra,
                    promedio_liga_tiros, n_window=6, k_shrinkage=5,
                    ponderar_por_elo=True, suavizado="ewm", ewm_span=10,
                    venue=None):
    """
    Convierte el historial de UN equipo en sus caracteristicas predictivas.

    Calcula promedios suavizados (EWM por defecto) de ataque/defensa, tiros,
    posesion, disciplina, forma y descanso; aplica shrinkage hacia el promedio
    del torneo; pondera los goles por la fuerza Elo del rival (Strength of
    Schedule) y deriva xGD y la tasa de conversion. Usa goles reales si falta xG.
    El shift(1) garantiza que ningun promedio incluya el partido actual (sin fuga
    de datos).

    Parametros clave
    ----------------
    df_partidos : DataFrame    Historial del equipo (esquema normalizado).
    promedio_liga_* : float    Promedios del torneo para el shrinkage.
    n_window, ewm_span : int   Ventana y span del suavizado.
    k_shrinkage : int          Fuerza del shrinkage.
    suavizado : "ewm" | "sma"  Tipo de promedio.
    venue : None | "Home" | "Away"  Filtra por sede (splits; off por defecto).

    Devuelve el DataFrame con todas las columnas de features anadidas.
    """
    df_partidos = df_partidos.copy()
    df_partidos['Date'] = pd.to_datetime(df_partidos['Date'])
    df_partidos = df_partidos.sort_values(by='Date').reset_index(drop=True)

    min_p = max(1, n_window // 2)

    # Splits local/visitante: en ligas de clubes, el rendimiento en casa y fuera
    # difiere. Si se pide un 'venue' y hay suficientes partidos de esa condicion,
    # calculamos los promedios usando SOLO esos. Si no alcanzan, usamos todos
    # (fallback). En sede neutral (Mundial) no se usa (venue=None).
    if venue is not None and 'Venue' in df_partidos.columns:
        sub = df_partidos[df_partidos['Venue'] == venue]
        if len(sub) >= min_p:
            df_partidos = sub.reset_index(drop=True)

    # Suavizado de los promedios. El shift(1) excluye el partido actual (sin fuga
    # de datos). "ewm" (decaimiento exponencial) da mas peso a lo reciente
    # reflejando el "estado de forma"; "sma" es media movil simple. El span del
    # EWM se calibro contra el mercado (ver backtest_cuotas).
    def prom(serie):
        s = serie.shift(1)
        if suavizado == "sma":
            return s.rolling(window=n_window, min_periods=min_p).mean()
        return s.ewm(span=ewm_span, min_periods=min_p).mean()

    # ── Fuerza del rival (Elo) ──────────────────────────────────────────────
    # elo_rival por partido y "Fuerza del Calendario" (SoS): Elo promedio de los
    # ultimos rivales enfrentados. El factor pondera los goles: anotar a un
    # gigante infla el valor, anotar a un equipo debil lo desinfla; conceder a un
    # gigante penaliza menos la defensa, conceder a uno debil penaliza mas.
    if 'Opponent' in df_partidos.columns:
        df_partidos['elo_rival'] = df_partidos['Opponent'].map(elo_de)
    else:
        df_partidos['elo_rival'] = np.nan
    df_partidos['elo_rival'] = df_partidos['elo_rival'].fillna(ELO_REFERENCIA)
    df_partidos['sos_prom'] = prom(df_partidos['elo_rival'])

    if ponderar_por_elo:
        factor_ataque = df_partidos['elo_rival'] / ELO_REFERENCIA
        factor_defensa = ELO_REFERENCIA / df_partidos['elo_rival']
    else:
        factor_ataque = pd.Series(1.0, index=df_partidos.index)
        factor_defensa = pd.Series(1.0, index=df_partidos.index)

    gf_pond = df_partidos['GF'] * factor_ataque
    ga_pond = df_partidos['GA'] * factor_defensa

    if 'xG' in df_partidos.columns and df_partidos['xG'].notna().any():
        base_favor = df_partidos['xG'] * factor_ataque
    else:
        # FBref no publica xG para partidos de selecciones/Mundial: usamos GF.
        base_favor = gf_pond
    df_partidos['xg_favor_prom'] = prom(base_favor)

    if 'xGA' in df_partidos.columns and df_partidos['xGA'].notna().any():
        base_contra = df_partidos['xGA'] * factor_defensa
    else:
        base_contra = ga_pond
    df_partidos['xg_contra_prom'] = prom(base_contra)

    # Diferencial de xG (xGD): metrica de dominio. Positivo y amplio = el equipo
    # domina la cancha, independientemente del marcador.
    df_partidos['xgd_prom'] = df_partidos['xg_favor_prom'] - df_partidos['xg_contra_prom']

    df_partidos['goles_favor_prom'] = prom(df_partidos['GF'])
    df_partidos['goles_contra_prom'] = prom(df_partidos['GA'])
    df_partidos['tiros_puerta_prom'] = prom(df_partidos['SoT'])
    df_partidos['posesion_prom'] = prom(df_partidos['Poss'])

    # Tasa de conversion (goles por tiro a puerta), suavizada. Mide eficiencia.
    gf_ewm = prom(df_partidos['GF'])
    sot_ewm = prom(df_partidos['SoT'])
    df_partidos['conversion_prom'] = (gf_ewm / sot_ewm).replace([np.inf, -np.inf], np.nan)

    df_partidos['disciplina'] = (
        df_partidos['Fls']
        + df_partidos.get('CrdR', pd.Series(0, index=df_partidos.index)) * 3
        + df_partidos.get('CrdY', pd.Series(0, index=df_partidos.index)) * 1
    )
    df_partidos['disciplina_prom'] = prom(df_partidos['disciplina'])

    def puntos(res):
        if res == 'W':
            return 3
        elif res == 'D':
            return 1
        return 0

    df_partidos['puntos'] = df_partidos['Result'].apply(puntos)
    df_partidos['racha_puntos_prom'] = prom(df_partidos['puntos'])

    df_partidos['dias_descanso'] = (
        df_partidos['Date'] - df_partidos['Date'].shift(1)
    ).dt.days.fillna(7)

    # Contamos sobre GF (siempre presente) para que el shrinkage pondere bien
    # incluso cuando FBref no publica xG (partidos de selecciones).
    n_real = df_partidos['GF'].shift(1).rolling(window=n_window, min_periods=min_p).count()

    df_partidos['xg_favor_adj'] = aplicar_shrinkage(
        df_partidos['xg_favor_prom'], promedio_liga_xg_favor, n_real, k=k_shrinkage)
    df_partidos['xg_contra_adj'] = aplicar_shrinkage(
        df_partidos['xg_contra_prom'], promedio_liga_xg_contra, n_real, k=k_shrinkage)
    df_partidos['tiros_puerta_adj'] = aplicar_shrinkage(
        df_partidos['tiros_puerta_prom'], promedio_liga_tiros, n_real, k=k_shrinkage)

    return df_partidos


def ultima_fila_valida(df_features, columnas_requeridas=None):
    """
    Devuelve la fila MAS reciente cuyas columnas imprescindibles no son nulas
    (o None si no hay ninguna). Es el "estado actual" del equipo que se pasa a
    calcular_lambdas. Solo exige las features esenciales (ataque, defensa,
    descanso); las opcionales se manejan con valores por defecto mas adelante.
    """
    if columnas_requeridas is None:
        # Solo exigimos lo imprescindible para estimar los goles esperados.
        # posesion_prom, disciplina_prom y racha_puntos_prom son opcionales:
        # calcular_lambdas() los lee con .get(valor_por_defecto) y, si faltan
        # (FBref a veces no publica faltas/tarjetas/posesion para selecciones),
        # simplemente no se aplica ese ajuste menor. Exigirlos dejaba sin
        # predecir a equipos con pocos datos disciplinarios (p.ej. Mexico).
        columnas_requeridas = ['xg_favor_adj', 'xg_contra_adj', 'dias_descanso']
    validas = df_features.dropna(subset=columnas_requeridas)
    if validas.empty:
        return None
    return validas.iloc[-1]
