"""
Wegenscan enrichment + KPI pipeline als herbruikbare functie.

Ontworpen voor integratie in speeltuin server.py.

Bron van de invoer
------------------
1. NETWORK-attributen (standaard): de prepare-pipeline heeft via WKD-breedtes
   en de OSM road-enricher al breedte, wegdek, snelheid, wegtype, fiets-,
   stoep- en parkeervoorzieningen per link. ``wegenscan_inputs`` vertaalt die
   naar de wegenscan-velden en legt per veld de bron vast
   (``props["wegenscan_sources"]``).
2. Databricks (optioneel, ``use_databricks=True``): de NWB/WKD-tabellen van de
   wegenscan-package vullen alleen velden aan waarvoor het netwerk geen waarde
   had. Uitzondering is ``max_speed_s85``, die het netwerk niet kent. Join op
   ``wvkIds`` (spatiale WKD-match uit prepare), met ``id_field`` als terugval;
   bij meerdere wegvakken per link telt de meest voorkomende waarde.
3. Wat dan nog ontbreekt, vult ``build_invoer`` met de wegenscan-defaults.
   Markeringen, rijrichtingscheiding, bus en sociale interactie hebben geen
   bron en blijven altijd default.

Daarna: KPI-berekening via wegenscan.py (build_invoer + calculate_kpis).
"""

import json
from collections import Counter

from wegenscan import calculate_kpis, calculate_generic_safety

import wegenscan_assets as _wa
import wegenscan_inputs as _wi

from core.vorm_gebruik import VormGebruik as _VormGebruik


# Bugfix wegenscan 2.1.0: bij een breedte boven de laatste tabelrij (20 m)
# verwijst get_bermschade_waarden naar een niet-bestaande variabele `waarden`
# (NameError → hele link NVT). Bedoeld is de laatste rij van de tabel.
# Kwam pas aan het licht nu de echte breedte gebruikt wordt (voorheen 6 m).
def _get_bermschade_waarden(self, width):
    rows = sorted(self.bermschade_waarden, key=lambda x: x["breedte"])
    for item in rows:
        if item["breedte"] >= width:
            return item["values"]
    return rows[-1]["values"]


_VormGebruik.get_bermschade_waarden = _get_bermschade_waarden


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

# Wegtypes waarvoor de wegenscan geen beoordeling heeft (autosnelweg/autoweg).
_OUT_OF_SCOPE_HIGHWAYS = {"motorway", "motorway_link", "trunk", "trunk_link"}


# ---------------------------------------------------------------------------
# Databricks-aanvulling (optioneel)
# ---------------------------------------------------------------------------


def _wvk_keys(props: dict, id_field: str) -> list[str]:
    """NWB-wegvak-id's van een link: wvkIds (lijst of JSON-string), anders id_field."""
    raw = props.get("wvkIds")
    ids = None
    if isinstance(raw, str):
        try:
            ids = json.loads(raw)
        except ValueError:
            ids = None
    elif raw is not None and not isinstance(raw, (int, float)):
        try:
            ids = list(raw)
        except TypeError:
            ids = None
    if ids:
        return [str(i) for i in ids]
    own = props.get(id_field)
    return [str(own)] if own not in (None, "") else []


def _majority(lookup: dict, keys: list[str]):
    """Meest voorkomende waarde van lookup over de keys (None als geen match)."""
    hits = [lookup[k] for k in keys if k in lookup]
    if not hits:
        return None
    counted = Counter(json.dumps(h, sort_keys=True, default=str) for h in hits)
    return json.loads(counted.most_common(1)[0][0])


