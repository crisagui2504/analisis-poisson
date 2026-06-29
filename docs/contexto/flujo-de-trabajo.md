# Flujo de trabajo

> Cómo hacer un cambio en este repo. No hay CI ni tests automatizados, así que la
> validación es manual (compila + backtest + smoke ad-hoc).

## Hacer un cambio
1. **Ubica la capa**: modelo (`src/modelo/`), datos (`src/datos/`), simulación/eval
   (`src/analisis/`), GUI (`src/interfaz/`). Config compartida en `src/ligas_config.py`.
2. **Calibrar = editar `PESOS_MODELO`** (o `ELO_RANKING`/`FACTOR_LOCAL`), no las fórmulas.
3. **Rutas** siempre con `rutas.data("…")`. Scripts ejecutables: bootstrap de path + `if __name__ == "__main__"`.
4. **Verifica** (ver checklist).
5. **Actualiza el `README.md` de la carpeta** afectada (y el raíz si cambia el flujo).
6. `npx repomix` para regenerar `repomix-output.xml`.
7. **Commit en una rama** (no en `main`), mensaje en español; `git push`.

## Checklist de "terminado"
- [ ] `py -3.11 -m compileall -q src` sin errores.
- [ ] Smoke: importar los módulos-librería sin fallo (excluye scripts de descarga).
- [ ] El cambio no introduce **fuga de datos** (promedios con `shift(1)`; predecir solo con el pasado).
- [ ] Si afecta al modelo: `backtest_cuotas` no empeora (log_loss/Brier/**RPS**) vs el mercado.
- [ ] READMEs de carpeta actualizados; `repomix-output.xml` regenerado.

## Mantener los datos al día
```
py -3.11 src/datos/actualizar_datos.py [Equipo ...]   # incremental Mundial
py -3.11 src/datos/calcular_promedios_liga.py          # promedios del torneo
py -3.11 src/datos/actualizar_elo.py [YYYY-MM-DD]      # Elo de selecciones
py -3.11 src/datos/descargar_club_elo.py               # Elo de clubes (caché)
py -3.11 src/datos/descargar_liga_csv.py "<liga>"      # base maestra de una liga
```

## "Deploy"
- No hay deploy: es una **app de escritorio**. Se ejecuta con `Abrir Predictor.bat`
  o `py -3.11 src/interfaz/app_gui.py`.
- Mover a otra PC: `py -3.11 -m pip install -r requirements.txt`. Para
  football-data.org: copiar `apis.example.json` → `apis.local.json` y poner la clave.
- [PENDIENTE: no hay versionado de releases, CI/CD ni empaquetado distribuible.]
