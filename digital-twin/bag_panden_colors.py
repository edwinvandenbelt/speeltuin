"""Kleurbepaling voor 3D BAG-panden (#19): gevel-/schuin-dak-/plat-dak-kleur per
pand, op basis van 'oorspronkelijkbouwjaar'.

Bedoeld om door een bag-panden-fetcher aangeroepen te worden zodat de kleuren
al in het weggeschreven bestand staan, als de properties ``wallColor``,
``roofColorPitched`` en ``roofColorFlat`` (elk ``"#rrggbb"``). Dat zijn precies
de propertynamen die de 3D BAG-viewer (digital-twin/scripts/main.js,
``_b3ResolveColors``) eerst per pand probeert te lezen; ontbreken ze (of is een
veld leeg/ongeldig), dan valt de viewer terug op dezelfde periode-paletlogica
als hieronder. Zet de fetcher deze kleuren dus vast, dan bepaalt de fetcher de
weergave; een later handmatige aanpassing van zo'n waarde in het bag-panden-
bestand blijft behouden (zie ``resolve_colors``: alleen ontbrekende velden
worden aangevuld) en komt direct door naar de 3D-weergave.

Komt bewust 1-op-1 overeen met de JS-tegenhanger in main.js (_BAG3D_PERIODS,
_b3PeriodIdx, _b3Hash, _b3FallbackColors), zodat een gebied dat de fetcher nog
niet heeft verwerkt er client-side hetzelfde uitziet als na verwerking.

Publieke API
------------
    period_index(year)             -> periode-index (1..N), of 0 als onbekend.
    fallback_colors(bouwjaar, id)  -> {"wallColor", "roofColorPitched", "roofColorFlat"}.
    resolve_colors(existing, bouwjaar, id)
        Vult alleen ontbrekende/lege velden in `existing` aan met fallback_colors;
        reeds aanwezige (ook handmatig gezette) waarden blijven ongewijzigd.
"""

from __future__ import annotations

Rgb = tuple[int, int, int]

# Terugval [gevel, schuin dak, plat dak] voor een onbekend/geen bouwjaar —
# ongewijzigd t.o.v. de kleuren die de viewer altijd al gebruikte.
DEFAULT_COLORS: tuple[Rgb, Rgb, Rgb] = ((236, 226, 210), (172, 94, 70), (156, 153, 148))

# Eén of meer kleurvarianten per bouwperiode [gevel, schuin dak, plat dak];
# latere jaren hebben er meer, zoals er in de praktijk ook meer materiaal-/
# kleurkeuze was. Welke variant een pand zonder explicite kleur krijgt wordt
# met _hash(pand-id) geloot (zie fallback_colors), zodat het willekeurig oogt
# maar stabiel is: hetzelfde pand krijgt altijd dezelfde kleur.
_PERIODS: tuple[dict, ...] = (
    {"before": 1800, "colors": (                                        # 17e/18e eeuw: donkere baksteen/pannen
        ((96, 52, 44), (72, 38, 32), (92, 90, 86)),
        ((84, 46, 40), (60, 40, 34), (88, 86, 82)),
    )},
    {"before": 1906, "colors": (                                        # 19e eeuw: lichte stuc, donker houtwerk
        ((222, 210, 188), (98, 70, 56), (122, 120, 114)),
        ((206, 196, 176), (70, 58, 50), (118, 116, 110)),
    )},
    {"before": 1945, "colors": (                                        # jaren '20-'30: warme rode/oranje baksteen
        ((152, 72, 52), (168, 88, 64), (140, 136, 130)),
        ((128, 64, 48), (140, 78, 58), (134, 130, 124)),
    )},
    {"before": 1970, "colors": (                                        # wederopbouw jaren '50-'60: gele baksteen/beton
        ((198, 190, 166), (150, 128, 104), (150, 148, 144)),
        ((172, 170, 164), (132, 118, 100), (146, 144, 140)),
    )},
    {"before": 1990, "colors": (                                        # jaren '70-'80: experimenteel, maar geen blauw
        ((112, 80, 56), (96, 68, 48), (112, 110, 106)),
        ((188, 150, 58), (168, 96, 40), (104, 98, 90)),                 # gele klinkers, bruin-oranje dak
        ((134, 54, 44), (104, 44, 38), (100, 98, 94)),
    )},
    {"before": None, "colors": (                                        # 1990-heden: veel materiaal-/kleurkeuze
        ((220, 220, 218), (72, 72, 76), (70, 68, 66)),
        ((196, 196, 198), (130, 130, 132), (128, 128, 130)),
        ((64, 64, 66), (48, 48, 50), (60, 60, 62)),
        ((150, 118, 86), (100, 76, 54), (92, 90, 86)),
    )},
)


