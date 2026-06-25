@echo off
REM ============================================================
REM  Predictor de Futbol - Mundial 2026
REM  Doble clic para abrir la aplicacion.
REM ============================================================
title Predictor de Futbol - Mundial 2026

REM Ir a la carpeta donde esta este .bat (la del proyecto)
cd /d "%~dp0"

echo Abriendo el Predictor de Futbol...
echo (Puedes cerrar esta ventana negra una vez que aparezca la aplicacion)
echo.

REM Usamos el lanzador "py" porque "python" en este equipo esta
REM secuestrado por el atajo de la Microsoft Store y falla.
py -3.11 src\interfaz\app_gui.py

REM Si la app cierra por un error, la ventana queda abierta para leerlo.
if errorlevel 1 (
    echo.
    echo ------------------------------------------------------------
    echo La aplicacion se cerro con un error. Revisa el mensaje arriba.
    echo ------------------------------------------------------------
    pause
)
