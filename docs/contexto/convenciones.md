# Convenciones

> Inferidas del código y los commits. No hay linter/formatter ni guía escrita
> formal, así que esto refleja la práctica observada.

## Idioma y nombres de equipos
- **Código, comentarios y docstrings en español**, en general **sin tildes** dentro
  del código fuente (p. ej. "formula", "calculo") por compatibilidad; los README sí usan tildes.
- Nombres de equipo **internos = forma FBref en inglés** ("South Africa", "Congo DR").
  La GUI muestra español vía `NOMBRE_DISPLAY`. Rivales se canonizan con
  `_limpiar_nombre_rival` (+ `ELO_ALIAS` / alias de ClubElo).

## Naming
- `snake_case` para funciones y variables; **MAYÚSCULAS** para constantes/config
  (`PESOS_MODELO`, `ELO_RANKING`, `FACTOR_LOCAL`, `TEMPORADAS`).
- Prefijo `_` para helpers privados (`_limpiar_nombre_rival`, `_ensamblar_resultado`,
  `_gana_penales`).
- Docstrings en todas las funciones del API público (ver commit "docstrings en todo el API publico").

## Patrones que usamos
- **Configuración centralizada en `ligas_config.py`**: pesos del modelo en
  `PESOS_MODELO`, fuerzas en `ELO_RANKING`, localía en `FACTOR_LOCAL`. Calibrar = editar ahí.
- **Rutas siempre vía `rutas.data("archivo")`** (nunca rutas relativas a mano).
- **Overrides en JSON que `ligas_config` funde solo**: `grupos_mundial.json`,
  `elo_override.json` (parten de un *base* para no acumular).
- **Funciones parametrizadas por `ruta`/`promedios`** para reusarlas (Mundial vs liga).
- **Sin fuga de datos**: los promedios usan `shift(1)`; el backtest predice cada
  partido solo con los anteriores.
- Scripts ejecutables: bootstrap de `sys.path` + lógica real bajo `if __name__ == "__main__"`.

## Prohibido / a evitar
- **`python`** en este equipo (lo secuestra la Microsoft Store) → usar **`py -3.11`**.
- **No editar las fórmulas** de `calcular_lambdas`/`matriz_poisson` para calibrar:
  cambiar `PESOS_MODELO`.
- **Splits local/visitante**: medidos, **empeoran** → quedan `off` por defecto.
- Evitar que los scripts de descarga corran al *importarse* (los nuevos llevan guard `__main__`; algunos viejos no — ver errores-conocidos).

## Tests
- **No hay framework de tests.** Validación = `backtest_cuotas` (log_loss/Brier/**RPS**
  vs mercado), `backtest.auditar_ewm_sin_fuga()`, y scripts de comprobación ad-hoc.

## Commits
- Mensajes **en español**, imperativos o estilo "Sprint N: …" / "Fix: …".
- Sin convención formal (no Conventional Commits). [PENDIENTE: no hay plantilla de PR/commit.]
