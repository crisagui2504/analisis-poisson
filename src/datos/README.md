# 🗄️ `src/datos/` — Ingesta y fuentes de datos

Todo lo que trae y normaliza los datos de los partidos. El esquema normalizado
(columnas `Date, Team, Opponent, Venue, Result, GF, GA, Poss, Sh, SoT, xG, xGA,
Fls, CrdY, CrdR`) es el contrato que consume el modelo.

## Módulos

### `ingest_fbref.py`
Núcleo de la ingesta desde FBref (vía `soccerdata`) y de la base maestra.
- **`construir_historial_equipo_directo(fbref, equipo)`** — lee shooting + misc de
  un equipo y normaliza columnas (sin `read_schedule`).
- **`construir_historial_equipo(df, equipo)`** — filtra un equipo de un DataFrame
  ya cargado (lo usa la base maestra del Mundial).
- **`cargar_historial_csv()` / `existe_csv_maestro()`** — leen `data/base_mundial_2026.csv`.
- **`fusionar_historiales(viejo, nuevo)`** — fusión **incremental** sin duplicar
  (dedup por `Team+Date+Opponent`; prevalece el dato nuevo).
- **`actualizar_csv_maestro(...)` / `actualizar_mundial()`** — actualizan el CSV
  agregando solo partidos nuevos.
- **`exportar_historiales_csv(...)`** — genera la base maestra desde cero.
- **`ruta_csv_liga(liga, temporada)` / `actualizar_liga_csv(...)`** — base maestra
  **por liga de clubes** (espejo del Mundial) con **cold-start** (concatena la
  temporada anterior para equipos con pocos partidos).
- **`promedios_desde_csv(equipos=None)`** — promedios del torneo desde la base
  maestra, filtrable (lo usa el bracket para promediar solo clasificados).

### `club_elo.py` — Elo de clubes (ClubElo)
- **`descargar_club_elo()`** baja el snapshot a `data/club_elo.csv`;
  **`elo_club(nombre)`** lo lee del caché con normalización + alias. Solo ligas
  europeas. Lo consulta `ligas_config.elo_de()` como respaldo para clubes.

### `proveedores.py` — capa de fuentes intercambiables (plug-in)
- **`ProveedorDatos`** — contrato común. Cada API es una subclase independiente.
  Incluidas: **`FBrefProvider`** (xG/tiros, sin clave) y **`FootballDataOrgProvider`**
  (resultados del Mundial, requiere API key gratis).
- **`historial_combinado(...)` / `actualizar_csv(...)`** — cruzan todas las fuentes
  disponibles; si una falla, las demás siguen (aislamiento).
- **`diagnostico()`** — imprime qué fuentes están activas.
- Agregar otra API = una subclase nueva registrada en `PROVEEDORES`.

### Scripts ejecutables
- **`actualizar_datos.py`** — actualización **incremental** (recomendada). Pasa los
  equipos que jugaron para que tarde segundos.
- **`descargar_datos.py`** — descarga **completa** del Mundial (lenta, con pausas).
- **`calcular_promedios_liga.py`** — genera `data/promedios_liga.json` desde el
  caché HTML local de soccerdata (sin red).
- **`descargar_club_elo.py`** — refresca el caché de Elo de clubes (ClubElo).
- **`descargar_liga_csv.py`** — genera/actualiza la base maestra de una liga de
  clubes (predicción offline e instantánea).
- **`actualizar_elo.py`** — recalcula el Elo de **selecciones** desde los
  resultados del Mundial a `data/elo_override.json` (lo aplica `ligas_config`).

## API keys
Copia `apis.example.json` (en la raíz) a **`apis.local.json`** y pega tu clave, o
usa la variable de entorno `FOOTBALL_DATA_ORG_KEY`. `apis.local.json` **no se sube
a git**.
