# Glosario

## Conceptos del modelo
- **xG / xGA**: goles esperados a favor / en contra (de FBref). Si faltan (típico en
  selecciones), se usan goles reales (GF/GA).
- **λ (lambda)**: goles esperados de un equipo en un partido; entra al Poisson.
- **Poisson**: distribución que da la probabilidad de cada nº de goles.
- **Dixon-Coles / `rho`**: corrección a las celdas de pocos goles de la matriz Poisson.
- **`k` (shrinkage)**: fuerza con que el promedio de un equipo se mezcla con el de la liga.
- **EWM**: media con decaimiento exponencial (span=10); pondera lo reciente.
- **Time-weighting**: variante (`suavizado="tiempo"`) que pondera por **días reales**.
- **Elo / `ELO_REFERENCIA` (1650)**: fuerza de un equipo; rival "promedio" = 1650.
- **`peso_elo`**: cuánto empuja la diferencia de Elo los λ hacia el favorito.
- **SoS (`sos_prom`)**: Strength of Schedule = Elo medio de los rivales enfrentados.
- **Localía (`FACTOR_LOCAL`)**: multiplicador del λ local, por liga (Mundial = neutral).
- **Cold-start**: completar a un equipo con pocos partidos con la temporada anterior.

## Métricas
- **log_loss / Brier**: error de las probabilidades vs el resultado real.
- **RPS** (Ranked Probability Score): error que respeta el **orden** 1‑X‑2.
- **MoV**: margen de victoria (bono al `K` del Elo).
- **ROI**: rentabilidad simulada apostando al "valor" del modelo. **devig**: quitar
  el margen de la casa a las cuotas.

## Mercados
- **1X2**: local / empate / visitante. **BTTS**: ambos anotan. **Over/Under 1.5/2.5/3.5**:
  total de goles. **Portería a cero / clean sheet**: el rival no marca. **h2h**: historial directo.

## Entidades / archivos
- **`base_mundial_2026.csv`**: base maestra del Mundial (48 selecciones).
- **`liga_<liga>_<temp>.csv`**: base maestra por liga de clubes.
- **`club_elo.csv`**: caché de Elo de clubes (ClubElo).
- **`promedios_liga.json`**: promedios del torneo para el shrinkage.
- **`grupos_mundial.json`**: grupos editables (override).
- **`bracket_eliminatoria.json`**: cruces confirmados de eliminatorias.
- **`elo_override.json`**: Elo de selecciones recalculado (override).
- **`montecarlo_resultados.csv`**: salida de la simulación.
- **`PESOS_MODELO`**: dict central con todos los pesos calibrables.

## Siglas
FBref · ClubElo · DC (Dixon-Coles) · SoS · EWM · RPS · MoV · KO (eliminatorias) ·
FD (football-data) · GUI · PJ (partidos jugados).
