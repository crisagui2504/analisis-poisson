# Errores conocidos y gotchas

> Intuidos del código, comentarios y README. No es una lista de bugs abiertos
> (no hay issue tracker en el repo).

## Entorno
- **`python` no funciona** en el equipo (lo secuestra la Microsoft Store): usar
  **`py -3.11`** o `Abrir Predictor.bat`. Documentado en el README.
- **Consola de Windows**: las tildes/ñ pueden verse como `T�rkiye`/`Cura�ao` al
  imprimir. Es cosmético (la data está bien en UTF-8).
- **Git en Windows**: avisos `LF will be replaced by CRLF` al commitear. Inofensivo.

## Scripts que ejecutan al importarse ⚠️
- `descargar_datos.py`, `actualizar_datos.py` y `calcular_promedios_liga.py` corren su
  lógica **a nivel de módulo** (sin `if __name__ == "__main__"`). **Importarlos dispara
  scraping/escritura de archivos** (incluido reescribir `base_mundial_2026.csv` /
  `promedios_liga.json`). No los importes en pruebas; ejecútalos como script.
  Los módulos nuevos (`club_elo`, `descargar_club_elo`, `descargar_liga_csv`,
  `actualizar_elo`) sí llevan guard.

## Datos
- **El CSV trae una fila por equipo por partido** (Argentina vs Algeria aparece dos
  veces, una por equipo). **No son duplicados**: borrarlas rompe el historial/h2h.
- **Columna `Opponent` inconsistente**: a veces con código de país (`dz Algeria`) y a
  veces sin él. Lo normaliza `_limpiar_nombre_rival`; limpiarlo en origen es opcional.
- **ClubElo no cubre Liga MX ni selecciones** → esos equipos caen a `ELO_REFERENCIA=1650`
  (se apaga el empuje por Elo para ellos).
- **Archivos estáticos que envejecen con el torneo**: `promedios_liga.json`,
  `elo_override.json` y `club_elo.csv` hay que regenerarlos para que reflejen lo último.
- **FBref no tiene API oficial**: si cambia su HTML, `soccerdata` puede romperse; úsalo
  con pausas (anti-bloqueo) — los scripts las incluyen.

## Modelo
- **`peso_elo=0.65` puede ser alto** y aplastar señales de forma/tiros; calibrar con
  `calibrar_peso_elo` (por RPS). El backtest no lo aplicaba hasta integrar el Elo de clubes.
- **Splits local/visitante empeoran** las predicciones → off por defecto (no reactivar sin medir).
- **Inter-ligas (`predecir_partido_interligas`)**: no aplica head-to-head (dos equipos
  de ligas distintas casi nunca aparecen enfrentados en los datos de liga).
- Una `temporada` con pocos partidos de un equipo lanza "No hay suficientes partidos
  completos" (umbral `min_previos`/features incompletas).

## [PENDIENTE]
- [PENDIENTE: no hay tests que fijen estos comportamientos; son acuerdos implícitos.]
