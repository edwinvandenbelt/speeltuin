#!/usr/bin/env python3
"""
export_to_sumo.py  –  Exporteert een GMP-speeltuin scenario naar SUMO-importformaat.

Genereert in de output-map:
  nodes.nod.xml   – knooppunten (invoer voor netconvert)
  edges.edg.xml   – wegvakken   (invoer voor netconvert)
  routes.rou.xml  – voertuigstromen o.b.v. OD-routes
  sumo.cfg        – SUMO-configuratiebestand
  README.txt      – instructies voor netconvert + sumo-gui

Gebruik:
  python export_to_sumo.py --area-dir work/Hasselt --output-dir output/sumo/Hasselt
  python export_to_sumo.py --area-dir work/Vreden  --output-dir output/sumo/Vreden \\
      --mode CAR --daypart mrh --sim-duration 7200

Vereisten:
  pip install geopandas pyarrow

SUMO-installatie (voor netconvert en sumo-gui):
  https://sumo.dlr.de/docs/Downloads.html
"""

import argparse
import json
import math
import os
import re
import sys
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

try:
    import geopandas as gpd
except ImportError:
    sys.exit("geopandas is vereist: pip install geopandas pyarrow")


# ── Dagdeel-fracties (identiek aan index.html DP_FRACTION) ──────────────────
# Basis 14.4 gewichtseenheden per dag  (2 spitsuren + 20 daluren × 0.52)
DP_FRACTION = {
    "mrh": 1 / 14.4,  # ochtendspits  07:00–09:00  (~0.0694)
    "erh": 1 / 14.4,  # avondspits    16:00–18:00  (~0.0694)
    "rest": (10.4 / 20) / 14.4,  # daluren    overig       (~0.0361)
}

# Tijdvensters per dagdeel in seconden vanaf middernacht
DP_WINDOW = {
    "mrh": (7 * 3600, 9 * 3600),  # 07:00–09:00
    "erh": (16 * 3600, 18 * 3600),  # 16:00–18:00
    "rest": (9 * 3600, 16 * 3600),  # 09:00–16:00 (vereenvoudigd daluur-blok)
}


# ── Hulpfuncties ─────────────────────────────────────────────────────────────


def _linkid_to_sumo_edge(lid) -> str:
    """
    Zet een GMP linkId om naar een SUMO edge-ID.

    Twee formaten worden ondersteund:
    • int64  (Hasselt):  40483658    -> '40483658'
                         40483658001 -> '40483658_001'   (suffix als 3-cijfer index)
                        -40483658    -> '-40483658'
                        -40483658001 -> '-40483658_001'
    • string (Vreden):  '30133009'   -> '30133009'
                         '30133009_1' -> '30133009_1'    (ongewijzigd)
                        '-30133009_1'-> '-30133009_1'

    We gebruiken de GMP linkId rechtstreeks als SUMO edge-ID zodat de linkPath
    uit het ROUTES-parquet direct bruikbaar is zonder extra vertaalstap.
    """
    s = str(lid)
    # int64 met geencodeerde suffix: bv. 40483658001 (> 1 miljard, suffix = laatste 3 cijfers)
    neg = s.startswith("-")
    abs_s = s.lstrip("-")
    if abs_s.isdigit() and len(abs_s) > 9:
        base = abs_s[:-3]
        suffix = abs_s[-3:].lstrip("0") or "0"
        return f"{'-' if neg else ''}{base}_{suffix:>03}"
    return s


def _sumo_edge_from_linkpath_entry(lid_str: str) -> str:
    """
    Converteert een linkPath entry (altijd een string) naar het overeenkomstige
    SUMO edge-ID, rekening houdend met beide formaten.
    """
    s = str(lid_str)
    neg = s.startswith("-")
    abs_s = s.lstrip("-")

    # int64 geencodeerd formaat: puur numeriek en > 9 cijfers -> suffix
    if abs_s.isdigit() and len(abs_s) > 9:
        base = abs_s[:-3]
        suffix = abs_s[-3:].lstrip("0") or "0"
        return f"{'-' if neg else ''}{base}_{suffix:>03}"

    # string-formaat of enkelvoudig integer
    return s


