"""
Configuracion de ligas y equipos precargados para el Mundial 2026.
"""

# ── Pesos y umbrales del modelo de lambdas ──────────────────────────────────
# Centralizados aqui para poder calibrar el modelo sin tocar las formulas
# matematicas en calcular_lambdas.py. Cambia un numero aqui y se aplica en
# todo el calculo.
PESOS_MODELO = {
    # Localia (solo se aplica si neutral=False; el Mundial juega en sede neutral)
    "factor_local": 1.10,

    # Fatiga: si un equipo descanso poco y el rival mucho, penaliza su ataque
    "factor_descanso": 0.95,
    "umbral_descanso_bajo": 4,   # dias: menos que esto = poco descanso
    "umbral_descanso_alto": 6,   # dias: mas que esto = bien descansado

    # Forma reciente (puntos promedio por partido en la ventana)
    "bonus_racha": 1.03,
    "penal_racha": 0.97,
    "umbral_racha_alta": 2.0,
    "umbral_racha_baja": 1.0,

    # Posesion: un equipo que controla mas el balon genera algo mas de peligro
    "bonus_posesion": 1.02,
    "umbral_posesion": 55,

    # Disciplina: un equipo indisciplinado concede algo mas al rival
    "bonus_disciplina": 1.02,
    "umbral_disciplina": 20,

    # Diferencia de fuerza Elo entre los dos equipos del partido. Empuja los
    # lambdas hacia el favorito segun la formula Elo (expectativa 0..1). 0 lo
    # desactiva; ~0.65 hace que un gigante se imponga a un equipo chico aunque
    # este venga en racha.
    "peso_elo": 0.65,

    # Valores por defecto cuando FBref no publica el dato (selecciones)
    "default_racha": 1.5,
    "default_posesion": 50,
    "default_disciplina": 15,
}


# ── Ranking de fuerza (Elo) ──────────────────────────────────────────────────
# Elo aproximado de cada seleccion. Se usa para ponderar los goles por la fuerza
# del rival (Strength of Schedule): anotar a un gigante "infla" el valor, anotar
# a un equipo debil lo "desinfla". Ajusta los numeros aqui para recalibrar.
ELO_REFERENCIA = 1650  # rival "promedio"; factor = elo_rival / ELO_REFERENCIA

ELO_RANKING = {
    # Selecciones del Mundial 2026 (nombres tal como los devuelve FBref)
    "Argentina": 2120, "France": 2110, "Spain": 2100, "England": 2070,
    "Brazil": 2060, "Portugal": 2050, "Netherlands": 2040, "Germany": 2010,
    "Belgium": 1990, "Colombia": 1990, "Uruguay": 1980, "Croatia": 1970,
    "Morocco": 1970, "Senegal": 1930, "Switzerland": 1920, "Japan": 1920,
    "Ecuador": 1900, "Mexico": 1900, "Norway": 1900, "Türkiye": 1900,
    "United States": 1900, "Korea Republic": 1860, "Austria": 1860,
    "Sweden": 1860, "Egypt": 1850, "Scotland": 1840, "IR Iran": 1840,
    "Côte d'Ivoire": 1840, "Algeria": 1820, "Czechia": 1820, "Paraguay": 1820,
    "Tunisia": 1820, "Canada": 1830, "Australia": 1810, "South Africa": 1780,
    "Bosnia & Herz.": 1760, "Ghana": 1760, "Qatar": 1750, "Uzbekistan": 1750,
    "Congo DR": 1740, "Saudi Arabia": 1740, "Iraq": 1720, "Panama": 1720,
    "Jordan": 1700, "Cabo Verde": 1680, "New Zealand": 1650, "Curaçao": 1620,
    "Haiti": 1600,
    # Rivales frecuentes de clasificatorias (mejoran el calculo de SoS)
    "Serbia": 1850, "Nigeria": 1850, "Poland": 1850, "Ukraine": 1850,
    "Italy": 2000, "Denmark": 1900, "Peru": 1750, "Chile": 1820,
    "Venezuela": 1700, "Bolivia": 1600, "Iceland": 1700, "Greece": 1800,
    "Hungary": 1800, "Honduras": 1650, "Guatemala": 1550, "Zambia": 1600,
    "Guinea": 1650, "Mozambique": 1450, "Uganda": 1500, "Botswana": 1450,
    "Mauritania": 1500, "Somalia": 1300, "Bangladesh": 1300, "Palestine": 1450,
    "Lebanon": 1500,
}

