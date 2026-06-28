# 🧠 `src/modelo/` — El modelo matemático

El corazón del predictor. Convierte el historial de dos equipos en
probabilidades. Pipeline: **features → lambdas → matriz de Poisson → 1X2 + mercados**.

## Módulos

### `feature_engineering.py`
Convierte el historial de un equipo en sus "características" predictivas.
- **`procesar_equipo(df, ...)`** — calcula promedios con **decaimiento exponencial
  (EWM, span=10)** de xG/goles a favor y en contra, tiros, posesión, disciplina,
  forma y descanso. Aplica **shrinkage** (mezcla con el promedio del torneo según
  cuántos partidos tiene), ponderación por **Elo del rival** (Strength of
  Schedule), y deriva **xGD** y la **tasa de conversión**. Si falta xG (típico en
  selecciones) usa goles reales. El `shift(1)` garantiza **cero fuga de datos**.
  Soporta `venue="Home"/"Away"` para splits (apagado por defecto: medido, empeora).
  Además del EWM admite **`suavizado="tiempo"`** (time-weighting de Dixon-Coles):
  cada partido pesa `exp(-ξ·días)` según los **días reales** transcurridos, con
  `ξ = ln(2)/half_life_dias`. Opt-in (default sigue siendo EWM); calíbralo con el
  backtest y RPS.
- **`ultima_fila_valida(df)`** — devuelve la fila más reciente con las features
  imprescindibles no nulas (o `None`).
- **`aplicar_shrinkage(...)`** — la fórmula de regularización hacia la media.

### `calcular_lambdas.py`
Convierte las features de los dos equipos en sus **goles esperados (λ)**.
- **`calcular_lambdas(local, visitante, ...)`** — λ base = combinación de ataque
  y defensa, y aplica ajustes acotados: localía, fatiga (descanso), forma,
  posesión, **tiros** (continuo), **SoS**, **conversión**, **xGD**, disciplina y un
  empuje **Elo head-to-head** hacia el favorito. Todos los pesos vienen de
  `PESOS_MODELO`.

### `matriz_poisson.py`
- **`generar_matriz_poisson(λ_local, λ_visitante, rho)`** — matriz 6×6 con la
  probabilidad de cada marcador exacto (producto de dos Poisson) y la
  **corrección Dixon-Coles** en los marcadores de pocos goles. Siempre suma 1.
- **`correccion_dixon_coles(...)`** — el ajuste de las celdas (0,0), (1,0), (0,1), (1,1).

### `predecir_partido.py` — el orquestador
- **`predecir_partido(local, visitante, liga, temporada, ...)`** — encadena todo
  el pipeline y devuelve un dict con probabilidades 1X2, λ, la matriz, los
  **mercados**, la **forma**, el **descanso** y las **métricas** para el radar.
- **`predecir_partido_interligas(local, liga_local, visitante, liga_visitante, ...)`**
  — cruces entre equipos de **ligas distintas** (Champions, Mundial de Clubes,
  amistosos). Cada equipo se evalúa con los datos y promedios de su propia liga;
  el **Elo de ClubElo** (comparable entre ligas europeas) hace de puente de fuerza.
  Por defecto `neutral=True` y sin head-to-head. Devuelve el mismo dict.
- **`calcular_mercados(matriz)`** — deriva BTTS, Over/Under 1.5/2.5/3.5 y portería
  a cero sumando regiones de la matriz.
- **`_factor_h2h(df, local, visitante)`** — historial directo (paternidad): inclina
  los λ ±4% con normalización **simétrica** de nombres.

> Para calibrar el comportamiento, edita `PESOS_MODELO` en `src/ligas_config.py`,
> no las fórmulas de aquí.
