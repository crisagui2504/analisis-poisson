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
    *Predecir partido* el programa primero trae los partidos nuevos de **solo los
    2 equipos del partido** (fusión incremental, sin borrar el CSV) y **luego**
    predice. Usa **fuentes rápidas** (API REST como football-data.org) → segundos,
    no minutos. Si no hay API configurada o la red falla, avisa y predice con los
    datos locales.

En el panel lateral, tras predecir, aparece la **forma reciente** (últimos 5:
🟢W / ⚪D / 🔴L) y los **días de descanso** de cada equipo.

Panel derecho (tras pulsar *Predecir partido*), organizado en **dos pestañas**:

*Pestaña «Predicción»:*
- **3 tarjetas 1-X-2** con porcentaje **y cuota justa** (1/probabilidad).
- **Barra de probabilidad** 1-X-2: reparto visual.
- **xG esperados (λ)** de cada equipo.
- **Mercados**: *Ambos anotan (BTTS)*, *Más de 2.5*, *Portería a 0*, y
  **mercados asiáticos** *Más de 1.5*, *Más de 3.5*, *Menos de 2.5* (con cuota).
- **Top 5 marcadores** más probables con su cuota justa.

*Pestaña «Análisis»:*
- **Radar de dominio** (telaraña): compara ataque, posesión, tiros, defensa y
  disciplina del local (verde) vs visitante (rojo).
- **Mapa de calor**: probabilidad de cada marcador exacto (0-0, 1-0, 2-1, …).

---

## 🧠 Cómo funciona (el modelo, paso a paso)

1. **Ingesta** (`ingest_fbref.py`)
   Descarga de FBref el historial de cada equipo (goles, xG, tiros a puerta,
   posesión, faltas, tarjetas) y normaliza los nombres de columna.

2. **Ingeniería de características** (`feature_engineering.py`)
   - Promedios con **decaimiento exponencial (EWM, span=10)**: pesa más los
     partidos recientes (estado de forma) que los antiguos. El span se calibró
     contra el mercado (ver backtest); EWM con span largo superó a la media móvil
     simple. Además calcula **xGD** (diferencial de xG, "dominio"), **tasa de
     conversión** (goles/tiro a puerta) y la **Fuerza del Calendario** (`sos_prom`).
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
| `proveedores.py` | **Capa de fuentes de datos intercambiables** (plug-in). FBref + football-data.org, independientes entre sí. Agregar otra API = una subclase más. |
| `apis.example.json` | Plantilla para tus API keys (cópiala a `apis.local.json`, que no se sube a git). |
| `paleta.py` | **Paleta de colores y tipografía** de la interfaz (design tokens). Cambia un color aquí y toda la app se actualiza. |
| `tema_oscuro.py` | Estilo moderno de los widgets ttk (combos, sliders, progreso, checks). |
| `calcular_promedios_liga.py` | Genera `promedios_liga.json` leyendo el caché local. |
| `descargar_datos.py` | Descarga masiva del Mundial equipo por equipo (con pausas anti-bloqueo) y exporta el CSV maestro. |
| `actualizar_datos.py` | **Actualización incremental**: trae solo los partidos nuevos de FBref y los fusiona en el CSV maestro sin borrarlo. |
| `montecarlo_mundial.py` | **Motor de simulación**: juega el Mundial completo (grupos + eliminatorias) miles de veces y estima la probabilidad de título de cada selección. |
| `backtest.py` | Calibra `rho` y `k` contra resultados históricos. |
| `backtest_cuotas.py` | **Backtest contra el mercado**: compara el modelo con las cuotas de cierre reales (Pinnacle/Bet365 de Football-Data.co.uk) y simula ROI. |
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

### Fuentes de datos / APIs (arquitectura desacoplada)
El proyecto **no depende de una sola fuente**. `proveedores.py` define una capa
*plug-in*: cada API es un proveedor independiente con el mismo contrato, y si una
falla o no está configurada, las demás siguen funcionando.

- **FBref** (vía soccerdata): goles, tiros, posesión, xG. No necesita clave.
- **football-data.org**: resultados/goles del Mundial (plan gratuito). Necesita
  una API key gratis.

Ver qué fuentes tienes activas:
```powershell
py -3.11 proveedores.py
```
Activar football-data.org: registra una key gratis en su web, copia
`apis.example.json` a **`apis.local.json`** y pega tu clave (o define la variable
de entorno `FOOTBALL_DATA_ORG_KEY`). `apis.local.json` no se sube a git.

Actualizar **cruzando todas las fuentes disponibles** (más cobertura/precisión):
```powershell
py -3.11 proveedores.py update Spain Brazil   # solo esos equipos
py -3.11 proveedores.py update                # todas las selecciones
```
La fusión deduplica por `Team + Date` y la fuente más confiable (FBref) prevalece.

