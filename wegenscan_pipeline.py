"""
Wegenscan enrichment + KPI pipeline als herbruikbare functie.

Ontworpen voor integratie in speeltuin server.py.

Aanname: spectrumId (Spectrum-netwerk) == wvk_id (NWB) voor Nederlandse netwerken.
De id_field-parameter bepaalt welke property als join-key op de NWB-tabellen
wordt gebruikt; standaard is dat 'spectrumId'.

Volgorde enrichment-stappen:
  1. speed_attributes  – max_speed, max_speed_s85     (bbox-gefilterd)
  2. road_category     – road_category, wegcat         (heel NL)
  3. profile           – profile, bicycle_location     (bbox-gefilterd)
  4. pedestrian        – pedestrian_location/crossing  (heel NL)
  5. parking           – parking_location/width        (heel NL, met fallbacks)
  6. speed_bumps       – speed_bumps                   (bbox-gefilterd)
  7. markings          – longitudinal_markings, separation  (defaults)
  8. bus               – bus_frequency, bus_facility       (defaults)
  9. social_interaction – social_interaction               (default)

Stap 10: KPI-berekening via wegenscan.py (build_invoer + calculate_kpis)
"""

# ---------------------------------------------------------------------------
# Imports uit de wegenscan-package
# ---------------------------------------------------------------------------

from db import execute_sql

from wegenscan import build_invoer, calculate_kpis, calculate_generic_safety

# speed_attributes
from add_speed_attributes import (
    compute_bbox,
    build_sql as _speed_build_sql,
    build_speed_lookup as _speed_build_lookup,
)

# road_category
from add_road_category import (
    SQL_QUERY as _WEGCAT_SQL,
    build_wegcat_lookup as _wegcat_build_lookup,
    derive_road_category as _derive_road_category,
    derive_wegcat as _derive_wegcat,
)

# profile
from add_profile import (
    build_sql as _profile_build_sql,
    build_lookup as _profile_build_lookup,
)

# pedestrian
from add_pedestrian import (
    SQL_QUERY as _PEDESTRIAN_SQL,
    build_lookup as _pedestrian_build_lookup,
)

# parking
from add_parking import (
    SQL_QUERY as _PARKING_SQL,
    build_lookup as _parking_build_lookup,
    derive_parking_from_road_category as _derive_parking_road_cat,
    derive_parking_from_bicycle_location as _derive_parking_bicycle,
    derive_parking_from_speed as _derive_parking_speed,
)

# speed_bumps
from add_speed_bumps import (
    build_sql as _bumps_build_sql,
    build_bumps_lookup as _bumps_build_lookup,
)


# ---------------------------------------------------------------------------
# KPI-namen voor logging / UI
# ---------------------------------------------------------------------------

KPI_LABELS = {
    "r_functional_usage": "Functioneel gebruik",
    "r_longitudinal_marking": "Kantmarkering",
    "r_directional_separation": "Rijrichtingscheiding",
    "r_lane_width": "Rijstrookbreedte",
    "r_road_surface": "Wegdek",
    "r_pedestrian_facility": "Voetgangersfaciliteit",
    "r_bicycle_facility": "Fietsfaciliteit",
    "r_parking_facility": "Parkeerfaciliteit",
    "r_bus_stop_facility": "Bushaltefaciliteit",
    "r_speed_bumps": "Drempels",
    "r_roadside_damage": "Bermschade",
    "r_road_width": "Rijbaanbreedte",
    "r_pedestrian_width": "Breedte voetpad",
    "r_bicycle_width": "Breedte fietspad",
    "r_parking_location": "Parkeerlocatie",
    "r_bus_location": "Buslocatie",
    "r_pedestrian_crossing": "Voetgangersoversteek",
    "r_bicycle_crossing": "Fietsoversteek",
    "r_bike_speed": "Fietssnelheid",
    "r_bike_usage": "Fietsgebruik",
    "r_bike_parking": "Fietsparkeren",
    "r_social_interaction": "Sociale interactie",
}


