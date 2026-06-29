# 💾 `data/` — Bases de datos y salidas

Archivos de datos que el programa lee y escribe. Las rutas se resuelven con
`src/rutas.py`, así que funcionan sin importar desde dónde ejecutes.

| Archivo | Qué es | ¿En git? |
|---------|--------|----------|
| `base_mundial_2026.csv` | **Base maestra** del Mundial: historial limpio y normalizado de las 48 selecciones. El predictor la lee directamente → 100% offline. La genera/actualiza `src/datos/`. | ✅ sí |
| `promedios_liga.json` | Promedios del torneo (xG favor/contra, tiros) que usa el shrinkage. | ✅ sí |
| `grupos_mundial.json` | Grupos del Mundial editados desde la app (✏️ Editar grupos). Tiene prioridad sobre `GRUPOS_MUNDIAL`. Se crea al guardar. | ❌ local |
| `bracket_eliminatoria.json` | Cuadro de eliminatorias confirmado (cruces reales). Si existe, el Monte Carlo simula desde estos cruces en vez de sembrar los grupos. | ✅ sí |
| `elo_override.json` | Elo de selecciones recalculado desde los resultados del Mundial (`src/datos/actualizar_elo.py`). Si existe, sobrescribe `ELO_RANKING`. Regenerable. | ❌ ignorado |
| `club_elo.csv` | Cache del Elo de clubes (ClubElo). Lo genera `src/datos/descargar_club_elo.py`. Solo ligas europeas. Regenerable. | ❌ ignorado |
| `liga_<liga>_<temporada>.csv` | **Base maestra por liga de clubes** (mismo esquema que `base_mundial`). La genera `src/datos/descargar_liga_csv.py`; si existe, la predicción de esa liga es offline e instantánea. Regenerable. | ❌ ignorado |
| `montecarlo_resultados.csv` | Salida de la simulación (% de título por selección). Regenerable. | ❌ ignorado |
| `resultados_backtest.csv` | Salida de la calibración `rho`/`k`. Regenerable. | ❌ ignorado |

> Las **API keys** no viven aquí: `apis.local.json` está en la raíz del proyecto
> (y nunca se sube a git).