def period_index(year: int | None) -> int:
    """Periode-index (1..N) in _PERIODS voor een bouwjaar, of 0 als onbekend/
    geen bruikbaar jaartal (→ terugval op DEFAULT_COLORS)."""
    if not year or not (1000 < year < 2100):
        return 0
    for i, period in enumerate(_PERIODS):
        before = period["before"]
        if before is None or year < before:
            return i + 1
    return len(_PERIODS)


def _hash(value: str) -> int:
    """FNV-1a (32-bit), alleen om deterministisch te 'loten' — identiek aan
    _b3Hash() in digital-twin/scripts/main.js."""
    h = 2166136261
    for ch in value:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def _variant_colors(idx: int, seed: int) -> tuple[Rgb, Rgb, Rgb]:
    if idx == 0:
        return DEFAULT_COLORS
    variants = _PERIODS[idx - 1]["colors"]
    return variants[seed % len(variants)]


def _to_hex(rgb: Rgb) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


# RGB-afstand waaronder gevel- en dakkleur als "vrijwel gelijk" gelden, en de
# factor waarmee een dakkleur dan donkerder wordt gemaakt ("een paar tinten
# donkerder"). Moet gelijk blijven aan gmt_network_enrichment.bag_fetcher
# (_SIMILAR_COLOR_DISTANCE / _DARKEN_FACTOR), zodat panden die de fetcher al
# heeft verwerkt er hetzelfde uitzien als panden die nog op deze fallback
# draaien.
_SIMILAR_COLOR_DISTANCE = 15.0
_DARKEN_FACTOR = 0.75


def _distance(a: Rgb, b: Rgb) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b, strict=True)) ** 0.5


def _darken(rgb: Rgb) -> Rgb:
    r, g, b = (max(0, round(c * _DARKEN_FACTOR)) for c in rgb)
    return (r, g, b)


def _adjust_roof(wall: Rgb, roof: Rgb) -> Rgb:
    """Maak `roof` een paar tinten donkerder als die vrijwel gelijk is aan `wall`."""
    if _distance(wall, roof) < _SIMILAR_COLOR_DISTANCE:
        return _darken(roof)
    return roof


def fallback_colors(bouwjaar: int | None, pand_id: str) -> dict[str, str]:
    """wallColor/roofColorPitched/roofColorFlat (als '#rrggbb') voor een pand
    zonder bestaande kleuren: periode-palet op basis van `bouwjaar`,
    kleurvariant geloot op `pand_id` (stabiel per pand). Een dakkleur die
    vrijwel niet te onderscheiden zou zijn van de gevelkleur wordt
    automatisch donkerder gemaakt (zie `_adjust_roof`)."""
    wall, pitched, flat = _variant_colors(period_index(bouwjaar), _hash(str(pand_id)))
    return {
        "wallColor": _to_hex(wall),
        "roofColorPitched": _to_hex(_adjust_roof(wall, pitched)),
        "roofColorFlat": _to_hex(_adjust_roof(wall, flat)),
    }


def resolve_colors(existing: dict | None, bouwjaar: int | None, pand_id: str) -> dict[str, str]:
    """Vul ontbrekende/lege wallColor/roofColorPitched/roofColorFlat aan met de
    terugval-kleuren, zonder al aanwezige (eventueel handmatig aangepaste)
    waarden te overschrijven — zo blijven persistente wijzigingen in het
    bag-panden-bestand bij een volgende fetcher-run behouden."""
    result = dict(existing or {})
    for key, value in fallback_colors(bouwjaar, pand_id).items():
        if not result.get(key):
            result[key] = value
    return result
