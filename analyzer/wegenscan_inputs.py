"""
Wegenscan-invoer afleiden uit NETWORK-attributen die de speeltuin al heeft.

De wegenscan-package haalt zijn invoer standaard zelf op uit Databricks (NWB/WKD).
Het NETWORK-bestand bevat via de prepare-pipeline (WKD-breedtes + OSM
road-enricher, gmt_network_enrichment ≥ 0.6) echter al de meeste gegevens.
Deze module vertaalt die kolommen naar de property-namen en waardedomeinen die
``wegenscan.build_invoer`` / ``calculate_kpis`` verwachten.

Elke afleiding geeft ``(waarde, bron)`` terug. Bron is ``"netwerk:<kolommen>"``
of ``None`` als er geen bruikbare netwerkwaarde is; dan blijft de property
leeg en vult build_invoer zijn eigen default in.

Alleen waarden die in de lookup-tabellen van wegenscan/core voorkomen worden
gebruikt; een onbekende string levert daar stil ONBEKEND of een KeyError op.
"""

from __future__ import annotations

import math

from add_parking import (
    derive_parking_from_bicycle_location,
    derive_parking_from_road_category,
    derive_parking_from_speed,
)
from add_road_category import derive_road_category
from wegenscan import build_invoer

# Categorieën waarvoor de KPI-tabellen (core/functie_vorm.py) waarden hebben.
KNOWN_CATEGORIES = (
    "ETW 15 km/h",
    "ETW 30 km/h",
    "GOW 30 km/h",
    "GOW 50 km/h",
    "ETW-I 60 km/h",
    "ETW-II 60 km/h",
    "GOW 80 km/h",
)

# Uitkomsten van derive_road_category die niet in de tabellen staan.
_CATEGORY_ALIASES = {
    "ETW 15 km/h (erf)": "ETW 15 km/h",
    "geen categorie,50 km/uur": "GOW 50 km/h",
}

# osmHighway → NWB-wegcategorienummer (1 autosnelweg … 7 erf), als invoer voor
# derive_road_category. Ontbrekende types → geen categorie.
_HIGHWAY_WEGCAT = {
    "motorway": 1, "motorway_link": 1,
    "trunk": 2, "trunk_link": 2,
    "primary": 3, "primary_link": 3,
    "secondary": 3, "secondary_link": 3,
    "tertiary": 4, "tertiary_link": 4,
    "unclassified": 5,
    "residential": 6, "service": 6, "track": 6, "road": 6,
    "living_street": 7, "pedestrian": 7,
}

# Ruwe OSM-surface → verhardingsklasse. Gelijk houden met _SURFACE_CLASS in
# common/js/montreal-basemap.js (Inrichting → Wegprofiel → Verharding).
_SURFACE_CLASS = {}
for _cls, _values in {
    "asfalt": ["asphalt", "paved", "chipseal"],
    "klinkers": ["paving_stones", "sett", "bricks", "cobblestone", "unhewn_cobblestone"],
    "beton": ["concrete", "concrete:plates", "concrete:lanes"],
    "halfverhard": ["compacted", "fine_gravel", "gravel", "pebblestone"],
    "onverhard": ["unpaved", "ground", "dirt", "earth", "grass", "sand", "mud"],
}.items():
    for _v in _values:
        _SURFACE_CLASS[_v] = _cls

# Verhardingsklasse → wegenscan r_surface (core/functie_vorm.py road_surfaces).
_SURFACE_KPI = {
    "asfalt": "gesloten (o.a. asfalt)",
    "beton": "gesloten (o.a. asfalt)",
    "klinkers": "open (o.a.klinkers)",
    "halfverhard": "gedeeltelijk open",
    "onverhard": "gedeeltelijk open",
}


# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------