def _pretty_xml(root: ET.Element) -> str:
    """Retourneert mooi opgemaakte XML-string met declaratie."""
    raw = ET.tostring(root, encoding="unicode")
    parsed = minidom.parseString(raw)
    lines = parsed.toprettyxml(indent="    ").splitlines()
    # minidom voegt een lege eerste regel toe; verwijder die
    return "\n".join(line for line in lines if line.strip())


def _find_parquet(area_dir: Path, file_type: str, mode: str) -> Path | None:
    """Zoek een parquet-bestand op basis van type en modus."""
    pattern = re.compile(
        r"^[0-9a-f\-]+-"
        + re.escape(file_type)
        + r"-"
        + re.escape(mode)
        + r"\.parquet$",
        re.IGNORECASE,
    )
    for f in area_dir.iterdir():
        if pattern.match(f.name):
            return f
    return None


def _detect_area_id(area_dir: Path) -> str | None:
    """Lees het area-ID uit .area-uuid of leid het af uit de bestandsnamen."""
    uuid_file = area_dir / ".area-uuid"
    if uuid_file.exists():
        return uuid_file.read_text().strip()
    for f in area_dir.iterdir():
        m = re.match(r"^([0-9a-f\-]{36})-NETWORK", f.name)
        if m:
            return m.group(1)
    return None


# ── Hoofd-exportfuncties ─────────────────────────────────────────────────────


def build_nodes_and_edges(net_gdf, feedlink_gdf=None):
    """
    Bouwt twee dicts:
      nodes: nodeId -> (lon, lat)
      edges: list van edge-dicts met SUMO-attributen

    Knooppuntcoördinaten worden afgeleid uit de geometrie-eindpunten van de links.
    Voedingslinks (zone-connectors) worden als speciale edges toegevoegd.
    """
    nodes = {}  # nodeId (str) -> (lon, lat)
    edges = []

    for _, row in net_gdf.iterrows():
        coords = list(row.geometry.coords)  # [(lon, lat), ...]
        if len(coords) < 2:
            continue

        from_node = str(row["fromNode"])
        to_node = str(row["toNode"])

        # Sla self-loops over (fromNode == toNode); netconvert negeert deze toch.
        if from_node == to_node:
            continue

        edge_id = _linkid_to_sumo_edge(row["linkId"])

        # Knooppuntcoördinaten uit eerste / laatste geometriepunt
        if from_node not in nodes:
            nodes[from_node] = (coords[0][0], coords[0][1])
        if to_node not in nodes:
            nodes[to_node] = (coords[-1][0], coords[-1][1])

        speed_ms = float(row["speed"]) / 3.6  # km/h -> m/s
        length_m = float(row["length"])
        lanes = int(row["lanes"]) if row["lanes"] and row["lanes"] > 0 else 1
        capacity = float(row["capacity"]) if row["capacity"] else 1800 * lanes
        highway = str(row.get("highway", ""))

        # Geometrie als SUMO shape-string "lon,lat lon,lat ..."
        shape = " ".join(f"{c[0]:.7f},{c[1]:.7f}" for c in coords)

        edges.append(
            dict(
                id=edge_id,
                from_node=from_node,
                to_node=to_node,
                speed=round(speed_ms, 3),
                length=round(length_m, 2),
                numLanes=lanes,
                capacity=round(capacity, 1),
                highway=highway,
                shape=shape,
            )
        )

    # Voedingslinks (zone-connectors) – optioneel
    if feedlink_gdf is not None:
        for _, row in feedlink_gdf.iterrows():
            coords = list(row.geometry.coords)
            if len(coords) < 2:
                continue
            from_node = str(row["fromNode"])
            to_node = str(row["toNode"])
            edge_id = f"feedlink_{from_node}_{to_node}"

            if from_node not in nodes:
                nodes[from_node] = (coords[0][0], coords[0][1])
            if to_node not in nodes:
                nodes[to_node] = (coords[-1][0], coords[-1][1])

            length_m = max(float(row.get("length", 10)), 1.0)
            shape = " ".join(f"{c[0]:.7f},{c[1]:.7f}" for c in coords)

            edges.append(
                dict(
                    id=edge_id,
                    from_node=from_node,
                    to_node=to_node,
                    speed=13.89,  # 50 km/h
                    length=round(length_m, 2),
                    numLanes=1,
                    capacity=9999.0,
                    highway="connector",
                    shape=shape,
                )
            )

    return nodes, edges


