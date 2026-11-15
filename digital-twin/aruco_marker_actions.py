"""
Vaste koppeling marker-ID -> netwerkbewerking voor de maquette-objectmarkers.

Elke rij hier is een complete bewerking (actie + vaste parameter) die een
fysieke ArUco-tag vertegenwoordigt. Dit is de enige plek waar die koppeling
staat: `maquette_camera.py` leest hem om te bepalen wat een gedetecteerde
marker moet doen, en `generate_aruco_markers.py` leest hem om het label op
het printvel te zetten. Een nieuwe bewerking toevoegen is één nieuwe regel
hier (en, als het doel-type nieuw is, een nieuwe "nearest"-helper in
maquette_camera.py).

Elk bewerkingstype mag maar één keer tegelijk actief zijn: er wordt van elke
marker-ID precies één fysieke tag geprint, dus de ArUco-ID is zowel de
bewerkingssleutel als de track-identiteit (zie tracking.py).
"""

MARKER_ACTIONS = {
    0: {"label": "Wegvak afsluiten", "action": "close_link"},
    1: {"label": "30 km/u", "action": "set_speed", "params": {"speed": 30}},
    2: {"label": "+100 productie", "action": "add_production", "params": {"delta": "+100"}},
}


def known_marker_ids() -> set[int]:
    """Alle marker-IDs waarvoor een bewerking gedefinieerd is."""
    return set(MARKER_ACTIONS.keys())