def _query_lookups(geojson: dict) -> dict:
    """Voer de Databricks-queries uit; per bron een dict wvk_id → waarde.

    Mislukte queries leveren een lege lookup op (geen defaults).
    """
    # Lazy: alleen nodig (en alleen verbinding maken) als Databricks aan staat.
    from db import execute_sql
    from add_speed_attributes import (
        compute_bbox,
        build_sql as speed_sql,
        build_speed_lookup,
    )
    from add_road_category import SQL_QUERY as wegcat_sql, build_wegcat_lookup
    from add_profile import build_sql as profile_sql, build_lookup as profile_lookup
    from add_pedestrian import SQL_QUERY as pedestrian_sql, build_lookup as pedestrian_lookup
    from add_parking import SQL_QUERY as parking_sql, build_lookup as parking_lookup
    from add_speed_bumps import build_sql as bumps_sql, build_bumps_lookup

    bbox = compute_bbox(geojson)
    steps = {
        "speed": (speed_sql(bbox), build_speed_lookup),
        "wegcat": (wegcat_sql, build_wegcat_lookup),
        "profile": (profile_sql(bbox), profile_lookup),
        "pedestrian": (pedestrian_sql, pedestrian_lookup),
        "parking": (parking_sql, parking_lookup),
        "bumps": (bumps_sql(bbox), build_bumps_lookup),
    }
    lookups = {}
    for name, (sql, build) in steps.items():
        print(f"  [wegenscan] Databricks: {name} …")
        columns, rows = execute_sql(sql)
        if columns is None or rows is None:
            print(f"  [wegenscan] WAARSCHUWING: {name}-query mislukt, geen aanvulling")
            lookups[name] = {}
            continue
        lookups[name] = build(columns, rows)
    # wegcat 99 = "niet gevonden" in build_wegcat_lookup.
    lookups["wegcat"] = {k: v for k, v in lookups["wegcat"].items() if v != 99}
    return lookups


def _supplement_from_databricks(features: list, geojson: dict, id_field: str) -> None:
    """Vul velden met bron 'default' aan uit Databricks (in-place)."""
    from add_road_category import derive_road_category

    lookups = _query_lookups(geojson)
    filled = Counter()

    for f in features:
        props = f["properties"]
        sources = props["wegenscan_sources"]
        keys = _wvk_keys(props, id_field)
        if not keys:
            continue

        def fill(field, value, src):
            if value is not None and _wi.is_assumed(sources.get(field)):
                props[field] = value
                sources[field] = src
                filled[field] += 1

        speed = _majority(lookups["speed"], keys)
        if speed and speed[0] > 0:
            max_speed, s85 = speed
            if sources["max_speed"] == "default":
                props["max_speed"] = max_speed
                sources["max_speed"] = "databricks:MAXSHD"
                filled["max_speed"] += 1
            if s85 > 0:
                # s85 heeft geen netwerkbron; altijd overnemen.
                props["max_speed_s85"] = s85
                sources["max_speed_s85"] = "databricks:s85"
                filled["max_speed_s85"] += 1

        wegcat = _majority(lookups["wegcat"], keys)
        if wegcat is not None and props.get("max_speed"):
            category = derive_road_category(wegcat, props["max_speed"])
            category = _wi.normalize_category(category)
            fill("road_category", category, "databricks:wkd_weg_catv2")

        profile = _majority(lookups["profile"], keys) or {}
        fill("profile", profile.get("profile"), "databricks:wkd_vrkrstpnv2")
        fill("bicycle_location", profile.get("bicycle_location"), "databricks:wkd_vrkrstpnv2")

        pedestrian = _majority(lookups["pedestrian"], keys) or {}
        fill("pedestrian_location", pedestrian.get("pedestrian_location"), "databricks:wkd_vrkrstpnv2")

        parking = _majority(lookups["parking"], keys) or {}
        if parking.get("parking_location") and _wi.is_assumed(sources["parking_location"]):
            props["parking_width"] = parking.get("parking_width", 0)
        fill("parking_location", parking.get("parking_location"), "databricks:wkd_parkvlak")

        fill("speed_bumps", _majority(lookups["bumps"], keys), "databricks:drempels")

    n = len(features)
    summary = ", ".join(f"{k} {v}/{n}" for k, v in filled.items()) or "niets"
    print(f"  [wegenscan] Databricks-aanvulling: {summary}")


# ---------------------------------------------------------------------------
# Publieke API
# ---------------------------------------------------------------------------


