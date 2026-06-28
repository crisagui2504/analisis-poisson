"""
Elo de clubes desde ClubElo (http://api.clubelo.com).

Cierra el "punto ciego" del modelo en ligas de clubes: sin esto, `elo_de()`
devolvia ELO_REFERENCIA para todos los clubes, apagando la ponderacion por
fuerza del rival (SoS) y el empuje por jerarquia (peso_elo) en feature_engineering
y calcular_lambdas.

Arquitectura (espejo de la del Mundial, para mantener el flujo de prediccion
100% offline):
  - `descargar_club_elo()` baja UN snapshot de todos los clubes y lo cachea en
    data/club_elo.csv. Es un paso EXPLICITO (ejecuta descargar_club_elo.py),
    igual que descargar_datos.py para el Mundial.
  - `elo_club(nombre)` lee SOLO del cache local (sin red) y casa el nombre de
    FBref con el de ClubElo via normalizacion + alias. Devuelve None si no lo
    encuentra (el llamador usa entonces ELO_REFERENCIA).

LIMITACION: ClubElo solo cubre ligas EUROPEAS. Liga MX (y cualquier liga no
europea) no esta; esos clubes devuelven None y caen al Elo de respaldo.
"""
import datetime as _dt
import os
import re
import unicodedata

import pandas as pd

from rutas import data

CLUB_ELO_CSV = data("club_elo.csv")
_API = "http://api.clubelo.com/{fecha}"

# Tokens genericos de nombre de club que se eliminan al normalizar (prefijos y
# sufijos societarios). NO incluimos palabras distintivas (real, athletic,
# stade, olympique, borussia...) porque diferencian clubes.
_STOP = {
    "fc", "cf", "afc", "sc", "ssc", "ac", "as", "us", "rc", "rcd", "cd", "ud",
    "sd", "ca", "cp", "sv", "vfb", "vfl", "tsg", "ogc", "calcio", "club",
}

# Alias para los casos en que la normalizacion no basta (ClubElo abrevia muy
# distinto a FBref). Clave = nombre estilo FBref/soccerdata; valor = nombre
# EXACTO como aparece en ClubElo. Ambos se normalizan al cargar, asi que pequenas
# variantes de mayusculas/acentos/puntuacion tambien casan.
_ALIAS_RAW = {
    # ── Premier League ──
    "Manchester City": "Man City", "Manchester Utd": "Man United",
    "Manchester United": "Man United", "Newcastle Utd": "Newcastle",
    "Newcastle United": "Newcastle", "Nott'ham Forest": "Forest",
    "Nottingham Forest": "Forest", "Leeds United": "Leeds",
    "Tottenham Hotspur": "Tottenham", "Spurs": "Tottenham",
    "Brighton & Hove Albion": "Brighton", "Brighton and Hove Albion": "Brighton",
    "West Ham United": "West Ham", "Wolverhampton Wanderers": "Wolves",
    "Wolverhampton": "Wolves",
    # ── La Liga ──
    "Atlético Madrid": "Atletico", "Atletico Madrid": "Atletico",
    "Atlético de Madrid": "Atletico", "Real Betis": "Betis",
    "Athletic Club": "Bilbao", "Athletic Bilbao": "Bilbao",
    "Celta Vigo": "Celta", "Celta de Vigo": "Celta", "Real Sociedad": "Sociedad",
    "Deportivo Alavés": "Alaves", "Alavés": "Alaves", "Real Oviedo": "Oviedo",
    # ── Bundesliga ──
    "Bayern Munich": "Bayern", "Bayern München": "Bayern",
    "Bayer Leverkusen": "Leverkusen", "Borussia Dortmund": "Dortmund",
    "Eintracht Frankfurt": "Frankfurt", "Werder Bremen": "Werder",
    "Mainz 05": "Mainz", "Borussia Mönchengladbach": "Gladbach",
    "Mönchengladbach": "Gladbach", "M'Gladbach": "Gladbach",
    "1. FC Köln": "Koeln", "Köln": "Koeln", "Cologne": "Koeln",
    "Hamburger SV": "Hamburg", "St. Pauli": "St Pauli", "Heidenheim": "Heidenheim",
    "RB Leipzig": "RB Leipzig",
    # ── Serie A ──
    "Internazionale": "Inter", "Inter Milan": "Inter", "AC Milan": "Milan",
    "Hellas Verona": "Verona",
    # ── Ligue 1 ──
    "Paris Saint-Germain": "Paris SG", "Paris S-G": "Paris SG",
    "Paris Saint Germain": "Paris SG", "Olympique Marseille": "Marseille",
    "Olympique de Marseille": "Marseille", "Olympique Lyonnais": "Lyon",
    "Stade Rennais": "Rennes", "Stade Brestois": "Brest",
    "RC Strasbourg Alsace": "Strasbourg",
}

# Cache en memoria: {nombre_normalizado_clubelo: elo}. Se carga una vez.
_elo_por_norm = None
_alias_norm = None


def _norm(s):
    """Normaliza un nombre de club: sin acentos, minusculas, sin tokens genericos."""
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    toks = [t for t in s.split() if t and t not in _STOP]
    if not toks:  # no dejes la cadena vacia por culpa del filtro
        toks = [t for t in s.split() if t]
    return " ".join(toks)


def descargar_club_elo(fecha=None, ruta=CLUB_ELO_CSV):
    """
    Baja el snapshot de Elo de TODOS los clubes para `fecha` (hoy por defecto)
    desde la API de ClubElo y lo guarda en `ruta` (data/club_elo.csv).

    Es un paso explicito: el flujo de prediccion NO descarga, solo lee el cache.
    Devuelve el DataFrame descargado.
    """
    if fecha is None:
        fecha = _dt.date.today().isoformat()
    url = _API.format(fecha=fecha)
    df = pd.read_csv(url)
    df = df[df["Elo"].notna()].copy()
    df.to_csv(ruta, index=False, encoding="utf-8")
    print(f"ClubElo: {len(df)} clubes guardados en '{ruta}' (fecha {fecha}).")
    return df


def _cargar():
    """Carga el cache local en memoria (una sola vez). Sin red."""
    global _elo_por_norm, _alias_norm
    if _elo_por_norm is not None:
        return
    _alias_norm = {_norm(k): _norm(v) for k, v in _ALIAS_RAW.items()}
    _elo_por_norm = {}
    if not os.path.exists(CLUB_ELO_CSV):
        return  # sin cache: elo_club() devolvera None hasta que se descargue
    try:
        df = pd.read_csv(CLUB_ELO_CSV)
    except Exception:
        return
    for _, fila in df.iterrows():
        _elo_por_norm[_norm(fila["Club"])] = float(fila["Elo"])


def elo_club(nombre):
    """
    Devuelve el Elo de ClubElo para un club (nombre estilo FBref) o None si no
    esta en el cache (club no europeo, cache no descargado, o nombre sin alias).
    """
    _cargar()
    if not _elo_por_norm:
        return None
    n = _norm(nombre)
    n = _alias_norm.get(n, n)  # aplica alias si existe
    return _elo_por_norm.get(n)


def diagnosticar(nombres):
    """
    Dada una lista de nombres de equipo (estilo FBref), devuelve los que NO se
    pudieron casar con ClubElo. Util para completar _ALIAS_RAW con tus ligas:
    pasa los equipos reales de una liga y revisa que falto.
    """
    return [nm for nm in nombres if elo_club(nm) is None]


def recargar():
    """Fuerza recargar el cache en memoria (tras una descarga nueva)."""
    global _elo_por_norm
    _elo_por_norm = None
    _cargar()