def write_nodes_xml(nodes: dict, output_path: Path):
    """Schrijft nodes.nod.xml."""
    root = ET.Element("nodes")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xsi:noNamespaceSchemaLocation", "http://sumo.dlr.de/xsd/nodes_file.xsd")

    for node_id, (lon, lat) in sorted(nodes.items()):
        node = ET.SubElement(root, "node")
        node.set("id", node_id)
        node.set("x", f"{lon:.7f}")
        node.set("y", f"{lat:.7f}")

    output_path.write_text(_pretty_xml(root), encoding="utf-8")
    print(f"  OK {output_path.name}  ({len(nodes)} knooppunten)")


def write_edges_xml(edges: list, output_path: Path):
    """Schrijft edges.edg.xml."""
    root = ET.Element("edges")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xsi:noNamespaceSchemaLocation", "http://sumo.dlr.de/xsd/edges_file.xsd")

    for e in edges:
        edge = ET.SubElement(root, "edge")
        edge.set("id", e["id"])
        edge.set("from", e["from_node"])
        edge.set("to", e["to_node"])
        edge.set("speed", str(e["speed"]))
        edge.set("length", str(e["length"]))
        edge.set("numLanes", str(e["numLanes"]))
        if e.get("shape"):
            edge.set("shape", e["shape"])
        if e.get("highway"):
            edge.set("type", e["highway"])

    output_path.write_text(_pretty_xml(root), encoding="utf-8")
    print(f"  OK {output_path.name}  ({len(edges)} wegvakken)")


def build_route_flows(routes_gdf, daypart: str, min_flow: float = 0.1):
    """
    Converteert OD-routes naar SUMO <route> + <flow> elementen.

    Per sub-route wordt berekend:
      vehsPerHour = originProduction × DP_FRACTION[daypart] × trips_fraction

    Retourneert:
      route_defs : list van (route_id, [edge_id, ...])
      flow_defs  : list van (flow_id, route_id, begin_s, end_s, vehsPerHour)
    """
    dp_frac = DP_FRACTION[daypart]
    begin_s, end_s = DP_WINDOW[daypart]

    # Bepaal of trips absoluut of fractioneel zijn (zie isAbsolute-logica in index.html)
    zone_trip_sums = {}
    for _, row in routes_gdf.iterrows():
        fz = row["fromZoneId"]
        for r in json.loads(row["routes"]):
            zone_trip_sums[fz] = zone_trip_sums.get(fz, 0.0) + float(r.get("trips", 0))
    is_absolute = max(zone_trip_sums.values(), default=0) > 1.5

    route_defs = []
    flow_defs = []
    route_counter = 0

    for _, row in routes_gdf.iterrows():
        origin_prod = float(row.get("originProduction", 0))
        if origin_prod <= 0 and not is_absolute:
            continue

        zone_sum = zone_trip_sums.get(row["fromZoneId"], 1.0) or 1.0
        sub_routes = json.loads(row["routes"])

        for sr in sub_routes:
            trips_val = float(sr.get("trips", 0))
            if trips_val <= 0:
                continue

            link_path = sr.get("linkPath", [])
            if not link_path:
                continue

            # Bereken uurintensiteit
            if is_absolute:
                # trips is absoluut aantal voertuigen/dag; normaliseer eerst
                weight = trips_val / zone_sum
                vph = zone_sum * dp_frac * weight
            else:
                # trips is fractie [0-1] van originProduction
                vph = origin_prod * dp_frac * trips_val

            if vph < min_flow:
                continue

            # Converteer linkPath -> SUMO edge IDs
            edge_ids = [_sumo_edge_from_linkpath_entry(lid) for lid in link_path]

            route_id = f"route_{route_counter}"
            flow_id = f"flow_{route_counter}"
            route_counter += 1

            route_defs.append((route_id, edge_ids))
            flow_defs.append(
                (
                    flow_id,
                    route_id,
                    begin_s,
                    end_s,
                    round(vph, 4),
                    row["fromZoneId"],
                    row["toZoneId"],
                )
            )

    return route_defs, flow_defs


