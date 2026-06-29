# Decisiones técnicas

> Detectadas en el código y los commits, con su porqué y lo descartado.

## Modelo
- **Poisson + corrección Dixon-Coles (`rho`)**. *Por qué*: el Poisson puro
  subestima los empates de pocos goles; `rho` reajusta (0,0)/(1,0)/(0,1)/(1,1).
- **Promedios EWM (span=10) en vez de media simple (SMA)**. *Por qué*: da más peso
  a lo reciente (forma); está calibrado. SMA queda como opción.
- **Shrinkage hacia el promedio del torneo (`k`)**. *Por qué*: con pocos partidos
  por equipo, evita sobre-interpretar muestras chicas.
- **`rho`/`k` por contexto**: Mundial `-0.05`/`5`, clubes `-0.05`/`2`. *Por qué*:
  selecciones juegan pocos partidos (más shrinkage); clubes ~38 (menos).
- **Empuje Elo head-to-head (`peso_elo`)**: fijo en `0.65`, ahora **calibrable**
  por RPS (`calibrar_peso_elo`). Hallazgo: el backtest no lo aplicaba antes.

## Datos y fuerza (Elo)
- **Base maestra CSV offline** (Mundial y por liga) en vez de scrapear en vivo.
  *Por qué*: predicción instantánea y sin depender de la red/HTML de FBref.
- **Elo en cascada** en `elo_de()`: selección → club (**ClubElo**) → `1650`.
  *Por qué*: sin ClubElo, los clubes caían todos a 1650 y se apagaba SoS + jerarquía.
- **ClubElo como puente inter-ligas** (comparable entre ligas europeas).
- **Elo de selecciones dinámico** (`actualizar_elo.py`): recalcula desde resultados,
  partiendo SIEMPRE de `ELO_RANKING_BASE`. *Por qué*: no acumular entre corridas.
- **Promedios solo de clasificados** en eliminatorias. *Por qué*: la media de la fase
  de grupos deja de ser representativa cuando los débiles ya cayeron.

## Monte Carlo
- **Simular el bracket confirmado** (`bracket_eliminatoria.json`) si existe, en vez de
  sembrar los grupos. *Por qué*: usar los cruces reales.
- **Penales sesgados por Elo, comprimidos** (`PESO_PENALES_ELO=0.5`). *Por qué*: el
  volado 50/50 ignora la jerarquía, pero los penales son más azar que el juego.

## Evaluación
- **RPS** además de log_loss/Brier. *Por qué*: respeta el orden 1‑X‑2.
- **Time-weighting (Dixon-Coles) opt-in**, default sigue EWM. *Por qué*: no alterar
  el default ya calibrado; calibrarlo por RPS antes de adoptarlo.

## Descartado (con motivo, en el código/commits)
- **Splits local/visitante**: "medidos: empeoran" → off.
- **xG a nivel de tiro (StatsBomb+XGBoost)**: no encaja con datos agregados de FBref.
- **ClubElo para selecciones**: ClubElo solo tiene clubes (no existe ese dato).
- **Elo de clubes para Liga MX**: ClubElo no la cubre → quedan en 1650.
