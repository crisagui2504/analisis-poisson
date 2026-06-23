# ⚽ Predictor de Fútbol · Mundial 2026

Aplicación de escritorio que estima la probabilidad de **victoria local / empate /
victoria visitante** de un partido, el **marcador más probable** y métricas tipo
casa de apuestas (BTTS, Over/Under, cuotas justas…), usando un modelo de
**Poisson + corrección Dixon-Coles** alimentado con datos reales de
[FBref](https://fbref.com) y [football-data.org](https://www.football-data.org).

Pensada para el **Mundial 2026** (48 selecciones precargadas, 100% offline), pero
también funciona para clubes de las grandes ligas europeas y la Liga MX.

---

## 🚀 Inicio rápido

1. Doble clic en **`Abrir Predictor.bat`**.
2. Elige **Liga**, **Equipo 1** y **Equipo 2**.
3. Pulsa **«Predecir partido»**.

> Desde terminal: `py -3.11 app_gui.py`
> ⚠️ **Usa `py`, no `python`** — en este equipo `python` está secuestrado por el
> atajo de la Microsoft Store y falla con *"Python was not found"*.

---

## 🖱️ Cómo se usa la aplicación

**Panel lateral (izquierda):**

- **Liga** — *Mundial 2026* o una liga de clubes.
- **Equipo 1 / Equipo 2** — los desplegables se llenan solos (48 selecciones en
  español para el Mundial; clubes descargados de FBref la primera vez).
- **Ajustes avanzados** (normalmente no hace falta tocarlos):
  - **Rho (Dixon-Coles)** (`-0.05`): corrige la dependencia entre marcadores de
    pocos goles (0-0, 1-0, 0-1, 1-1).
  - **Shrinkage k** (`5`): cuánto se "tira" la estimación de un equipo hacia el
    promedio cuando tiene pocos partidos. Más alto = más conservador.
  - **Usar caché local** (activado): reutiliza los datos ya descargados. Déjalo así.
  - **Actualizar datos antes de predecir** (desactivado): trae los partidos nuevos
    de **solo los 2 equipos** desde una API rápida (football-data.org) y luego
    predice. Si falla la red, avisa y usa los datos locales.
- Tras predecir, aparece la **forma reciente** (últimos 5: 🟢W / ⚪D / 🔴L) y los
  **días de descanso** de cada equipo.
- **🏆 Simular Mundial**: corre el Monte Carlo del torneo completo (selector de
  1.000 / 5.000 / 10.000 simulaciones) y muestra el ranking de candidatos al
  título con gráfico de barras, sin salir de la app.

**Panel de resultados (derecha), en dos pestañas:**

- *Predicción*: tarjetas **1-X-2** con % y **cuota justa** (1/prob), barra de
  probabilidad, **λ** esperados, mercados (**BTTS**, **Over/Under 1.5 / 2.5 / 3.5**,
  **portería a cero**) y **Top 5 marcadores** más probables con su cuota.
- *Análisis*: **radar de dominio** (ataque, posesión, tiros, defensa, disciplina)
  local vs visitante, y **mapa de calor** de marcadores exactos.

---

## 🧠 Cómo funciona (el modelo, paso a paso)

1. **Ingesta** (`ingest_fbref.py`, `proveedores.py`) — descarga el historial de
   cada equipo (goles, xG, tiros a puerta, posesión, faltas, tarjetas) y normaliza
   columnas. Para el Mundial lee la base local `base_mundial_2026.csv`.

2. **Ingeniería de características** (`feature_engineering.py`):
   - Promedios con **decaimiento exponencial (EWM, span=10)**: pesan más los
     partidos recientes (forma). El span se calibró contra el mercado y superó a
     la media móvil simple.
   - **Shrinkage**: mezcla el promedio del equipo con el del torneo según cuántos
     partidos tiene (un equipo con 2 partidos no se sobre-interpreta).
   - **Respaldo a goles reales**: si FBref no publica xG (típico en selecciones),
     usa **GF / GA** en lugar de xG.
   - **Fuerza del rival (Elo / Strength of Schedule)**: pondera los goles por el
     Elo del rival (`ELO_RANKING`). Anotar a un gigante *infla*; a un débil,
     *desinfla*. Calcula `sos_prom`, `xgd_prom` (diferencial de xG) y la **tasa de
     conversión** (goles/tiro).

3. **Cálculo de lambdas** (`calcular_lambdas.py`) — convierte las features en los
   **goles esperados (λ)**, ajustando por localía (off en sede neutral), fatiga,
   forma, posesión, disciplina, tiros, SoS y conversión. Cierra con un **empuje
   Elo head-to-head** para que un gigante se imponga a un chico en racha.

4. **Matriz de Poisson + Dixon-Coles** (`matriz_poisson.py`) — matriz 6×6 con la
   probabilidad de cada marcador exacto, corregida en los marcadores de pocos goles.

5. **Resultado y mercados** (`predecir_partido.py`) — suma la matriz por regiones
   para P(local/empate/visitante) y deriva BTTS, Over/Under 1.5/2.5/3.5, portería
   a cero, y el historial directo (head-to-head, ±4%).

**Origen de los datos:** el Mundial lee `base_mundial_2026.csv` (offline,
instantáneo); los clubes se descargan de FBref en vivo la primera vez.

---

## 🛠️ Instalación y dependencias

| Herramienta | Para qué |
|-------------|----------|
| **Python 3.11** | Lenguaje base (lanzador `py -3.11`). |
| **tkinter** | Interfaz gráfica (incluido con Python). |
| **soccerdata** | Descarga de FBref (scraping estructurado; cachea en `~/soccerdata`). |
| **requests** | Llamadas REST a football-data.org. |
| **pandas / numpy / scipy** | Tablas, matriz de probabilidades, distribución de Poisson. |
| **matplotlib** | Mapa de calor y radar. |
| **scikit-learn** | `log_loss` del backtest/calibración. |

Instalar dependencias (solo al mover el proyecto a otra PC):
```powershell
py -3.11 -m pip install -r requirements.txt
```

---

## 📂 Estructura del proyecto

| Archivo | Rol |
|---------|-----|
| `Abrir Predictor.bat` | Lanzador de doble clic (usa `py -3.11 app_gui.py`). |
| `app_gui.py` | **Aplicación principal** (interfaz gráfica). |
| `predecir_partido.py` | Orquesta la predicción y deriva los mercados. La GUI llama a `predecir_partido()`. |
| `feature_engineering.py` | Promedios EWM, shrinkage, ponderación Elo/SoS, validación de filas. |
| `calcular_lambdas.py` | Calcula los goles esperados (λ) con todos los ajustes. |
| `matriz_poisson.py` | Matriz de marcadores + corrección Dixon-Coles. |
| `ligas_config.py` | Ligas, 48 selecciones (español ↔ FBref), `PESOS_MODELO`, `ELO_RANKING` y `GRUPOS_MUNDIAL`. |
| `ingest_fbref.py` | Descarga/normaliza datos de FBref y fusiona el CSV maestro. |
| `proveedores.py` | **Capa de fuentes intercambiables** (plug-in): FBref + football-data.org. |
| `apis.example.json` | Plantilla de API keys (cópiala a `apis.local.json`, que no se sube a git). |
| `paleta.py` / `tema_oscuro.py` | Paleta de colores (design tokens) y estilo de los widgets. |
| `descargar_datos.py` | Descarga masiva del Mundial (con pausas) y exporta el CSV maestro. |
| `actualizar_datos.py` | **Actualización incremental**: agrega solo los partidos nuevos. |
| `calcular_promedios_liga.py` | Genera `promedios_liga.json` desde el caché local. |
| `montecarlo_mundial.py` | **Simulación**: juega el Mundial miles de veces y estima % de título. |
| `backtest.py` | Backtest histórico + auditoría anti-fuga del EWM. |
| `backtest_cuotas.py` | **Backtest contra el mercado** (cuotas reales) + calibración + ROI. |
| `base_mundial_2026.csv` | **Base maestra** del Mundial (historial de las 48 selecciones). |
| `promedios_liga.json` | Promedios del torneo usados por el shrinkage. |
| `requirements.txt` | Dependencias para `pip install -r`. |

---

## 🔄 Datos: mantenerlos al día

**Actualización incremental (recomendada).** Conforme se juegan partidos:
```powershell
py -3.11 actualizar_datos.py                       # las 48 selecciones (lento)
py -3.11 actualizar_datos.py Spain Brazil Mexico   # solo esas (rápido)
```
Fusiona los partidos nuevos en `base_mundial_2026.csv` sin borrar lo anterior
(deduplica por `Team + Date + Opponent`; prevalece el dato nuevo).

> ⏱️ FBref no permite pedir "solo lo nuevo": cada equipo baja su temporada
> completa y la librería espacia las peticiones, por eso las 48 tardan minutos.
> Pasa **solo los equipos que jugaron** para que baje a segundos. La casilla
> *"Actualizar antes de predecir"* hace justo esto con los 2 equipos del partido.

**Descarga completa desde cero** (datos más frescos, tarda varios minutos):
```powershell
py -3.11 descargar_datos.py        # regenera base_mundial_2026.csv al terminar
py -3.11 calcular_promedios_liga.py  # recalcula promedios_liga.json
```

**Fuentes de datos / APIs (arquitectura desacoplada).** `proveedores.py` define
una capa *plug-in*: cada API es independiente y, si una falla o no está
configurada, las demás siguen.
```powershell
py -3.11 proveedores.py                     # ver qué fuentes están activas
py -3.11 proveedores.py update Spain Brazil  # actualizar cruzando todas las fuentes
```
Para activar **football-data.org**: registra una key gratis, copia
`apis.example.json` → `apis.local.json` y pega tu clave (o usa la variable de
entorno `FOOTBALL_DATA_ORG_KEY`). Agregar otra API = una subclase de
`ProveedorDatos` registrada en `PROVEEDORES`; nada más cambia.

---

## 📊 Análisis avanzado

**Simular el Mundial completo (Monte Carlo).** Desde la app con el botón
**🏆 Simular Mundial**, o por terminal:
```powershell
py -3.11 montecarlo_mundial.py 10000   # [n_simulaciones] [semilla] opcionales
```
Juega el torneo 10.000 veces (grupos + eliminatorias). No le da la victoria al
favorito automáticamente: **lanza los dados** con `numpy` según las probabilidades
del modelo, permitiendo sorpresas. Guarda `montecarlo_resultados.csv` con el % de
campeón/final/semis/cuartos y muestra el Top 12.

> El cuadro vive en `GRUPOS_MUNDIAL` (`ligas_config.py`): 12 grupos de 4,
> **sembrados por Elo de forma provisional** (no es el sorteo oficial). Edita esas
> listas para reflejar los grupos reales. Las features se calculan una sola vez y
> los cruces se memorizan → 10.000 torneos corren en segundos.

**Backtest contra cuotas reales (¿le gana al mercado?).**
```powershell
py -3.11 backtest_cuotas.py            # Premier League 2024-25
py -3.11 backtest_cuotas.py SP1 2425   # E0/SP1/I1/D1/F1
```
Descarga el CSV de Football-Data.co.uk (resultados + cuotas de cierre de Pinnacle/
Bet365), reconstruye el historial **del mismo archivo** (offline, sin FBref) y
predice cada partido **sin fuga de datos**. Reporta `log_loss`/Brier/acierto del
modelo vs el mercado y un **simulador de ROI**.

> *Realismo:* batir las cuotas de cierre es muy difícil. Un log_loss peor que el
> mercado con un ROI ligeramente positivo suele ser **ruido**, no ventaja durable.

---

## ⚙️ Calibrar el modelo

Todos los pesos y umbrales viven en **`PESOS_MODELO`** (`ligas_config.py`): localía,
fatiga, forma, posesión, disciplina, tiros, SoS, conversión, xGD, Elo. Cámbialos
ahí — un solo lugar, sin tocar la matemática de `calcular_lambdas.py`.

`rho` y `k` se calibran contra el mercado con `backtest_cuotas.calibrar([df1, ...])`.
Hallazgo: **`k` (shrinkage) es la palanca real, no `rho`**. Defaults **por contexto**:

| Contexto | rho | k | Por qué |
|----------|-----|---|---------|
| **Mundial** | −0.05 | 5 | selecciones tienen pocos partidos → necesitan más shrinkage |
| **Clubes** | −0.05 | 2 | tienen ~38 partidos → poco shrinkage es óptimo |

**Auditoría anti-fuga** (`backtest.auditar_ewm_sin_fuga()`): confirma que
`.shift(1).ewm().mean()` es causal — no filtra datos del partido actual ni del
futuro. Pasa sin fuga.

---

## ⚠️ Solución de problemas

- **`python` no se reconoce** → usa `py -3.11` o abre `Abrir Predictor.bat`.
- **Errores rojos de red al predecir** (`ConnectionResetError`, `Max retries…`) →
  para el Mundial no deberían salir (lee el CSV local). En clubes son inofensivos:
  `soccerdata` intenta refrescar y, si falla, usa el caché; la predicción se
  completa igual. Mantén **«Usar caché local»** activado.
- **"No hay suficientes partidos completos"** → ese equipo tiene muy pocos partidos
  jugados en la temporada elegida.
- **Nombres de equipo**: para el Mundial usa el desplegable (español); para clubes
  deben coincidir exactamente con FBref.
- **FBref no tiene API oficial**: si cambian su HTML, `soccerdata` puede romperse
  hasta que lo actualicen. Úsalo de forma responsable según sus términos.

---

## 🗒️ Historial de cambios

**Correcciones de fondo**
1. **Respaldo a goles reales sin xG** *(clave para el Mundial)*: el ataque usa GF
   (la defensa ya usaba GA) y el shrinkage cuenta sobre GF.
2. **Dixon-Coles**: corregido el swap de lambdas en las celdas (1,0) y (0,1).
3. **Sin data leakage** en el backtest (promedios solo con partidos previos).
4. **NaN-check explícito** en `ultima_fila_valida()`.
5. **log_loss**: índice de clase (0/1/2), no one-hot.
6. **Matriz normalizada con `rho=0`**: antes sumaba ~0.98; ahora siempre 1.

**Mejoras del modelo (medidas con `backtest_cuotas.py`)**
- **EWM** (span=10) en vez de media móvil — pesa más lo reciente.
- **Tiros a puerta** activados con ajuste **continuo** (antes se calculaban y se
  ignoraban).
- **Fuerza del Calendario** (`sos_prom`), **xGD** y **tasa de conversión** ahora
  influyen en los lambdas.
- **Head-to-Head**: paternidad histórica entre selecciones (±4%).
- Efecto neto en clubes: log_loss **1.0251 → 1.0196**, acierto **49.1% → 50.6%**.
- **Splits local/visitante**: implementados pero **apagados** — medidos, empeoran
  (partir la muestra mete ruido; la localía ya la cubre `factor_local`).

**Calidad de código**
- `PESOS_MODELO` centraliza los "números mágicos"; paleta como design tokens.
- Persistencia explícita en CSV maestro (app del Mundial 100% offline).
- Type hints en las funciones principales; UI sin congelarse (hilo + `self.after`).

**Pendiente**
- Backtest **multi-temporada** (hoy: 5 ligas, una temporada).
- **xT** (StatsBomb) y modelo a **nivel jugador / PSxG** — saltos de arquitectura.
- **Score effects** medidos (requiere datos jugada-a-jugada no disponibles).