def write_routes_xml(
    route_defs: list, flow_defs: list, output_path: Path, daypart: str
):
    """Schrijft routes.rou.xml."""
    root = ET.Element("routes")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xsi:noNamespaceSchemaLocation", "http://sumo.dlr.de/xsd/routes_file.xsd")

    # Voertuigtype
    vtype = ET.SubElement(root, "vType")
    vtype.set("id", "car")
    vtype.set("vClass", "passenger")
    vtype.set("maxSpeed", "50")
    vtype.set("accel", "2.6")
    vtype.set("decel", "4.5")
    vtype.set("length", "4.5")
    vtype.set("color", "0.8,0.2,0.2")

    # Routes
    route_id_set = set()
    for route_id, edge_ids in route_defs:
        if route_id in route_id_set:
            continue
        route_id_set.add(route_id)
        r = ET.SubElement(root, "route")
        r.set("id", route_id)
        r.set("edges", " ".join(edge_ids))

    # Flows
    begin_s, end_s = DP_WINDOW[daypart]
    for flow_id, route_id, begin_s, end_s, vph, from_zone, to_zone in flow_defs:
        f = ET.SubElement(root, "flow")
        f.set("id", flow_id)
        f.set("type", "car")
        f.set("route", route_id)
        f.set("begin", str(begin_s))
        f.set("end", str(end_s))
        f.set("vehsPerHour", str(vph))
        f.set("departLane", "best")
        f.set("departSpeed", "max")
        # Bewaar OD-info als SUMO params
        ET.SubElement(f, "param").set("key", "fromZoneId")
        f[-1].set("value", from_zone)
        ET.SubElement(f, "param").set("key", "toZoneId")
        f[-1].set("value", to_zone)

    output_path.write_text(_pretty_xml(root), encoding="utf-8")
    print(
        f"  OK {output_path.name}  ({len(route_defs)} routes, {len(flow_defs)} flows)"
    )


def write_sumo_config(
    output_dir: Path, area_name: str, sim_duration: int, daypart: str
):
    """Schrijft sumo.cfg."""
    begin_s, end_s = DP_WINDOW[daypart]

    cfg = ET.Element("configuration")
    cfg.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    cfg.set(
        "xsi:noNamespaceSchemaLocation", "http://sumo.dlr.de/xsd/sumoConfiguration.xsd"
    )

    inp = ET.SubElement(cfg, "input")
    ET.SubElement(inp, "net-file").set("value", "network.net.xml")
    ET.SubElement(inp, "route-files").set("value", "routes.rou.xml")

    time = ET.SubElement(cfg, "time")
    ET.SubElement(time, "begin").set("value", str(begin_s))
    ET.SubElement(time, "end").set("value", str(end_s))
    ET.SubElement(time, "step-length").set("value", "1")

    report = ET.SubElement(cfg, "report")
    ET.SubElement(report, "verbose").set("value", "true")
    ET.SubElement(report, "no-step-log").set("value", "false")

    out_el = ET.SubElement(cfg, "output")
    ET.SubElement(out_el, "summary-output").set("value", "summary.xml")
    ET.SubElement(out_el, "tripinfo-output").set("value", "tripinfo.xml")
    ET.SubElement(out_el, "edgedata-output").set("value", "edgedata.xml")

    proc = ET.SubElement(cfg, "processing")
    ET.SubElement(proc, "ignore-route-errors").set("value", "true")

    cfg_path = output_dir / "sumo.cfg"
    cfg_path.write_text(_pretty_xml(cfg), encoding="utf-8")
    print(f"  OK sumo.cfg  (dagdeel={daypart}, {begin_s}s–{end_s}s)")


