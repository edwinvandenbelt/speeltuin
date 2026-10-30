"""
Wegenscan-invoer uit TRAFFIC-ASSETS: parkeervlakken en drempels per link.

TRAFFIC-ASSETS (prepare stage-5, ``fetch_parking_areas`` / ``fetch_bgt_assets``)
bevat BGT-parkeervlakken (+ OSM-aanvulling) en BGT-verkeersdrempels als
polygonen. Deze module koppelt ze ruimtelijk aan de netwerklinks en zet per link:

* ``assetParkingLocation`` / ``assetParkingWidth`` – langs- of haaksparkeren
  (diepte loodrecht op de weg > 3,5 m → haaks, zelfde regel als
  ``add_parking.derive_parking``);
* ``assetSpeedBumps`` – 'op wegvakken' / 'op kruispunten' /
  'op wegvakken en kruispunten'.

``wegenscan_inputs`` leest die properties en geeft ze de bron ``assets:…``.
"""

from __future__ import annotations

import math

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, shape

# Metrisch CRS voor afstanden (RD New; de wegenscan is NL-only).
_METRIC_CRS = "EPSG:28992"

# Parkeervak hoort bij een link als de dichtstbijzijnde rand binnen
# halve wegbreedte + deze marge van de wegas ligt.
_PARKING_EDGE_MARGIN_M = 2.5
# Diepte loodrecht op de weg: groter is een parkeerterrein, geen straatparkeren.
_MAX_STREET_PARKING_DEPTH_M = 8.0
# derive_parking: breder dan 3,5 m → haaksparkeren.
_PERPENDICULAR_DEPTH_M = 3.5
# Minimaal gedekt stuk van de link (m of fractie van de linklengte, de kleinste).
_MIN_COVER_M = 15.0
_MIN_COVER_FRACTION = 0.3
# Drempel hoort bij de link binnen deze afstand van de wegas …
_BUMP_DISTANCE_M = 4.0
# … en ligt 'op een kruispunt' binnen deze afstand van een eindpunt.
_BUMP_JUNCTION_M = 15.0
_DEFAULT_HALF_WIDTH_M = 3.0


