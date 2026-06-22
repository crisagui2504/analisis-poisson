# ⚽ Predictor de Fútbol · Mundial 2026

Aplicación de escritorio que estima la probabilidad de **victoria local / empate /
victoria visitante** para un partido, junto con el marcador más probable, usando
un modelo estadístico de **Poisson + corrección Dixon-Coles** alimentado con datos
reales descargados de [FBref](https://fbref.com).

Pensada para el **Mundial 2026** (48 selecciones precargadas), pero también
funciona para clubes de las grandes ligas europeas y la Liga MX.

---

## 🚀 Inicio rápido (lo único que necesitas para usarla)

1. Haz **doble clic en `Abrir Predictor.bat`**.
2. Se abre la ventana del predictor. Elige **Liga**, **Equipo 1** y **Equipo 2**.
3. Pulsa **«Predecir partido»**.
4. Verás las probabilidades, los goles esperados (λ) y el **mapa de calor** de
   marcadores exactos.

> Si prefieres la terminal, abre PowerShell en esta carpeta y ejecuta:
> ```powershell
> py -3.11 app_gui.py
> ```
> ⚠️ **Usa `py`, no `python`.** En este equipo el comando `python` está
> secuestrado por el atajo de la Microsoft Store y falla con
> *"Python was not found"*.

---

## 🧩 ¿Qué herramientas usa?

| Herramienta | Para qué se usa |
|-------------|-----------------|
| **Python 3.11** | Lenguaje base. Lanzador `py -3.11`. |
| **tkinter** | Interfaz gráfica (viene incluido con Python). |
| **soccerdata** | Descarga datos de FBref (FBref no tiene API oficial; hace scraping estructurado y cachea en `~/soccerdata`). |
| **pandas** | Manejo de tablas de partidos. |
| **numpy** | Cálculo de la matriz de probabilidades. |
| **scipy** | Distribución de Poisson (`scipy.stats.poisson`). |
| **matplotlib** | Mapa de calor de marcadores. |
| **scikit-learn** | Solo para el backtest/calibración (`log_loss`). |

### Instalación de dependencias (solo la primera vez)

```powershell
py -3.11 -m pip install pandas numpy scipy matplotlib scikit-learn soccerdata
```

> En este equipo ya están todas instaladas. Esta línea solo es necesaria si
> mueves el proyecto a otra computadora.

---

## 🖱️ Cómo se usa la aplicación

Panel izquierdo:

- **Liga** — elige *Mundial 2026* o una liga de clubes.
- **Equipo 1 / Equipo 2** — los desplegables se llenan solos según la liga.
  - En *Mundial 2026* aparecen las 48 selecciones **en español**.
  - En ligas de clubes, los equipos se descargan de FBref la primera vez.
- **Parámetros (avanzado)** — normalmente no hace falta tocarlos:
  - **Rho Dixon-Coles** (`-0.13` por defecto): corrige la dependencia entre
    resultados de pocos goles (0-0, 1-0, 0-1, 1-1).
  - **Shrinkage k** (`5` por defecto): cuánto se "tira" la estimación de un
    equipo hacia el promedio del torneo cuando tiene pocos partidos. Más alto =
    más conservador.
  - **Usar caché local** (activado): reutiliza los datos ya descargados en vez
    de volver a pedirlos a FBref. **Déjalo activado** salvo que quieras forzar
    una descarga nueva.
  - **Actualizar datos antes de predecir** (desactivado): si lo marcas, al pulsar
    *Predecir partido* el programa primero trae de FBref los partidos nuevos de
    **solo los 2 equipos del partido** (fusión incremental, sin borrar el CSV) y
    **luego** predice — son unos segundos, no minutos. Si la red falla, avisa y
    predice igual con los datos locales.

Panel derecho (tras pulsar *Predecir partido*):

- **3 tarjetas redondeadas**: probabilidad de victoria del Equipo 1, empate, y
  victoria del Equipo 2.
- **Barra de probabilidad** 1-X-2: reparto visual de las tres probabilidades.
- **xG esperados (λ)**: goles esperados de cada equipo según el modelo.
- **Tarjetas de mercados**: *Ambos anotan (BTTS)*, *Más de 2.5 goles* y
  *Portería a 0* (local / visitante).
- **Mapa de calor**: probabilidad de cada marcador exacto (0-0, 1-0, 2-1, …).

---

## 🧠 Cómo funciona (el modelo, paso a paso)

1. **Ingesta** (`ingest_fbref.py`)
   Descarga de FBref el historial de cada equipo (goles, xG, tiros a puerta,
   posesión, faltas, tarjetas) y normaliza los nombres de columna.

2. **Ingeniería de características** (`feature_engineering.py`)
   - Calcula promedios móviles de las últimas *N* partidos (ventana = 6).
   - Aplica **shrinkage**: mezcla el promedio del equipo con el promedio del
     torneo, ponderando por cuántos partidos tiene el equipo. Así un equipo con
     2 partidos no se sobre-interpreta.
   - **Respaldo a goles reales**: si FBref **no publica xG** para un partido
     (caso típico de selecciones / Mundial), el modelo usa los **goles a favor
     (GF)** y **en contra (GA)** en lugar de xG. *(Esta es la corrección clave
     que hace que el Mundial funcione — ver §Correcciones.)*
   - **Fuerza del rival (Elo / Strength of Schedule)**: cada rival histórico
     tiene un Elo (`ELO_RANKING` en `ligas_config.py`). Los goles se **ponderan**
     por ese Elo: anotar a un gigante *infla* el valor, anotar a un equipo débil
     lo *desinfla* (y al revés para los goles concedidos). Además se calcula la
     columna `sos_prom` (Elo medio de los últimos rivales).

3. **Cálculo de lambdas** (`calcular_lambdas.py`)
   Convierte las características en los **goles esperados (λ)** de cada equipo,
   ajustando por: localía (desactivada en sede neutral del Mundial), días de
   descanso/fatiga, forma reciente, posesión y disciplina. Por último aplica un
   **empuje hacia el favorito según la diferencia de Elo head-to-head** (fórmula
   Elo estándar, ponderada por `PESOS_MODELO["peso_elo"]`): garantiza que un
   gigante se imponga a un equipo chico aunque éste venga en racha.

4. **Matriz de Poisson + Dixon-Coles** (`matriz_poisson.py`)
   Genera una matriz 6×6 con la probabilidad de cada marcador exacto, y aplica
   la corrección Dixon-Coles a los marcadores de pocos goles.

5. **Resultado y mercados** (`predecir_partido.py`)
   Suma la matriz por regiones para P(local), P(empate), P(visitante) y deriva
   métricas tipo casa de apuestas: **BTTS** (ambos anotan), **Over/Under 2.5
   goles** y **portería a cero** de cada equipo.

### Origen de los datos (Mundial vs clubes)

- **Mundial 2026**: el predictor lee primero `base_mundial_2026.csv` (la base
  maestra). Esto lo hace **100% offline, instantáneo y sin errores de red**. Solo
  si ese archivo no existe (o marcas *no usar caché*) recurre a FBref en vivo.
- **Clubes**: se descargan de FBref en vivo la primera vez.

### Calibrar el modelo (sin tocar fórmulas)

Todos los pesos y umbrales del modelo viven en el diccionario **`PESOS_MODELO`**
de `ligas_config.py` (ventaja de localía, fatiga, forma, posesión, disciplina).
Si quieres ajustar el comportamiento, cambia los números **ahí**, en un solo
lugar, sin tocar la matemática de `calcular_lambdas.py`.

---

## 📂 Estructura del proyecto

| Archivo | Rol |
|---------|-----|
| `app_gui.py` | **Aplicación principal** (interfaz gráfica). Es lo que abre el `.bat`. |
| `predecir_partido.py` | Orquesta la predicción (sin interfaz). La GUI llama a `predecir_partido()`. |
| `ingest_fbref.py` | Descarga y normaliza datos de FBref vía `soccerdata`. |
| `feature_engineering.py` | Promedios móviles, shrinkage y validación de filas. |
| `calcular_lambdas.py` | Calcula los goles esperados (λ) ajustados. |
| `matriz_poisson.py` | Matriz de marcadores + corrección Dixon-Coles. |
| `ligas_config.py` | Ligas, temporadas, las 48 selecciones (nombre español ↔ FBref), **`PESOS_MODELO`** (pesos/umbrales del modelo) y **`ELO_RANKING`** (fuerza de cada selección). Todo para calibrar en un solo lugar. |
| `paleta.py` | **Paleta de colores y tipografía** de la interfaz (design tokens). Cambia un color aquí y toda la app se actualiza. |
| `tema_oscuro.py` | Estilo moderno de los widgets ttk (combos, sliders, progreso, checks). |
| `calcular_promedios_liga.py` | Genera `promedios_liga.json` leyendo el caché local. |
| `descargar_datos.py` | Descarga masiva del Mundial equipo por equipo (con pausas anti-bloqueo) y exporta el CSV maestro. |
| `actualizar_datos.py` | **Actualización incremental**: trae solo los partidos nuevos de FBref y los fusiona en el CSV maestro sin borrarlo. |
| `montecarlo_mundial.py` | **Motor de simulación**: juega el Mundial completo (grupos + eliminatorias) miles de veces y estima la probabilidad de título de cada selección. |
| `backtest.py` | Calibra `rho` y `k` contra resultados históricos. |
| `promedios_liga.json` | Promedios del torneo usados por el shrinkage. |
| `base_mundial_2026.csv` | **Base de datos maestra** del Mundial (historial limpio y normalizado de las 48 selecciones). El predictor la lee directamente → 100% offline y rápido. |
| `montecarlo_resultados.csv` | Salida de la simulación: probabilidad de campeón / final / semis / cuartos por selección. |

---

## 🔧 Tareas de mantenimiento (opcionales)

### Volver a descargar los datos del Mundial
Si pasa el tiempo y quieres datos más recientes:
```powershell
py -3.11 descargar_datos.py
```
Descarga selección por selección con pausas de ~45 s para no ser bloqueado por
FBref. Tarda varios minutos. **Al terminar regenera automáticamente
`base_mundial_2026.csv`**, la base maestra que usa el predictor.

### Mantener los datos al día (incremental, recomendado)
Conforme se juegan partidos, en vez de descargar todo otra vez:
```powershell
py -3.11 actualizar_datos.py                       # las 48 selecciones (lento)
py -3.11 actualizar_datos.py Spain Brazil Mexico   # solo esas (rápido)
```
Trae de FBref lo reciente y **fusiona los partidos nuevos** en
`base_mundial_2026.csv` sin borrar lo anterior (deduplica por
`Team + Date + Opponent`; si un partido ya existía, prevalece el dato nuevo).

> ⏱️ **Por qué tarda y cómo acelerarlo:** FBref no permite pedir "solo lo nuevo";
> cada equipo descarga su temporada completa y FBref limita a los scrapers
> (soccerdata espacia las peticiones). Por eso actualizar las **48 selecciones**
> tarda varios minutos. Si solo jugaron unos pocos equipos, **pásalos como
> argumento** y baja a segundos. En la app, la casilla *"Actualizar datos antes
> de predecir"* hace justo esto: actualiza **solo los 2 equipos del partido**.

### Recalcular los promedios del torneo
Tras una descarga nueva, regenera `promedios_liga.json` (lee solo el caché
local, no toca la red):
```powershell
py -3.11 calcular_promedios_liga.py
```

### Simular el Mundial completo (Monte Carlo)

Para estimar quién ganaría el torneo, no un solo partido:
```powershell
py -3.11 montecarlo_mundial.py 10000
```
Juega el Mundial completo 10.000 veces (fase de grupos + eliminatorias). En cada
partido no le da la victoria al favorito automáticamente: **lanza los dados** con
`numpy` según las probabilidades del modelo, permitiendo sorpresas. Al terminar
guarda `montecarlo_resultados.csv` con el % de título de cada selección y muestra
el Top 12 en pantalla. Acepta argumentos opcionales: `montecarlo_mundial.py
[n_simulaciones] [semilla]`.

> **El cuadro del torneo** vive en `GRUPOS_MUNDIAL` (`ligas_config.py`): 12 grupos
> de 4. La versión incluida está **sembrada por Elo de forma provisional** (no es
> el sorteo oficial). Para resultados exactos, edita esas listas moviendo los
> nombres a sus grupos reales. La simulación las lee tal cual.
>
> Rendimiento: las características de cada equipo se calculan **una sola vez** y
> los cruces se memorizan, así 10.000 torneos completos corren en segundos.

### Calibrar el modelo (avanzado)
```python
import pandas as pd
from ingest_fbref import descargar_liga
from backtest import correr_backtest

df_liga = descargar_liga('ENG-Premier League', '2024-2025')
partidos = df_liga[['Date', 'Team', 'Opponent', 'Result']].drop_duplicates()
correr_backtest(partidos, df_liga, verbose=True)
# Usa el rho/k con menor log_loss como parámetros en la app.
```

---

## ⚠️ Notas y solución de problemas

- **`python` no se reconoce / "Python was not found"** → usa `py -3.11`
  (o simplemente abre `Abrir Predictor.bat`).
- **Errores rojos de red al predecir** (`ConnectionResetError`,
  `localhost ... connection refused`, `Max retries exceeded`) → **para el Mundial
  ya no deberían aparecer**, porque el predictor lee `base_mundial_2026.csv` sin
  tocar la red. Si llegaran a salir (p. ej. en ligas de clubes), son
  **inofensivos**: `soccerdata` intenta refrescar por internet y, si falla, usa
  el caché local; la predicción se completa igual. Mantén **«Usar caché local»**
  activado.
- **"No hay suficientes partidos completos para calcular"** → significaba que el
  equipo no tenía datos utilizables. Con la corrección de respaldo a goles
  reales esto ya no debería ocurrir para selecciones del Mundial. Si aparece en
  una liga de clubes, ese equipo tiene muy pocos partidos jugados en la
  temporada elegida.
- **Predicción de clubes**: requiere descargar datos en vivo de FBref la primera
  vez (el caché solo trae el Mundial 2026). Si la red a FBref falla en ese
  momento, prueba de nuevo más tarde; no es un fallo del programa.
- **Nombres de equipo**: para el Mundial usa los del desplegable (en español).
  Para clubes deben coincidir **exactamente** con FBref.
- **FBref no tiene API oficial.** Si cambian su HTML, `soccerdata` puede romperse
  hasta que sus mantenedores la actualicen. Usa la herramienta de forma
  responsable respecto a los términos de FBref/Sports Reference.

---

## ✅ Correcciones aplicadas en esta versión

1. **Respaldo a goles reales cuando falta xG** *(clave para el Mundial)*: FBref
   no publica xG para partidos de selecciones, lo que dejaba todas las filas
   inválidas y producía el error *"No hay suficientes partidos completos"*. Ahora
   el ataque usa **GF** como respaldo (igual que la defensa ya usaba **GA**), y
   el conteo del shrinkage se basa en **GF** (siempre presente) para que ese
   respaldo realmente pese. → `feature_engineering.py`.
2. **Dixon-Coles**: corregido el swap de lambdas en las celdas (1,0) y (0,1).
3. **Backtest sin data leakage**: el promedio de liga del shrinkage se calcula
   solo con partidos previos a cada predicción.
4. **NaN-check explícito**: `ultima_fila_valida()` evita pasar filas incompletas
   a `calcular_lambdas`.
5. **log_loss corregido**: sklearn espera el índice de clase (0/1/2), no one-hot.
6. **Ingesta automática**: ya no hay que copiar tablas de FBref a mano.
7. **Matriz normalizada con `rho=0`**: la rama sin Dixon-Coles no reescalaba la
   Poisson truncada (las probabilidades sumaban ~0.98). Ahora siempre suma 1.

## 🧼 Mejoras de calidad de código (refactor)

1. **Sin "números mágicos"**: todos los multiplicadores y umbrales del modelo se
   movieron al diccionario `PESOS_MODELO` en `ligas_config.py`. Calibrar el
   modelo ahora es cambiar números en un solo sitio, sin tocar las fórmulas.
2. **Persistencia explícita de datos**: `descargar_datos.py` exporta un CSV
   maestro limpio (`base_mundial_2026.csv`) y el predictor lo lee directamente.
   La app del Mundial es ahora **100% offline y ultrarrápida**, sin depender del
   caché interno de `soccerdata`.
3. **Tipado estático (type hints)**: las funciones principales declaran tipos de
   entrada/salida (p. ej. `def predecir_partido(... ) -> dict:`), para que el
   editor detecte errores antes de ejecutar.
4. **UI sin congelarse**: la descarga/cálculo corre en un hilo aparte y *todas*
   las actualizaciones de la interfaz pasan por `self.after(...)`, evitando que
   Windows marque la app como "No responde".

## 📌 Pendiente (no implementado)

- `fuerza_rival_prom`: normalizar el xG según la fuerza de los rivales
  enfrentados.
- Backtest multi-liga / multi-temporada para una calibración más robusta.