def enrich_features(
    features: list,
    geojson: dict,
    id_field: str = "spectrumId",
    use_databricks: bool = False,
    assets=None,
) -> dict:
    """
    Verrijkt GeoJSON-features met de wegenscan-invoervelden (in-place).

    Eerst uit de NETWORK-attributen; met ``use_databricks`` daarna aanvulling
    uit de NWB/WKD-tabellen voor velden zonder netwerkwaarde.

    Returns
    -------
    dict
        Dekking per veld: percentage features met een niet-default bron.
    """
    print(f"[wegenscan] Enrichment gestart ({len(features)} features)")
    if features and not any("osmHighway" in f["properties"] for f in features):
        print(
            "  [wegenscan] WAARSCHUWING: netwerk mist de OSM road-enricher-kolommen "
            "(osmHighway, surface, cycleway…); opnieuw prepareren geeft betere invoer. "
            "Nu worden veel defaults gebruikt."
        )
    if assets is not None:
        stats = _wa.link_assets(features, assets)
        print(
            f"  [wegenscan] TRAFFIC-ASSETS: {stats['parking_areas']} actuele parkeervlakken → "
            f"{stats['parking_links']} links; {stats['speed_bumps']} drempels → "
            f"{stats['bump_links']} links"
        )
    _wi.enrich_from_network(features)

    if use_databricks:
        print(f"[wegenscan] Databricks-aanvulling (join op wvkIds / {id_field!r}) …")
        _supplement_from_databricks(features, geojson, id_field)

    coverage = _wi.coverage(features)
    print(
        "[wegenscan] Dekking (niet-default): "
        + ", ".join(f"{k} {v}%" for k, v in coverage.items())
    )
    return coverage


def run_kpis(features: list) -> list:
    """
    Berekent 21 veiligheids-KPI's per feature.

    Voegt toe aan elke feature.properties:
      - ``safety``         dict met 21 KPI-waarden (GOED/REDELIJK/MATIG/SLECHT/NVT)
      - ``generic_safety`` geaggregeerde score

    Autosnelwegen/autowegen vallen buiten de wegenscan en krijgen NVT.
    """
    errors = skipped = 0
    for feature in features:
        props = feature["properties"]
        if props.get("osmHighway") in _OUT_OF_SCOPE_HIGHWAYS:
            skipped += 1
            props["safety"] = {}
            props["generic_safety"] = "NVT"
            continue
        try:
            invoer = _wi.build_invoer_from_network(props)
            # De invoer waarmee gerekend is (incl. defaults), voor het zijpaneel.
            props["wegenscan_invoer"] = invoer
            safety = calculate_kpis(invoer)
            props["safety"] = safety
            props["generic_safety"] = calculate_generic_safety(safety)
        except Exception as exc:
            errors += 1
            link_id = props.get("linkId") or props.get("spectrumId") or "?"
            print(f"  [wegenscan] WAARSCHUWING: KPI-fout voor linkId={link_id}: {exc}")
            props["safety"] = {}
            props["generic_safety"] = "NVT"

    ok = len(features) - errors - skipped
    print(
        f"[wegenscan] KPI-berekening: {ok}/{len(features)} features succesvol"
        + (f", {skipped} buiten scope (autosnelweg/autoweg)" if skipped else "")
    )
    return features


def run_pipeline(
    geojson: dict,
    id_field: str = "spectrumId",
    use_databricks: bool = False,
    assets=None,
) -> dict:
    """
    Volledige wegenscan-pipeline op een GeoJSON FeatureCollection.

    Stappen: enrichment (netwerk, optioneel Databricks) → KPI-berekening

    Parameters
    ----------
    geojson : dict
        GeoJSON FeatureCollection (bijv. geladen uit een NETWORK-bestand).
    id_field : str
        Property die als NWB wvk_id-join geldt als een link geen wvkIds heeft.
    use_databricks : bool
        Velden zonder netwerkwaarde aanvullen uit Databricks (NWB/WKD).
    assets : GeoDataFrame | None
        TRAFFIC-ASSETS van het gebied (parkeervlakken, drempels); optioneel.

    Returns
    -------
    dict
        Nieuwe GeoJSON FeatureCollection met veiligheids-properties en
        ``wegenscan_coverage`` (dekking per invoerveld, in %).
    """
    # Kopie per feature: de invoer kan de (gecachte) netwerkdata van de server zijn.
    features = [
        {**f, "properties": dict(f.get("properties") or {})}
        for f in geojson.get("features", [])
    ]

    coverage = enrich_features(features, geojson, id_field, use_databricks, assets)
    run_kpis(features)

    return {**geojson, "features": features, "wegenscan_coverage": coverage}