def _active(assets: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Alleen actuele BGT-objecten: historische versies (eind_registratie of
    termination_date gezet) eruit, en per lokaal_id de laatste registratie."""
    out = assets
    for col in ("eind_registratie", "termination_date"):
        if col in out.columns:
            out = out[out[col].isna()]
    if "lokaal_id" in out.columns and "tijdstip_registratie" in out.columns:
        has_id = out["lokaal_id"].notna()
        latest = (
            out[has_id]
            .sort_values("tijdstip_registratie")
            .drop_duplicates("lokaal_id", keep="last")
        )
        out = pd.concat([latest, out[~has_id]])
    return out


def _half_width(props: dict) -> float:
    lo, hi = props.get("roadWidthMinM"), props.get("roadWidthMaxM")
    try:
        if lo is not None and hi is not None and math.isfinite(lo) and math.isfinite(hi):
            return (lo + hi) / 4
        w = props.get("roadWidthM")
        if w is not None and math.isfinite(w):
            return float(w)  # roadWidthM is al per richting (≈ halve breedte)
    except TypeError:
        pass
    return _DEFAULT_HALF_WIDTH_M


def _depth_and_cover(line, poly):
    """Diepte van het vak loodrecht op de link en het gedekte stuk langs de link (m)."""
    centroid = poly.centroid
    s = line.project(centroid)
    # Lokale richting van de link rond het projectiepunt.
    a = line.interpolate(max(s - 2.0, 0.0))
    b = line.interpolate(min(s + 2.0, line.length))
    dx, dy = b.x - a.x, b.y - a.y
    norm = math.hypot(dx, dy)
    if norm == 0:
        return None, 0.0
    ux, uy = dx / norm, dy / norm          # langs de weg
    nx, ny = -uy, ux                       # loodrecht op de weg
    coords = np.asarray(poly.exterior.coords)
    across = coords[:, 0] * nx + coords[:, 1] * ny
    depth = float(across.max() - across.min())
    along = [line.project(Point(x, y)) for x, y in coords]
    cover = float(max(along) - min(along))
    return depth, cover


def link_assets(features: list, assets: gpd.GeoDataFrame | None) -> dict:
    """Koppel parkeervlakken en drempels aan links (in-place op properties).

    Returns tellingen voor logging.
    """
    stats = {"parking_links": 0, "bump_links": 0, "parking_areas": 0, "speed_bumps": 0}
    if assets is None or assets.empty or not features:
        return stats

    assets = assets.to_crs(_METRIC_CRS) if assets.crs else assets.set_crs("EPSG:4326").to_crs(_METRIC_CRS)
    parking = _active(assets[assets["assetType"] == "parkingArea"])
    bumps = _active(assets[assets["assetType"] == "speedBump"])
    parking = parking[parking.geom_type == "Polygon"]
    stats["parking_areas"], stats["speed_bumps"] = len(parking), len(bumps)

    links = gpd.GeoDataFrame(
        {"i": range(len(features))},
        geometry=[shape(f["geometry"]) for f in features],
        crs="EPSG:4326",
    ).to_crs(_METRIC_CRS)

    # Links binnen het gebied dat de assets beslaan: daar is 'geen drempel'
    # een waarneming (BGT is volledig), daarbuiten weten we het niet.
    # Alleen als de BGT echt is opgehaald (anders kan een ontbrekende drempel
    # ook 'niet opgehaald' betekenen).
    if "source" in assets.columns and (assets["source"] == "BGT").any():
        from shapely.geometry import box
        covered = box(*assets.total_bounds)
        for i, line in zip(links["i"], links.geometry):
            if line is not None and covered.contains(line):
                features[i]["properties"]["assetsCovered"] = True

    p_index = parking.sindex
    b_index = bumps.sindex
    p_geoms = parking.geometry.values
    b_geoms = bumps.geometry.values

    for i, line in zip(links["i"], links.geometry):
        if line is None or line.is_empty or line.geom_type != "LineString" or line.length == 0:
            continue
        props = features[i]["properties"]
        reach = _half_width(props) + _PARKING_EDGE_MARGIN_M

        # ── Parkeren ──
        cover_by_type = {"langsparkeren": 0.0, "haaksparkeren": 0.0}
        depth_sum = 0.0
        for j in p_index.query(line.buffer(reach, cap_style="flat"), predicate="intersects"):
            poly = p_geoms[j]
            if poly.distance(line) > reach:
                continue
            depth, cover = _depth_and_cover(line, poly)
            if depth is None or depth > _MAX_STREET_PARKING_DEPTH_M or cover <= 0:
                continue
            kind = "haaksparkeren" if depth > _PERPENDICULAR_DEPTH_M else "langsparkeren"
            cover_by_type[kind] += cover
            depth_sum += depth * cover
        total = sum(cover_by_type.values())
        if total >= min(_MIN_COVER_M, _MIN_COVER_FRACTION * line.length):
            kind = max(cover_by_type, key=cover_by_type.get)
            props["assetParkingLocation"] = kind
            props["assetParkingWidth"] = round(depth_sum / total, 2)
            stats["parking_links"] += 1

        # ── Drempels ──
        on_section = on_junction = False
        for j in b_index.query(line.buffer(_BUMP_DISTANCE_M), predicate="intersects"):
            pos = line.project(b_geoms[j].centroid)
            if min(pos, line.length - pos) <= _BUMP_JUNCTION_M:
                on_junction = True
            else:
                on_section = True
        if on_section or on_junction:
            props["assetSpeedBumps"] = (
                "op wegvakken en kruispunten" if on_section and on_junction
                else "op wegvakken" if on_section else "op kruispunten"
            )
            stats["bump_links"] += 1

    return stats
