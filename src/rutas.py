"""
Rutas del proyecto.

Centraliza la ubicacion de los archivos de datos y de configuracion. Las rutas
se calculan a partir de la ubicacion de ESTE archivo (no del directorio actual),
asi el programa funciona sin importar desde donde se ejecute.

Estructura:
    <raiz>/
      ├── src/        <- codigo (aqui vive rutas.py)
      └── data/       <- base_mundial_2026.csv, promedios_liga.json, salidas...
"""
import os

SRC = os.path.dirname(os.path.abspath(__file__))   # .../src
RAIZ = os.path.dirname(SRC)                          # .../mundial
DATA = os.path.join(RAIZ, "data")


def data(nombre: str) -> str:
    """Ruta absoluta de un archivo dentro de la carpeta data/."""
    return os.path.join(DATA, nombre)


def raiz(nombre: str) -> str:
    """Ruta absoluta de un archivo en la raiz del proyecto."""
    return os.path.join(RAIZ, nombre)