def filter_routes_with_net(routes_xml: Path, net_xml: Path, output_path: Path):
    """
    Filtert routes.rou.xml zodat alleen edges worden gebruikt die in network.net.xml
    bestaan. Routes waarbij meer dan de helft van de edges ontbreekt worden verwijderd.

    Gebruik deze stap NA het uitvoeren van netconvert, omdat netconvert edges kan
    verwijderen of samenvoegen (bijv. bij --geometry.remove).

    Retourneert (behouden_routes, verwijderde_routes, behouden_flows, verwijderde_flows).
    """
    # Laad geldige edge IDs uit net.xml (interne junction-edges beginnen met ':')
    net_tree = ET.parse(net_xml)
    valid_edges = {
        e.get("id")
        for e in net_tree.findall(".//edge")
        if e.get("id") and not e.get("id").startswith(":")
    }
    print(f"  Netwerk bevat {len(valid_edges)} geldige edges")

    rou_tree = ET.parse(routes_xml)
    root = rou_tree.getroot()

    # Bouw mapping route_id -> edge list
    routes_by_id = {}
    for r in root.findall("route"):
        rid = r.get("id")
        edges = r.get("edges", "").split()
        routes_by_id[rid] = edges

    kept_routes, dropped_routes = 0, 0
    kept_flows, dropped_flows = 0, 0
    valid_route_ids = set()

    for r in root.findall("route"):
        rid = r.get("id")
        edges = r.get("edges", "").split()
        # Behoud alleen edges die in het netwerk bestaan
        filtered = [e for e in edges if e in valid_edges]
        missing = len(edges) - len(filtered)
        # Verwijder route als >50% van de edges ontbreekt of <2 edges resten
        if len(filtered) < 2 or missing / max(len(edges), 1) > 0.5:
            root.remove(r)
            dropped_routes += 1
        else:
            r.set("edges", " ".join(filtered))
            valid_route_ids.add(rid)
            kept_routes += 1

    # Verwijder flows waarvan de route is weggevallen
    for f in root.findall("flow"):
        if f.get("route") not in valid_route_ids:
            root.remove(f)
            dropped_flows += 1
        else:
            kept_flows += 1

    output_path.write_text(_pretty_xml(root), encoding="utf-8")
    print(f"  OK {output_path.name}")
    print(f"     Routes: {kept_routes} behouden, {dropped_routes} verwijderd")
    print(f"     Flows:  {kept_flows} behouden, {dropped_flows} verwijderd")
    return kept_routes, dropped_routes, kept_flows, dropped_flows


def write_readme(output_dir: Path, area_name: str, daypart: str):
    """Schrijft README.txt met instructies voor netconvert en sumo-gui."""
    begin_s, end_s = DP_WINDOW[daypart]
    readme = textwrap.dedent(f"""
        SUMO-export van GMP-scenario: {area_name}
        Dagdeel: {daypart}  ({begin_s // 3600:02d}:00 – {end_s // 3600:02d}:00)
        =====================================================

        Stap 1 – Netwerk bouwen met netconvert
        ──────────────────────────────────────
        De coördinaten in nodes.nod.xml zijn WGS84 (lon/lat in graden).
        Zonder --proj.utm behandelt netconvert deze als meters, wat een
        sterk vervormde "stekelbal" oplevert in sumo-gui.

        LET OP: gebruik GEEN --geometry.remove en GEEN --junctions.join.
        Deze opties voegen edges samen, waarna routes naar verwijderde edges
        verwijzen en SUMO crasht. Gebruik:

        netconvert \\
            --node-files nodes.nod.xml \\
            --edge-files edges.edg.xml \\
            --output-file network.net.xml \\
            --proj.utm \\
            --no-internal-links

        Stap 1b – Routes filteren na netconvert (optioneel maar aanbevolen)
        ─────────────────────────────────────────────────────────────────────
        Als toch netconvert-opties zijn gebruikt die edges kunnen verwijderen,
        filter dan de routes met:

        python export_to_sumo.py \\
            --area-dir <gebied> \\
            --output-dir {output_dir.name} \\
            --filter-with-net {output_dir.name}/network.net.xml

        Dit overschrijft routes.rou.xml met alleen geldige routes.

        Stap 2 – Simulatie uitvoeren
        ────────────────────────────
        sumo-gui -c sumo.cfg
          of
        sumo -c sumo.cfg

        Stap 3 – Resultaten bekijken
        ────────────────────────────
        summary.xml   – totaal voertuigen, reistijden per tijdstap
        tripinfo.xml  – per voertuig: vertrektijd, reistijd, afstand
        edgedata.xml  – verkeersintensiteit per wegvak

        Kalibratie met routeSampler.py (aanbevolen)
        ────────────────────────────────────────────
        SUMO's routeSampler.py verfijnt routes.rou.xml op basis van de
        gemeten intensiteiten per wegvak (flows_observed.xml):

        python %SUMO_HOME%/tools/routeSampler.py \\
            --net-file network.net.xml \\
            --route-files routes.rou.xml \\
            --edgedata-files flows_observed.xml \\
            --output-file routes_calibrated.rou.xml \\
            --begin {begin_s} --end {end_s}

        Bestanden
        ─────────
        nodes.nod.xml        – {area_name} knooppunten (WGS84)
        edges.edg.xml        – {area_name} wegvakken
        routes.rou.xml       – OD-voertuigstromen (dagdeel: {daypart})
        flows_observed.xml   – gemeten intensiteiten per wegvak (voor routeSampler)
        sumo.cfg             – simulatieconfiguratie
        network.net.xml      – gegenereerd door netconvert (nog niet aanwezig)
    """).strip()
    (output_dir / "README.txt").write_text(readme, encoding="utf-8")
    print("  OK README.txt")