# ---------------------------------------------------------------------------
# Hulpfunctie: bbox uit GeoJSON
# ---------------------------------------------------------------------------


def _get_bbox(geojson: dict):
    """Bepaal bounding box voor de GeoJSON (uit properties of geometrieën)."""
    return compute_bbox(geojson)


# ---------------------------------------------------------------------------
# Enrichment-stappen
# ---------------------------------------------------------------------------


def _enrich_speed(features: list, geojson: dict, id_field: str) -> int:
    """Voeg max_speed en max_speed_s85 toe via Databricks (bbox-gefilterd)."""
    bbox = _get_bbox(geojson)
    sql = _speed_build_sql(bbox)
    columns, rows = execute_sql(sql)
    if columns is None or rows is None:
        print(
            "  [wegenscan] WAARSCHUWING: snelheid-query mislukt, defaults worden gebruikt"
        )
        for f in features:
            f["properties"].setdefault("max_speed", -1)
            f["properties"].setdefault("max_speed_s85", -1)
        return 0
    lookup = _speed_build_lookup(columns, rows)
    matched = 0
    for f in features:
        wvk_id = str(f["properties"].get(id_field, ""))
        if wvk_id in lookup:
            max_speed, max_speed_s85 = lookup[wvk_id]
            f["properties"]["max_speed"] = max_speed
            f["properties"]["max_speed_s85"] = max_speed_s85
            matched += 1
        else:
            f["properties"].setdefault("max_speed", -1)
            f["properties"].setdefault("max_speed_s85", -1)
    print(f"  [wegenscan] snelheid: {matched}/{len(features)} features gematcht")
    return matched


def _enrich_road_category(features: list, id_field: str) -> int:
    """Voeg road_category en wegcat toe via Databricks."""
    columns, rows = execute_sql(_WEGCAT_SQL)
    if columns is None or rows is None:
        print(
            "  [wegenscan] WAARSCHUWING: wegcat-query mislukt, defaults worden gebruikt"
        )
        for f in features:
            f["properties"].setdefault("road_category", "ETW 30 km/h")
            f["properties"].setdefault("wegcat", "straat")
        return 0
    lookup = _wegcat_build_lookup(columns, rows)
    matched = 0
    for f in features:
        props = f["properties"]
        wvk_id = str(props.get(id_field, ""))
        max_speed = props.get("max_speed", -1)
        if isinstance(max_speed, str):
            try:
                max_speed = int(max_speed)
            except (TypeError, ValueError):
                max_speed = -1
        wegcat_number = lookup.get(wvk_id, 99)
        props["wegcat_number"] = wegcat_number
        props["wegcat"] = _derive_wegcat(wegcat_number)
        props["road_category"] = _derive_road_category(wegcat_number, max_speed)
        if wvk_id in lookup:
            matched += 1
    print(f"  [wegenscan] wegcategorie: {matched}/{len(features)} features gematcht")
    return matched


def _enrich_profile(features: list, geojson: dict, id_field: str) -> int:
    """Voeg profile en bicycle_location toe via Databricks (bbox-gefilterd)."""
    bbox = _get_bbox(geojson)
    sql = _profile_build_sql(bbox)
    columns, rows = execute_sql(sql)
    if columns is None or rows is None:
        print(
            "  [wegenscan] WAARSCHUWING: profiel-query mislukt, defaults worden gebruikt"
        )
        for f in features:
            f["properties"].setdefault(
                "profile", "gemengd (auto 2, fiets 2 richtingen)"
            )
            f["properties"].setdefault("bicycle_location", "niet van toepassing")
            f["properties"].setdefault(
                "bicycle_crossing", "uit de voorrang / geen voorziening"
            )
            f["properties"].setdefault("bicycle_width", 0)
        return 0
    lookup = _profile_build_lookup(columns, rows)
    matched = 0
    for f in features:
        props = f["properties"]
        wvk_id = str(props.get(id_field, ""))
        if wvk_id in lookup:
            props.update(lookup[wvk_id])
            matched += 1
        else:
            props.setdefault("profile", "gemengd (auto 2, fiets 2 richtingen)")
            props.setdefault("bicycle_location", "niet van toepassing")
            props.setdefault("bicycle_crossing", "uit de voorrang / geen voorziening")
            props.setdefault("bicycle_width", 0)
    print(f"  [wegenscan] profiel: {matched}/{len(features)} features gematcht")
    return matched