def _num(value) -> float | None:
    """Eindig getal of None (pandas levert NaN voor ontbrekende waarden)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _str(value) -> str | None:
    if isinstance(value, str):
        s = value.strip().lower()
        return s or None
    return None


def _bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    return None


def _sides(props: dict, prefix: str) -> list[str]:
    """Bekende waarden van <prefix>Left / <prefix>Right."""
    return [v for v in (_str(props.get(prefix + "Left")), _str(props.get(prefix + "Right"))) if v]


# ---------------------------------------------------------------------------
# Afleidingen per wegenscan-veld
# ---------------------------------------------------------------------------


def surface_class(props: dict) -> str:
    """Verhardingsklasse (asfalt/klinkers/beton/halfverhard/onverhard/onbekend)."""
    return _SURFACE_CLASS.get(_str(props.get("surface")) or "", "onbekend")


def derive_surface(props: dict):
    """r_surface-waarde voor de KPI's, via dezelfde klassen als de kaartlaag."""
    kpi = _SURFACE_KPI.get(surface_class(props))
    return (kpi, "netwerk:surface") if kpi else (None, None)


def derive_width(props: dict):
    """Totale wegbreedte (m); zelfde regel als _designWidthM in analyzer/index.html."""
    lo, hi = _num(props.get("roadWidthMinM")), _num(props.get("roadWidthMaxM"))
    if lo is not None and hi is not None:
        return (lo + hi) / 2, "netwerk:roadWidthMinM/MaxM"
    w = _num(props.get("roadWidthM"))
    if w is not None:
        return w * 2, "netwerk:roadWidthM"
    w = _num(props.get("osmWidth"))
    if w is not None and w > 0:
        return w, "netwerk:osmWidth"
    return None, None


def derive_speed(props: dict):
    """Maximumsnelheid (km/h): speedLimit, anders osmMaxspeed."""
    for col in ("speedLimit", "osmMaxspeed"):
        v = _num(props.get(col))
        if v is not None and v > 0:
            return int(round(v)), f"netwerk:{col}"
    return None, None


def derive_road_category_from_network(props: dict, speed: int | None):
    """Wegenscan-categorie uit osmHighway + snelheid, via derive_road_category."""
    highway = _str(props.get("osmHighway"))
    if speed is None:
        return None, None
    if highway is None:
        # Netwerk zonder road-enricher: alleen de snelheid. derive_road_category
        # met een onbekende wegcat (99) valt terug op 30/50/60 km/h.
        category = normalize_category(derive_road_category(99, speed))
        return (category, "netwerk:speedLimit (zonder wegtype)") if category else (None, None)
    wegcat = _HIGHWAY_WEGCAT.get(highway)
    if wegcat is None:
        return None, None
    if speed <= 15 and wegcat >= 5:
        category = "ETW 15 km/h"
    else:
        category = normalize_category(derive_road_category(wegcat, speed))
    if category is None:
        return None, None
    return category, "netwerk:osmHighway+snelheid"


def normalize_category(category: str | None) -> str | None:
    """Uitkomst van derive_road_category → categorie uit de KPI-tabellen, of None."""
    category = _CATEGORY_ALIASES.get(category, category)
    return category if category in KNOWN_CATEGORIES else None


def derive_bicycle_location(props: dict):
    """bicycle_location uit cyclewayLeft/Right (lane/track/shared_lane/no)."""
    sides = _sides(props, "cycleway")
    if not sides:
        return None, None
    src = "netwerk:cyclewayLeft/Right"
    if "track" in sides:
        return "vrijliggend fietspad (eenrichting)", src
    if "lane" in sides:
        return "fietsstroken", src
    # shared_lane / share_busway / no: fietsers rijden op de rijbaan.
    return "gemengd op rijbaan", src


def derive_profile(props: dict, bicycle_location: str | None):
    """Rijbaanprofiel uit osmOneway en de fietsvoorziening."""
    oneway = _bool(props.get("osmOneway"))
    if oneway is None:
        return None, None
    src = "netwerk:osmOneway" + ("+cycleway" if bicycle_location else "")
    if bicycle_location in ("vrijliggend fietspad (eenrichting)", "niet van toepassing"):
        if oneway:
            return "rijbaan auto 1 richting (geen fietsers)", src
        return "rijbaan auto 2 richtingen (geen fietsers)", src
    if bicycle_location == "fietsstroken":
        if oneway:
            return "fietsstroken (auto 1, fiets 1 richting)", src
        return "fietsstroken (auto 2, fiets 2 richtingen)", src
    if oneway:
        return "gemengd (auto 1, fiets 1 richting)", src
    return "gemengd (auto 2, fiets 2 richtingen)", src