**Agregar otra API** (p. ej. API-Football): crea una subclase de `ProveedorDatos`
en `proveedores.py`, implementa `disponible()` y `historial_equipo()` devolviendo
el esquema normalizado, y regístrala en `PROVEEDORES`. Nada más cambia.

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

### Backtest contra cuotas reales (¿le gana al mercado?)
Mide si el modelo iguala o supera a las casas de apuestas, usando las **cuotas de
cierre reales** (Pinnacle, Bet365) que publica gratis Football-Data.co.uk:
```powershell
py -3.11 backtest_cuotas.py            # Premier League 2024-25
py -3.11 backtest_cuotas.py SP1 2425   # La Liga 2024-25 (E0/SP1/I1/D1/F1)
```
Descarga el CSV de la liga, reconstruye el historial de cada equipo **del mismo
archivo** (100% offline, sin FBref) y predice cada partido **sin fuga de datos**
(solo con partidos anteriores). Reporta el `log_loss`/Brier/acierto del modelo vs
el del mercado, y un **simulador de ROI** apostando solo donde el modelo detecta
valor. *Nota realista:* batir las cuotas de cierre es muy difícil; un log_loss
peor que el mercado con un ROI ligeramente positivo suele ser ruido, no una
ventaja durable.

**Calibración de `rho`/`k`** (`backtest_cuotas.calibrar([df1, df2, ...])`): un
barrido sobre las 5 grandes ligas europeas (≈1500 partidos) mostró que **`k`
(shrinkage) es la palanca real, no `rho`**. Recalibrado tras las nuevas variables:
- `rho = -0.05` (el óptimo es plano cerca de 0).
- **Clubes**: `k = 2` (muchos partidos → poco shrinkage).
- **Mundial**: se mantiene `k = 5`. Las selecciones tienen **pocos partidos**
  (7–25) y necesitan MÁS shrinkage; un `k` bajo las sobreajustaría. Los defaults
  son **por contexto**, no un valor único.

**Auditoría anti-fuga (EWM)** (`backtest.auditar_ewm_sin_fuga()`): confirma que
el suavizado `.shift(1).ewm().mean()` es causal — no filtra datos del partido
actual ni del futuro hacia los promedios del pasado. Pasa sin fuga.

**Confirmación con Monte Carlo**: tras los Sprints 1-2, las potencias reales
suben su % de título (España 3.7→6.0%, Inglaterra 4.2→5.6%, Argentina 9.5→11.3%)
y bajan los beneficiarios de grupo débil — señal de que el modelo captura mejor
la calidad subyacente.

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
8. **Tiros a puerta ahora activos**: `tiros_puerta_adj` se calculaba pero
   `calcular_lambdas` lo ignoraba. Ahora aplica un ajuste ofensivo **continuo**
   (no escalón) según cuánto remata por encima de la media.
9. **Variables conectadas y nuevas** (medidas con `backtest_cuotas.py`):
   - **EWM** en vez de media móvil (span=10, calibrado): pesa más lo reciente.
   - **Fuerza del Calendario** (`sos_prom`) ahora se lee en los lambdas (±3%).
   - **xGD** (diferencial de xG): bono de dominio (±3%).
   - **Tasa de conversión** (goles/tiro a puerta): premia/penaliza eficiencia.
   - **Head-to-Head**: paternidad histórica entre dos selecciones (±4%).
   - Efecto medido en clubes: log_loss **1.0251 → 1.0196** y acierto
     **49.1% → 50.6%** (la mejora se logró calibrando el span del EWM; un span
     corto empeoraba el modelo — por eso se mide cada cambio).
   - **Splits local/visitante** (`procesar_equipo(venue=...)`): implementados y
     medidos, pero **empeoran** el modelo (1.018 → 1.028) porque partir la
     muestra a la mitad añade ruido; la localía ya la cubre `factor_local`. Quedan
     como opción **apagada por defecto**.

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

- **Backtest multi-temporada**: hoy la calibración usa varias ligas pero una sola
  temporada (2024-25); ampliarlo a varias temporadas daría parámetros más robustos.
- **xT (Expected Threat)** desde datos de eventos (StatsBomb) y **modelo a nivel
  jugador / PSxG** (FBref `read_player_match_stats`) — saltos de arquitectura mayores.
- **Score effects** medidos (tiempo real en ventaja): requiere datos jugada-a-jugada
  que `soccerdata` no expone.

> Nota: la "fuerza del rival" (normalizar según el Elo de los rivales enfrentados)
> y el "backtest multi-liga" que figuraban aquí **ya están implementados** —
> ponderación Elo/SoS en `feature_engineering.py` y `backtest_cuotas.calibrar()`
> sobre 5 ligas.
