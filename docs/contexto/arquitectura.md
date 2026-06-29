# Arquitectura

> Predictor de fútbol (Mundial 2026 + ligas de clubes): modelo Poisson + Dixon-Coles
> sobre datos de FBref, con app de escritorio y simulador Monte Carlo.

## Stack
- **Lenguaje**: Python **3.11** (se invoca con `py -3.11`, no `python`).
- **Cálculo**: `pandas`, `numpy`, `scipy` (Poisson), `scikit-learn` (`log_loss`).
- **GUI**: `tkinter` (escritorio, sin framework web).
- **Datos**: `soccerdata` (scraping FBref + caché HTML), `requests`/`lxml`/`html5lib`.
  ClubElo vía su API/CSV; football-data.co.uk para el backtest de cuotas;
  football-data.org opcional (capa de proveedores).
- Sin base de datos: todo es **CSV/JSON** en `data/`.

## Mapa de carpetas
```
src/
  rutas.py            rutas absolutas a data/ (centralizadas)
  ligas_config.py     config compartida: PESOS_MODELO, ELO_RANKING(+override),
                      FACTOR_LOCAL, LIGAS, grupos, NOMBRE_DISPLAY, elo_de()
  modelo/             feature_engineering · calcular_lambdas · matriz_poisson · predecir_partido
  datos/              ingest_fbref · proveedores · club_elo · scripts de descarga/actualización
  interfaz/           app_gui.py (tkinter)
  analisis/           montecarlo_mundial · backtest_cuotas · backtest
data/                 base_mundial_2026.csv, promedios_liga.json, *_override/cache, salidas
Abrir Predictor.bat · requirements.txt · apis.example.json · repomix-output.xml
```
Cada subcarpeta tiene su propio `README.md`. Los scripts ejecutables llevan un
*bootstrap* que añade `src/` y subcarpetas a `sys.path`.

## Flujo de datos
1. **Ingesta** → `base_mundial_2026.csv` (Mundial) / `liga_<liga>_<temp>.csv` (clubes);
   `club_elo.csv` (Elo de clubes). Esquema normalizado de columnas = contrato.
2. **Features** (`feature_engineering.procesar_equipo`): promedios EWM + shrinkage +
   SoS por Elo (`elo_de`), sin fuga (`shift(1)`).
3. **Lambdas** (`calcular_lambdas`) → **matriz Poisson + Dixon-Coles** (`matriz_poisson`).
4. **`predecir_partido` / `predecir_partido_interligas`** → 1X2 + mercados (dict que consume la GUI).
5. **Monte Carlo** (`montecarlo_mundial`): `construir_modelo` → `crear_sampler` →
   `simular_bracket` (si existe `bracket_eliminatoria.json`) o `simular_torneo`.
6. **Backtest** (`backtest_cuotas`): cuotas reales → `correr` → `metricas` (log_loss/Brier/RPS).

## Qué NO existe (a hoy)
- **Sin tests automatizados** ni framework (no `tests/`, no pytest). Verificación ad-hoc + `backtest.auditar_ewm_sin_fuga()`.
- **Sin CI/CD**, sin linter/formatter configurado (no `pyproject.toml`/`.pre-commit`/`.github`).
- Sin API REST, sin Docker, sin base de datos.
- **GUI inter-ligas**: solo existe el backend (`predecir_partido_interligas`), no la pantalla.
- Elo de clubes **no cubre Liga MX** (ni selecciones) en ClubElo.
- Sin xG a nivel de tiro (se usa el xG agregado de FBref).
- [PENDIENTE: no se halló archivo de licencia ni `CONTRIBUTING`.]