def derive_pedestrian_location(props: dict, speed: int | None):
    """pedestrian_location uit sidewalkLeft/Right (yes/no/separate)."""
    sides = _sides(props, "sidewalk")
    if not sides:
        return None, None
    src = "netwerk:sidewalkLeft/Right"
    if "yes" in sides or "separate" in sides:
        return "op voetpad/trottoir", src
    # Geen stoep: buiten de kom geen voetgangers, binnen de kom op de rijbaan.
    if speed is not None and speed >= 60:
        return "niet van toepassing", src
    return "gemengd op rijbaan", src


def derive_pedestrian_crossing(props: dict, pedestrian_location: str | None):
    """pedestrian_crossing uit numPedestrianCrossings / numRefugeAreas."""
    if pedestrian_location == "niet van toepassing":
        return "niet van toepassing", "netwerk:sidewalkLeft/Right"
    if (_num(props.get("numPedestrianCrossings")) or 0) > 0:
        return "in de voorrang / zebrapad", "netwerk:numPedestrianCrossings"
    if (_num(props.get("numRefugeAreas")) or 0) > 0:
        return "uit de voorrang met middengeleider", "netwerk:numRefugeAreas"
    return None, None


def derive_parking_location(props: dict):
    """parking_location uit BGT/OSM-parkeervlakken (TRAFFIC-ASSETS), anders
    uit parkingLeft/Right (OSM parking:<side>-schema)."""
    asset = props.get("assetParkingLocation")
    if asset:
        return asset, "assets:parkingArea"
    sides = _sides(props, "parking")
    if not sides:
        return None, None
    src = "netwerk:parkingLeft/Right"
    if any(s in ("street_side", "on_kerb", "half_on_kerb") for s in sides):
        return "langsparkeren", src
    if "lane" in sides:
        return "op de rijbaan", src
    # no / separate / overig: geen parkeren langs de rijbaan.
    return "niet van toepassing", src


def derive_speed_bumps(props: dict):
    """speed_bumps: alleen 'aanwezig' is uit het netwerk af te leiden.

    numSpeedBumps = 0 betekent in de huidige data vaak 'niet bekend', dus dan
    blijft het een default.
    """
    asset = props.get("assetSpeedBumps")
    if asset:
        return asset, "assets:speedBump"
    if (_num(props.get("numSpeedBumps")) or 0) > 0:
        return "op wegvakken", "netwerk:numSpeedBumps"
    if props.get("assetsCovered"):
        # BGT registreert drempels volledig: binnen het assets-gebied is
        # 'geen drempel gevonden' een waarneming, geen aanname.
        return "niet aanwezig", "assets:speedBump (geen)"
    return None, None


# ---------------------------------------------------------------------------
# Publieke API
# ---------------------------------------------------------------------------

# Velden die in wegenscan_sources gerapporteerd worden (ook als ze default zijn).
SOURCE_FIELDS = (
    "flow",
    "road_category",
    "max_speed",
    "max_speed_s85",
    "width",
    "surface",
    "profile",
    "bicycle_location",
    "pedestrian_location",
    "pedestrian_crossing",
    "parking_location",
    "speed_bumps",
)


