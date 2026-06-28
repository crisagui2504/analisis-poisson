# 📦 `src/` — Código fuente

Todo el código del predictor, organizado por capas. Cada subcarpeta tiene su
propio README con el detalle de sus módulos.

| Carpeta / archivo | Qué contiene |
|-------------------|--------------|
| [`modelo/`](modelo/README.md) | El modelo matemático: features, lambdas, matriz de Poisson y el orquestador de la predicción. |
| [`datos/`](datos/README.md) | Ingesta desde FBref, capa de fuentes intercambiables y scripts de descarga/actualización. |
| [`interfaz/`](interfaz/README.md) | La aplicación gráfica (tkinter) y su estilo. |
| [`analisis/`](analisis/README.md) | Simulación Monte Carlo del torneo y backtests contra el mercado. |
| `ligas_config.py` | **Configuración compartida** (vive aquí, fuera de las subcarpetas, porque la usan todas): ligas, las 48 selecciones (español ↔ FBref), `ELO_RANKING`, `GRUPOS_MUNDIAL`, `PESOS_MODELO`, `FACTOR_LOCAL` (localía por liga) y los lectores de grupos editables. `elo_de()` consulta ClubElo (`datos/club_elo.py`) como respaldo para clubes. |
| `rutas.py` | Rutas absolutas a `data/` y a la raíz, calculadas desde la ubicación del archivo (no del directorio actual). |

## Cómo se resuelven los imports

El proyecto usa imports planos (`from calcular_lambdas import ...`). Para que
funcionen estando en subcarpetas, cada script **ejecutable** lleva al inicio un
pequeño *bootstrap* que añade `src/` y todas sus subcarpetas a `sys.path`:

```python
import os as _os, sys as _sys
_SRC = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _sub in ("", "modelo", "datos", "interfaz", "analisis"):
    _sys.path.insert(0, _os.path.join(_SRC, _sub))
```

Así puedes ejecutar cualquier script directamente desde la raíz del proyecto sin
configurar `PYTHONPATH` ni instalar el paquete.
