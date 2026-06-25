# 🖥️ `src/interfaz/` — La aplicación gráfica

Interfaz de escritorio en **tkinter** con estilo moderno tipo dashboard. Es lo que
abre `Abrir Predictor.bat`.

## Módulos

### `app_gui.py` — la aplicación principal
La clase **`PredictorApp(tk.Tk)`** arma toda la ventana. Toda descarga/cálculo
corre en un **hilo aparte** y las actualizaciones de UI pasan por `self.after(...)`,
así la ventana nunca se congela.

Componentes destacados:
- **`Cabecera`, `Tarjeta`, `BarraProbabilidad`** — widgets de `Canvas` con esquinas
  redondeadas, degradados y barras de probabilidad.
- **`_iniciar_prediccion` / `_mostrar_resultado`** — predicen un partido y muestran
  el panel en pestañas (Predicción / Análisis): tarjetas 1-X-2 con **cuota justa**,
  mercados (incl. asiáticos), **Top 5 marcadores**, **radar de dominio** y mapa de
  calor.
- **`_iniciar_montecarlo` / `_mostrar_montecarlo`** — corren la simulación del
  torneo y muestran el ranking de candidatos con gráfico de barras.
- **`_abrir_editor_grupos`** — ventana para editar los 12 grupos (sorteo oficial),
  con validación de 48 selecciones únicas; guarda en `data/grupos_mundial.json`.
- **`_render_forma_sidebar`** — los círculos de forma (🟢W / ⚪D / 🔴L) y el descanso.

### `paleta.py`
**Design tokens**: todos los colores y la tipografía en un solo lugar. Cambia un
color aquí y toda la app se actualiza.

### `tema_oscuro.py`
Estilo de los widgets `ttk` (combos, sliders, progreso, checks, pestañas) acorde a
la paleta oscura. Se aplica con `aplicar_tema(root)`.

> Ejecutar: `py -3.11 src/interfaz/app_gui.py` (o el `.bat`).