def derive_inputs(props: dict) -> tuple[dict, dict]:
    """Leid alle wegenscan-velden af uit één set NETWORK-properties.

    Returns ``(waarden, bronnen)``; ``waarden`` bevat alleen velden met een
    netwerkwaarde, ``bronnen`` bevat elk veld uit SOURCE_FIELDS (``"default"``
    als er geen netwerkwaarde was).
    """
    values: dict = {}
    sources: dict = {}

    def put(field, result):
        value, src = result
        if value is not None:
            values[field] = value
            sources[field] = src

    flow = props.get("flow")
    if isinstance(flow, dict) or (_num(flow) or 0) > 0:
        # build_invoer leest flow zelf; hier alleen de bron vastleggen.
        sources["flow"] = "netwerk:flow"

    speed, speed_src = derive_speed(props)
    if speed is not None:
        # Geen s85-bron in het netwerk; de limiet is de beste benadering.
        values["max_speed"] = speed
        values["max_speed_s85"] = speed
        sources["max_speed"] = speed_src
        sources["max_speed_s85"] = speed_src + " (limiet)"

    put("road_category", derive_road_category_from_network(props, speed))
    put("width", derive_width(props))
    put("wegenscan_surface", derive_surface(props))
    if "wegenscan_surface" in sources:
        sources["surface"] = sources.pop("wegenscan_surface")

    put("bicycle_location", derive_bicycle_location(props))
    put("profile", derive_profile(props, values.get("bicycle_location")))
    put("pedestrian_location", derive_pedestrian_location(props, speed))
    put("pedestrian_crossing", derive_pedestrian_crossing(props, values.get("pedestrian_location")))
    put("parking_location", derive_parking_location(props))
    if sources.get("parking_location") == "assets:parkingArea":
        values["parking_width"] = props.get("assetParkingWidth", 0)
    put("speed_bumps", derive_speed_bumps(props))

    if "parking_location" not in values:
        # Vuistregels van de wegenscan zelf (add_parking), zoals de oorspronkelijke
        # pipeline ze gebruikte als er geen parkeerdata was. Blijft een aanname,
        # maar voorkomt dat overal 'op de rijbaan' (−2 m rijbaanbreedte) geldt.
        derived = (
            derive_parking_from_road_category(values.get("road_category"))
            or derive_parking_from_bicycle_location(values.get("bicycle_location"))
            or derive_parking_from_speed(speed if speed is not None else -1)
        )
        values["parking_location"] = derived["parking_location"]
        values["parking_width"] = derived["parking_width"]
        sources["parking_location"] = "aanname:vuistregel"

    for field in SOURCE_FIELDS:
        sources.setdefault(field, "default")
    return values, sources


def enrich_from_network(features: list) -> dict:
    """Zet de afgeleide velden op elke feature (in-place).

    Bestaande properties worden overschreven door de wegenscan-velden; per
    feature komt ``wegenscan_sources`` erbij. Geeft de dekking terug (zie
    ``coverage``).
    """
    for f in features:
        props = f["properties"]
        values, sources = derive_inputs(props)
        props.update(values)
        props["wegenscan_sources"] = sources
    return coverage(features)


def is_assumed(src: str | None) -> bool:
    """Bron is een aanname (default of vuistregel), geen data."""
    return not src or src == "default" or src.startswith("aanname")


def coverage(features: list) -> dict:
    """Per veld het percentage features met een bron uit data (geen aanname)."""
    hits = dict.fromkeys(SOURCE_FIELDS, 0)
    for f in features:
        for field, src in f["properties"].get("wegenscan_sources", {}).items():
            if field in hits and not is_assumed(src):
                hits[field] += 1
    n = len(features) or 1
    return {field: round(100 * count / n) for field, count in hits.items()}


def build_invoer_from_network(props: dict) -> dict:
    """build_invoer, maar met de verhardingsklasse uit deze module.

    ``wegenscan.translate_surface`` matcht op substrings ('paved' zit ook in
    'unpaved') en wijkt af van de kaartlaag; daarom overschrijven we r_surface
    als er een netwerkwaarde is. Een ontbrekende surface komt uit parquet als
    NaN binnen, waarop translate_surface crasht; die maken we eerst None.
    """
    if not isinstance(props.get("surface"), str):
        props = {**props, "surface": None}
    invoer = build_invoer(props)
    if props.get("wegenscan_surface"):
        invoer["r_surface"] = props["wegenscan_surface"]
    return invoer