def _enrich_pedestrian(features: list, id_field: str) -> int:
    """Voeg pedestrian_location en pedestrian_crossing toe via Databricks."""
    columns, rows = execute_sql(_PEDESTRIAN_SQL)
    if columns is None or rows is None:
        print(
            "  [wegenscan] WAARSCHUWING: voetganger-query mislukt, defaults worden gebruikt"
        )
        for f in features:
            f["properties"].setdefault("pedestrian_location", "op voetpad/trottoir")
            f["properties"].setdefault(
                "pedestrian_crossing", "uit de voorrang / geen voorziening"
            )
            f["properties"].setdefault("pedestrian_width", 0)
        return 0
    lookup = _pedestrian_build_lookup(columns, rows)
    matched = 0
    for f in features:
        props = f["properties"]
        wvk_id = str(props.get(id_field, ""))
        props["pedestrian_width"] = 0
        if wvk_id in lookup:
            props.update(lookup[wvk_id])
            matched += 1
        else:
            props.setdefault("pedestrian_location", "op voetpad/trottoir")
            props.setdefault(
                "pedestrian_crossing", "uit de voorrang / geen voorziening"
            )
    print(f"  [wegenscan] voetgangers: {matched}/{len(features)} features gematcht")
    return matched


def _enrich_parking(features: list, id_field: str) -> int:
    """Voeg parking_location en parking_width toe via Databricks (met fallbacks)."""
    columns, rows = execute_sql(_PARKING_SQL)
    if columns is None or rows is None:
        print(
            "  [wegenscan] WAARSCHUWING: parkeer-query mislukt, defaults worden gebruikt"
        )
        for f in features:
            f["properties"].setdefault("parking_location", "op de rijbaan")
            f["properties"].setdefault("parking_width", 0)
        return 0
    lookup = _parking_build_lookup(columns, rows)
    matched = 0
    for f in features:
        props = f["properties"]
        wvk_id = str(props.get(id_field, ""))
        if wvk_id in lookup:
            props.update(lookup[wvk_id])
            matched += 1
        else:
            derived = _derive_parking_road_cat(props.get("road_category"))
            if derived is None:
                derived = _derive_parking_bicycle(props.get("bicycle_location"))
            if derived is None:
                derived = _derive_parking_speed(props.get("max_speed", -1))
            if derived:
                props.update(derived)
    print(f"  [wegenscan] parkeren: {matched}/{len(features)} features gematcht")
    return matched


def _enrich_speed_bumps(features: list, geojson: dict, id_field: str) -> int:
    """Voeg speed_bumps toe via Databricks (bbox-gefilterd)."""
    bbox = _get_bbox(geojson)
    sql = _bumps_build_sql(bbox)
    columns, rows = execute_sql(sql)
    if columns is None or rows is None:
        print(
            "  [wegenscan] WAARSCHUWING: drempel-query mislukt, defaults worden gebruikt"
        )
        for f in features:
            f["properties"].setdefault("speed_bumps", "niet aanwezig")
        return 0
    lookup = _bumps_build_lookup(columns, rows)
    matched = 0
    for f in features:
        wvk_id = str(f["properties"].get(id_field, ""))
        if wvk_id in lookup:
            f["properties"]["speed_bumps"] = lookup[wvk_id]
            matched += 1
        else:
            f["properties"].setdefault("speed_bumps", "niet aanwezig")
    print(f"  [wegenscan] drempels: {matched}/{len(features)} features gematcht")
    return matched