def write_observed_flows_xml(net_gdf, daypart: str, output_path: Path):
    """
    Schrijft een SUMO edgedata-XML met de gemeten intensiteiten per wegvak.
    Kan worden gebruikt door routeSampler.py voor kalibratie.
    """
    dp_frac = DP_FRACTION[daypart]

    root = ET.Element("data")
    interval = ET.SubElement(root, "interval")
    begin_s, end_s = DP_WINDOW[daypart]
    interval.set("begin", str(begin_s))
    interval.set("end", str(end_s))
    interval.set("id", "observed")

    for _, row in net_gdf.iterrows():
        edge_id = _linkid_to_sumo_edge(row["linkId"])

        # Gebruik flowsPerDaypart indien beschikbaar, anders flow × DP_FRACTION
        fp = row.get("flowsPerDaypart")
        if fp and isinstance(fp, dict):
            flow_vph = float(fp.get(daypart, 0))
        elif fp and isinstance(fp, str):
            try:
                fp_dict = json.loads(fp)
                flow_vph = float(fp_dict.get(daypart, 0))
            except Exception:
                flow_vph = float(row.get("flow24hrs", row.get("flow", 0))) * dp_frac
        else:
            flow_vph = float(row.get("flow24hrs", row.get("flow", 0))) * dp_frac

        if flow_vph <= 0:
            continue

        edge_el = ET.SubElement(interval, "edge")
        edge_el.set("id", edge_id)
        edge_el.set("entered", str(round(flow_vph, 2)))

    output_path.write_text(_pretty_xml(root), encoding="utf-8")
    print(
        f"  OK {output_path.name}  (gemeten intensiteiten per wegvak voor routeSampler)"
    )


# ── CLI ──────────────────────────────────────────────────────────────────────


def parse_args():
    p = argparse.ArgumentParser(
        description="Exporteer een GMP-speeltuin scenario naar SUMO-importformaat.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--area-dir",
        required=True,
        help="Map met de GMP parquet-bestanden (bijv. work/Hasselt)",
    )
    p.add_argument("--output-dir", required=True, help="Output-map voor SUMO-bestanden")
    p.add_argument(
        "--mode",
        default="CAR",
        help="Transportmodus: CAR, BIKE, MIXED (standaard: CAR)",
    )
    p.add_argument(
        "--daypart",
        default="mrh",
        choices=list(DP_FRACTION.keys()),
        help="Dagdeel: mrh (ochtendspits), erh (avondspits), "
        "rest (daluren)  (standaard: mrh)",
    )
    p.add_argument(
        "--min-flow",
        type=float,
        default=0.1,
        help="Minimale uurintensiteit [vtg/h] om een route op te nemen "
        "(standaard: 0.1)",
    )
    p.add_argument(
        "--include-feedlinks",
        action="store_true",
        help="Voedingslinks (zone-connectors) opnemen in het netwerk",
    )
    p.add_argument(
        "--no-observed-flows",
        action="store_true",
        help="Geen flows_observed.xml schrijven",
    )
    return p.parse_args()


