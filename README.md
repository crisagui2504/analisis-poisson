# ⚽ Predictor de Fútbol · Mundial 2026

Aplicación de escritorio que estima la probabilidad de **victoria local / empate /
victoria visitante** de un partido, el **marcador más probable** y métricas tipo
casa de apuestas (BTTS, Over/Under, cuotas justas…), usando un modelo de
**Poisson + corrección Dixon-Coles** alimentado con datos reales de
[FBref](https://fbref.com) y [football-data.org](https://www.football-data.org).
Incluye un **simulador Monte Carlo** del torneo completo.

Pensada para el **Mundial 2026** (48 selecciones, 100% offline), pero también
funciona para clubes de las grandes ligas europeas y la Liga MX.

---

## 🚀 Inicio rápido

1. Doble clic en **`Abrir Predictor.bat`**.
2. Elige **Liga**, **Equipo 1** y **Equipo 2** → **«Predecir partido»**.
3. O pulsa **🏆 Simular Mundial** para correr el torneo completo.

> Desde terminal (en la raíz del proyecto): `py -3.11 src/interfaz/app_gui.py`
> ⚠️ **Usa `py`, no `python`** — en este equipo `python` está secuestrado por el
> atajo de la Microsoft Store y falla con *"Python was not found"*.

Instalar dependencias (solo al mover el proyecto a otra PC):
```powershell
py -3.11 -m pip install -r requirements.txt
```

---

## 📁 Estructura del proyecto

```
mundial/
├── Abrir Predictor.bat      ← lanzador de doble clic
├── requirements.txt
├── README.md                ← este archivo (el principal)
├── apis.example.json        ← plantilla de API keys
├── src/                     ← todo el código (ver src/README.md)
│   ├── rutas.py             ← rutas de datos (centralizadas)
│   ├── ligas_config.py      ← config compartida (equipos, pesos, Elo, grupos)
│   ├── modelo/              ← el modelo matemático  (src/modelo/README.md)
│   ├── datos/               ← ingesta y fuentes      (src/datos/README.md)
│   ├── interfaz/            ← la app gráfica          (src/interfaz/README.md)
│   └── analisis/            ← Monte Carlo y backtest  (src/analisis/README.md)
└── data/                    ← bases de datos y salidas (data/README.md)
```

**Cada carpeta tiene su propio README** con el detalle de sus módulos. Para
entender una parte concreta, entra a su carpeta.

> Las rutas de datos están centralizadas en `src/rutas.py`, y cada script
> "ejecutable" lleva un pequeño *bootstrap* que añade `src/` y sus subcarpetas al
> path. Así puedes correr cualquier script directamente, desde la raíz, sin
> configurar nada.

---

## 🖱️ Cómo se usa la aplicación

**Panel lateral (izquierda):** liga, los dos equipos, ajustes avanzados (rho, k,
caché, *actualizar antes de predecir*), el botón **🏆 Simular Mundial** con
selector de simulaciones, y **✏️ Editar grupos** para meter el sorteo oficial.
Tras predecir aparece la **forma reciente** (🟢W / ⚪D / 🔴L) y los días de descanso.

**Panel de resultados (derecha), en pestañas:**
- *Predicción*: tarjetas **1-X-2** con % y **cuota justa**, barra de probabilidad,
  **λ** esperados, mercados (**BTTS**, **Over/Under 1.5 / 2.5 / 3.5**, **portería a
  cero**) y **Top 5 marcadores** con su cuota.
- *Análisis*: **radar de dominio** (ataque, posesión, tiros, defensa, disciplina)
  y **mapa de calor** de marcadores exactos.
- *Torneo* (tras Simular Mundial): ranking de candidatos al título con barras.

---

## 🧠 Cómo funciona (el modelo, paso a paso)

1. **Ingesta** (`src/datos/`) — historial de cada equipo (goles, xG, tiros,
   posesión, faltas, tarjetas). El Mundial lee `data/base_mundial_2026.csv`.
2. **Características** (`src/modelo/feature_engineering.py`) — promedios con
   **decaimiento exponencial (EWM, span=10)**, **shrinkage**, respaldo a goles
   reales sin xG, ponderación **Elo / Strength of Schedule**, **xGD** y conversión.
3. **Lambdas** (`src/modelo/calcular_lambdas.py`) — goles esperados (λ) ajustados
   por localía, fatiga, forma, posesión, disciplina, tiros, SoS, conversión y un
   empuje **Elo head-to-head**.
4. **Matriz Poisson + Dixon-Coles** (`src/modelo/matriz_poisson.py`) — matriz 6×6
   de marcadores exactos.
5. **Resultado y mercados** (`src/modelo/predecir_partido.py`) — 1X2 + BTTS,
   Over/Under, portería a cero y head-to-head.

Detalle matemático de cada módulo en **[src/modelo/README.md](src/modelo/README.md)**.

---

## 🔄 Datos: mantenerlos al día

```powershell
# Incremental (recomendado): agrega solo partidos nuevos, sin borrar el CSV
py -3.11 src/datos/actualizar_datos.py Spain Brazil Mexico   # solo esos (rápido)
py -3.11 src/datos/actualizar_datos.py                       # las 48 (lento)

# Multi-fuente (FBref + football-data.org si tienes API key)
py -3.11 src/datos/proveedores.py                  # ver fuentes activas
py -3.11 src/datos/proveedores.py update Spain     # cruzar fuentes

# Descarga completa desde cero (regenera data/base_mundial_2026.csv)
py -3.11 src/datos/descargar_datos.py
py -3.11 src/datos/calcular_promedios_liga.py

# Clubes: base maestra por liga (predicción offline e instantánea, con cold-start)
py -3.11 src/datos/descargar_liga_csv.py "ENG-Premier League"   # genera liga_*.csv

# Elo de clubes (ClubElo): reactiva SoS y jerarquía en ligas; puente inter-ligas
py -3.11 src/datos/descargar_club_elo.py
```
Para activar **football-data.org**: copia `apis.example.json` → `apis.local.json`
(no se sube a git) y pega tu key gratis. Detalle en
**[src/datos/README.md](src/datos/README.md)**.

---

## 📊 Análisis avanzado

```powershell
# Simular el Mundial (también desde el botón 🏆 de la app)
py -3.11 src/analisis/montecarlo_mundial.py 10000

# ¿Le gana al mercado? Backtest contra cuotas reales de cierre (log_loss/Brier/RPS)
py -3.11 src/analisis/backtest_cuotas.py            # Premier League 2024-25
py -3.11 src/analisis/backtest_cuotas.py SP1 2425   # E0/SP1/I1/D1/F1
py -3.11 src/analisis/backtest_cuotas.py E0 2425 barrido   # barre half_life por RPS
```
Calibración de `rho`/`k`, **RPS**, time-weighting (`suavizado="tiempo"`), auditoría
anti-fuga y simulador de ROI en **[src/analisis/README.md](src/analisis/README.md)**.

---

## ⚙️ Calibración (resumen)

Todos los pesos viven en `PESOS_MODELO` (`src/ligas_config.py`). `rho`/`k` se
calibran contra el mercado; los defaults son **por contexto**:

| Contexto | rho | k | Por qué |
|----------|-----|---|---------|
| **Mundial** | −0.05 | 5 | pocas partidos por selección → más shrinkage |
| **Clubes** | −0.05 | 2 | ~38 partidos → poco shrinkage es óptimo |

---

## ⚠️ Solución de problemas

- **`python` no se reconoce** → usa `py -3.11` o abre `Abrir Predictor.bat`.
- **Errores rojos de red al predecir** → para el Mundial no deberían salir (lee el
  CSV local). En clubes son inofensivos (usa el caché de soccerdata).
- **"No hay suficientes partidos completos"** → ese equipo tiene muy pocos
  partidos en la temporada elegida.
- **FBref no tiene API oficial**: si cambian su HTML, `soccerdata` puede romperse
  hasta que lo actualicen. Úsalo de forma responsable según sus términos.

---

## 🗒️ Historial de cambios (resumen)

- **Modelo**: Poisson + Dixon-Coles, respaldo a goles reales sin xG, EWM
  calibrado, Elo/SoS, xGD, conversión, head-to-head, tiros continuo. Mejora
  medida en clubes: log_loss 1.025 → 1.020.
- **App**: interfaz moderna en pestañas, mercados + cuotas justas, top-5, radar,
  forma, simulador Monte Carlo integrado con editor de grupos.
- **Datos**: base maestra offline, actualización incremental, capa de fuentes
  intercambiables (FBref + football-data.org), **base maestra por liga de clubes**
  con **cold-start** (concatena la temporada anterior para equipos con pocos partidos).
- **Clubes**: **Elo de ClubElo** (reactiva SoS y jerarquía fuera del Mundial),
  **localía por liga** (`FACTOR_LOCAL`), y **predicción inter-ligas**
  (`predecir_partido_interligas`) con el Elo de ClubElo como puente.
- **Torneo**: el Monte Carlo simula el **bracket de eliminatorias confirmado**
  (`data/bracket_eliminatoria.json`) si existe, en vez de sembrar los grupos.
- **QA**: backtest contra cuotas reales con **RPS**, **time-weighting** opcional
  (Dixon-Coles) calibrable por RPS, calibración por contexto, auditoría anti-fuga.

**Pendiente**: GUI para inter-ligas (modo "Competiciones Internacionales");
xT (StatsBomb) y nivel jugador/PSxG; score effects medidos.