def _enrich_defaults(features: list) -> None:
    """Zet overige attributen op defaults (markings, bus, social_interaction)."""
    for f in features:
        props = f["properties"]
        props.setdefault("longitudinal_markings", "niet aanwezig")
        props.setdefault("separation", "niet aanwezig")
        props.setdefault("bus_frequency", "niet aanwezig")
        props.setdefault("bus_facility", "niet van toepassing")
        props.setdefault("social_interaction", "ja")


# ---------------------------------------------------------------------------
# Publieke API
# ---------------------------------------------------------------------------


def enrich_features(
    features: list, geojson: dict, id_field: str = "spectrumId"
) -> list:
    """
    Verrijkt een lijst GeoJSON-features met NWB-attributen via Databricks.

    Parameters
    ----------
    features : list
        De feature-lijst uit de GeoJSON FeatureCollection.
    geojson : dict
        De volledige FeatureCollection (nodig voor bbox-berekening).
    id_field : str
        De property-naam die als join-key op NWB wvk_id wordt gebruikt.
        Standaard 'spectrumId'.

    Returns
    -------
    list
        Dezelfde feature-lijst, in-place bijgewerkt.
    """
    print(
        f"[wegenscan] Enrichment gestart ({len(features)} features, id_field={id_field!r})"
    )

    print("[wegenscan] Stap 1/6: snelheidsattributen …")
    _enrich_speed(features, geojson, id_field)

    print("[wegenscan] Stap 2/6: wegcategorie …")
    _enrich_road_category(features, id_field)

    print("[wegenscan] Stap 3/6: rijbaanprofiel …")
    _enrich_profile(features, geojson, id_field)

    print("[wegenscan] Stap 4/6: voetgangers …")
    _enrich_pedestrian(features, id_field)

    print("[wegenscan] Stap 5/6: parkeren …")
    _enrich_parking(features, id_field)

    print("[wegenscan] Stap 6/6: drempels …")
    _enrich_speed_bumps(features, geojson, id_field)

    print("[wegenscan] Defaults toepassen (markering, bus, sociale interactie) …")
    _enrich_defaults(features)

    print("[wegenscan] Enrichment klaar.")
    return features


def run_kpis(features: list) -> list:
    """
    Berekent 21 veiligheids-KPI's per feature.

    Voegt toe aan elke feature.properties:
      - ``safety``         dict met 21 KPI-waarden (GOED/REDELIJK/MATIG/SLECHT/NVT)
      - ``generic_safety`` geaggregeerde score

    Returns
    -------
    list
        Dezelfde feature-lijst, in-place bijgewerkt.
    """
    errors = 0
    for feature in features:
        props = feature["properties"]
        invoer = build_invoer(props)
        try:
            safety = calculate_kpis(invoer)
            props["safety"] = safety
            props["generic_safety"] = calculate_generic_safety(safety)
        except Exception as exc:
            errors += 1
            link_id = props.get("linkId") or props.get("spectrumId") or "?"
            print(f"  [wegenscan] WAARSCHUWING: KPI-fout voor linkId={link_id}: {exc}")
            props["safety"] = {}
            props["generic_safety"] = "NVT"

    ok = len(features) - errors
    print(f"[wegenscan] KPI-berekening: {ok}/{len(features)} features succesvol")
    return features


def run_pipeline(geojson: dict, id_field: str = "spectrumId") -> dict:
    """
    Volledige wegenscan-pipeline op een GeoJSON FeatureCollection.

    Stappen: enrichment (Databricks) → KPI-berekening

    Parameters
    ----------
    geojson : dict
        GeoJSON FeatureCollection (bijv. geladen uit een NETWORK-bestand).
    id_field : str
        Property-naam die als NWB wvk_id join-key geldt. Standaard 'spectrumId'.

    Returns
    -------
    dict
        Nieuwe GeoJSON FeatureCollection met toegevoegde veiligheids-properties.
    """
    features = [f for f in geojson.get("features", [])]

    enrich_features(features, geojson, id_field)
    run_kpis(features)

    return {**geojson, "features": features}