def main():
    args = parse_args()
    area_dir = Path(args.area_dir)
    output_dir = Path(args.output_dir)

    if not area_dir.is_dir():
        sys.exit(f"Fout: map niet gevonden: {area_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    area_name = area_dir.name
    mode = args.mode.upper()

    print(f"\nGMP -> SUMO export")
    print(f"  Gebied:   {area_name}")
    print(f"  Modus:    {mode}")
    print(f"  Dagdeel:  {args.daypart}")
    print(f"  Output:   {output_dir}\n")

    # ── 1. Parquet-bestanden laden ──────────────────────────────────────────
    net_path = _find_parquet(area_dir, "NETWORK", mode)
    rte_path = _find_parquet(area_dir, "ROUTES", mode)
    feed_path = _find_parquet(area_dir, "FEEDLINK", mode)

    if not net_path:
        sys.exit(f"Fout: NETWORK-{mode}.parquet niet gevonden in {area_dir}")

    print("Bestanden laden...")
    net_gdf = gpd.read_parquet(net_path)
    print(f"  OK NETWORK  ({len(net_gdf)} wegvakken)")

    routes_gdf = None
    if rte_path:
        routes_gdf = gpd.read_parquet(rte_path)
        print(f"  OK ROUTES   ({len(routes_gdf)} OD-paren)")
    else:
        print(
            f"  !  ROUTES-{mode}.parquet niet gevonden – alleen netwerk wordt geëxporteerd"
        )

    feed_gdf = None
    if args.include_feedlinks and feed_path:
        feed_gdf = gpd.read_parquet(feed_path)
        print(f"  OK FEEDLINK ({len(feed_gdf)} connectors)")

    # ── 2. Netwerk schrijven ────────────────────────────────────────────────
    print("\nNetwerk verwerken...")
    nodes, edges = build_nodes_and_edges(net_gdf, feed_gdf)
    write_nodes_xml(nodes, output_dir / "nodes.nod.xml")
    write_edges_xml(edges, output_dir / "edges.edg.xml")

    # ── 3. Routes + flows schrijven ─────────────────────────────────────────
    if routes_gdf is not None:
        print("\nRoutes verwerken...")
        route_defs, flow_defs = build_route_flows(
            routes_gdf, args.daypart, args.min_flow
        )
        if route_defs:
            write_routes_xml(
                route_defs, flow_defs, output_dir / "routes.rou.xml", args.daypart
            )
        else:
            print(
                "  !  Geen routes met voldoende flow gevonden "
                f"(min_flow={args.min_flow} vtg/h)"
            )

    # ── 4. Gemeten intensiteiten (voor routeSampler.py) ─────────────────────
    if not args.no_observed_flows:
        print("\nGemeten intensiteiten schrijven...")
        write_observed_flows_xml(
            net_gdf, args.daypart, output_dir / "flows_observed.xml"
        )

    # ── 5. Config + README ──────────────────────────────────────────────────
    print("\nConfiguratie schrijven...")
    begin_s, end_s = DP_WINDOW[args.daypart]
    write_sumo_config(output_dir, area_name, end_s - begin_s, args.daypart)
    write_readme(output_dir, area_name, args.daypart)

    # ── Samenvatting ────────────────────────────────────────────────────────
    print(f"""
Klaar! Bestanden in: {output_dir}

Volgende stap – netwerk compileren met netconvert:
  netconvert --node-files {output_dir / "nodes.nod.xml"} --edge-files {output_dir / "edges.edg.xml"} --output-file {output_dir / "network.net.xml"} --proj.utm --no-internal-links

Daarna simuleren:
  sumo-gui -c {output_dir / "sumo.cfg"}
""")


if __name__ == "__main__":
    main()