# Alias: nombre "limpio" del rival -> clave en ELO_RANKING (cuando difieren).
ELO_ALIAS = {
    "Iran": "IR Iran", "South Korea": "Korea Republic", "USA": "United States",
    "Ivory Coast": "Côte d'Ivoire", "Turkey": "Türkiye", "Czech Republic": "Czechia",
    "DR Congo": "Congo DR", "Bosnia": "Bosnia & Herz.", "Cape Verde": "Cabo Verde",
}


def _limpiar_nombre_rival(opponent: str) -> str:
    """FBref antepone un codigo de pais ('sa Saudi Arabia'). Lo quitamos."""
    if not isinstance(opponent, str):
        return ""
    partes = opponent.strip().split(" ", 1)
    # Si el primer token es un codigo corto en minusculas, lo descartamos.
    if len(partes) == 2 and partes[0].islower() and len(partes[0]) <= 3:
        return partes[1].strip()
    return opponent.strip()


def elo_de(opponent: str, default: float = ELO_REFERENCIA) -> float:
    """Devuelve el Elo de un rival a partir del nombre que da FBref."""
    nombre = _limpiar_nombre_rival(opponent)
    if nombre in ELO_RANKING:
        return ELO_RANKING[nombre]
    if nombre in ELO_ALIAS:
        return ELO_RANKING[ELO_ALIAS[nombre]]
    return default


LIGAS = {
    "Mundial 2026": "INT-World Cup",
    "Premier League (Inglaterra)": "ENG-Premier League",
    "La Liga (España)": "ESP-La Liga",
    "Liga MX (México)": "MEX-Liga MX",
    "Bundesliga (Alemania)": "GER-Bundesliga",
    "Serie A (Italia)": "ITA-Serie A",
    "Ligue 1 (Francia)": "FRA-Ligue 1",
}

TEMPORADAS = {
    "Mundial 2026": "2026",
    "Premier League (Inglaterra)": "2025-2026",
    "La Liga (España)": "2025-2026",
    "Liga MX (México)": "2025-2026",
    "Bundesliga (Alemania)": "2025-2026",
    "Serie A (Italia)": "2025-2026",
    "Ligue 1 (Francia)": "2025-2026",
}

# 48 equipos clasificados al Mundial 2026.
# Los nombres apuntan a la forma inglesa/FBref mas probable. Si soccerdata
# devuelve "No data found" para alguno, ajusta aqui el nombre exacto de FBref.
EQUIPOS_MUNDIAL = [
    "Algeria",
    "Argentina",
    "Australia",
    "Austria",
    "Belgium",
    "Bosnia & Herz.",
    "Brazil",
    "Canada",
    "Cabo Verde",
    "Colombia",
    "Croatia",
    "Curaçao",
    "Czechia",
    "Congo DR",
    "Ecuador",
    "Egypt",
    "England",
    "France",
    "Germany",
    "Ghana",
    "Haiti",
    "IR Iran",
    "Iraq",
    "Côte d'Ivoire",
    "Japan",
    "Jordan",
    "Korea Republic",
    "Mexico",
    "Morocco",
    "Netherlands",
    "New Zealand",
    "Norway",
    "Panama",
    "Paraguay",
    "Portugal",
    "Qatar",
    "Saudi Arabia",
    "Scotland",
    "Senegal",
    "South Africa",
    "Spain",
    "Sweden",
    "Switzerland",
    "Tunisia",
    "Türkiye",
    "United States",
    "Uruguay",
    "Uzbekistan",
]

