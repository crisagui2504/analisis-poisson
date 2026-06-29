# 📊 `src/analisis/` — Simulación y validación

Herramientas que van más allá de un partido: simular el torneo completo y medir
qué tan bueno es el modelo.

## Módulos

### `montecarlo_mundial.py` — simulación del torneo
Juega el Mundial completo miles de veces y estima la probabilidad de título.
- **`correr(n_sim, semilla, grupos)`** — devuelve un DataFrame con % de
  campeón/final/semis/cuartos por selección y lo guarda en
  `data/montecarlo_resultados.csv`.
- **`construir_modelo(equipos, ..., promedios=None)`** — calcula las features de
  cada selección **una sola vez** (clave del rendimiento). Si se pasan `promedios`,
  los usa para el shrinkage en vez del JSON.
- **`crear_sampler(...)`** — memoriza la distribución de marcadores de cada cruce.
- **`simular_bracket(rng, dist, bracket, elos)`** — si existe
  `data/bracket_eliminatoria.json`, juega los **cruces reales confirmados**.
- **`simular_torneo(rng, dist, grupos, elos)`** — respaldo: juega grupos +
  eliminatorias sembradas. Los empates de eliminatoria se resuelven por
  **penales sesgados por Elo** (`_gana_penales`, compresión `PESO_PENALES_ELO`).
- En eliminatorias, el shrinkage usa **`promedios_desde_csv(equipos)`**: promedia
  solo sobre los 32 clasificados (la media deja de estar contaminada por los
  débiles ya eliminados).
- Lee los grupos de `data/grupos_mundial.json` si existe (editable desde la app),
  con respaldo a `GRUPOS_MUNDIAL`.

### `backtest_cuotas.py` — ¿le gana al mercado?
Backtest contra las **cuotas de cierre reales** (Pinnacle/Bet365 de
Football-Data.co.uk).
- **`descargar_cuotas(liga, temporada)`** — baja el CSV de resultados + cuotas.
- **`historial_desde_cuotas(df)`** — reconstruye el historial **del mismo CSV**
  (100% offline, sin FBref).
- **`correr(df, ...)`** — predice cada partido **sin fuga de datos** y devuelve
  probabilidades del modelo vs mercado.
- **`metricas(...)`** (log-loss/Brier/**RPS**/acierto — RPS respeta el orden 1‑X‑2),
  **`simular_roi(...)`** (ROI apostando al "valor") y **`calibrar(dfs, rhos, ks)`**
  (barrido para encontrar el mejor `rho`/`k`).
- Para comparar suavizados: `correr(df, suavizado="tiempo", half_life_dias=60)` vs
  el default EWM, mirando el **RPS** resultante.
- **`calibrar_peso_elo(dfs, ...)`** — barre el empuje por Elo (`peso_elo`) usando
  el Elo de ClubElo de cada club, por RPS/log_loss. CLI: `... E0 2425 calibrar-elo`.

### `backtest.py` — backtest histórico + auditoría
- **`correr_backtest(...)`** — calibra `rho`/`k` contra resultados históricos sin
  fuga de datos.
- **`auditar_ewm_sin_fuga()`** — verifica que el suavizado `.shift(1).ewm().mean()`
  es causal: no filtra datos del partido actual ni del futuro.

> Ejecutables: `py -3.11 src/analisis/montecarlo_mundial.py 10000` ·
> `py -3.11 src/analisis/backtest_cuotas.py SP1 2425`