EQUIPOS_MUNDIAL.sort()
assert len(EQUIPOS_MUNDIAL) == 48, f"Deberian ser 48 equipos, hay {len(EQUIPOS_MUNDIAL)}"

# ── Cuadro del Mundial 2026: 12 grupos de 4 ─────────────────────────────────
# IMPORTANTE: esta es una distribucion provisional, sembrada por Elo en bombos
# (no es el sorteo oficial). EDITALA para reflejar los grupos reales: solo mueve
# los nombres entre las listas. La simulacion (montecarlo_mundial.py) la lee tal
# cual. Los nombres deben coincidir con los de FBref (los de EQUIPOS_MUNDIAL).
GRUPOS_MUNDIAL = {
    "A": ["Argentina", "Morocco", "Egypt", "Ghana"],
    "B": ["France", "Senegal", "Scotland", "Qatar"],
    "C": ["Spain", "Switzerland", "IR Iran", "Uzbekistan"],
    "D": ["England", "Japan", "Côte d'Ivoire", "Congo DR"],
    "E": ["Brazil", "Ecuador", "Canada", "Saudi Arabia"],
    "F": ["Portugal", "Mexico", "Algeria", "Iraq"],
    "G": ["Netherlands", "Norway", "Czechia", "Panama"],
    "H": ["Germany", "Türkiye", "Paraguay", "Jordan"],
    "I": ["Belgium", "United States", "Tunisia", "Cabo Verde"],
    "J": ["Colombia", "Korea Republic", "Australia", "New Zealand"],
    "K": ["Uruguay", "Austria", "South Africa", "Curaçao"],
    "L": ["Croatia", "Sweden", "Bosnia & Herz.", "Haiti"],
}

# Nombres para mostrar en la interfaz (espanol) -> nombre FBref.
NOMBRE_DISPLAY = {
    "Alemania": "Germany",
    "Arabia Saudita": "Saudi Arabia",
    "Argelia": "Algeria",
    "Argentina": "Argentina",
    "Australia": "Australia",
    "Austria": "Austria",
    "Bélgica": "Belgium",
    "Bosnia y Herzegovina": "Bosnia & Herz.",
    "Brasil": "Brazil",
    "Cabo Verde": "Cabo Verde",
    "Canadá": "Canada",
    "Catar": "Qatar",
    "Chequia": "Czechia",
    "Colombia": "Colombia",
    "Corea del Sur": "Korea Republic",
    "Costa de Marfil": "Côte d'Ivoire",
    "Croacia": "Croatia",
    "Curazao": "Curaçao",
    "Ecuador": "Ecuador",
    "Egipto": "Egypt",
    "Escocia": "Scotland",
    "España": "Spain",
    "Estados Unidos": "United States",
    "Francia": "France",
    "Ghana": "Ghana",
    "Haití": "Haiti",
    "Inglaterra": "England",
    "Irak": "Iraq",
    "Irán": "IR Iran",
    "Japón": "Japan",
    "Jordania": "Jordan",
    "Marruecos": "Morocco",
    "México": "Mexico",
    "Noruega": "Norway",
    "Nueva Zelanda": "New Zealand",
    "Países Bajos": "Netherlands",
    "Panamá": "Panama",
    "Paraguay": "Paraguay",
    "Portugal": "Portugal",
    "RD Congo": "Congo DR",
    "Senegal": "Senegal",
    "Sudáfrica": "South Africa",
    "Suecia": "Sweden",
    "Suiza": "Switzerland",
    "Túnez": "Tunisia",
    "Turquía": "Türkiye",
    "Uruguay": "Uruguay",
    "Uzbekistán": "Uzbekistan",
}

EQUIPOS_MUNDIAL_ES = sorted(NOMBRE_DISPLAY.keys())
