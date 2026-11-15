"""
generate_aruco_markers.py — print-klare ArUco-objectmarkers genereren
=======================================================================

Genereert één PNG per marker-ID uit `aruco_marker_actions.MARKER_ACTIONS`,
plus één gecombineerd PDF-vel op echte mm-schaal, met het label van elke
bewerking als bijschrift — zodat de operator op het uitgeprinte vel meteen
ziet welke tag welke bewerking doet.

Dit script draait los van de camera-detectie (geen sys.path-koppeling naar
kien-camera-maquette/ nodig) en gebruikt dezelfde ArUco-dictionary als
daar (zie kien-camera-maquette/config.py:ARUCO_DICTIONARY).

Gebruik:
    python generate_aruco_markers.py [--size-mm 60] [--out-dir aruco_markers]

Print het PDF-vel vervolgens op ware grootte (100 %, "fit to page" uit) en
plak elke tag op een vlak, stevig voorwerp — zie README.md voor montagetips.
"""
import argparse
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont

from aruco_marker_actions import MARKER_ACTIONS

# Zelfde dictionary als kien-camera-maquette/config.py:ARUCO_DICTIONARY.
_ARUCO_DICTIONARY = cv2.aruco.DICT_4X4_50

# 300 dpi is ruim genoeg voor een scherpe inkjet-/laserprint.
_DPI = 300
_MM_PER_INCH = 25.4

# Witruimte rond de marker (ArUco's eigen "rustzone", nodig voor betrouwbare
# detectie) en onder de marker voor het label.
_QUIET_ZONE_MM = 10.0
_LABEL_HEIGHT_MM = 12.0

# A4 in mm, en de marge/tussenruimte tussen de tegels op het PDF-vel.
_PAGE_SIZE_MM = (210.0, 297.0)
_PAGE_MARGIN_MM = 15.0
_PAGE_GAP_MM = 15.0


def _mm_to_px(mm: float) -> int:
    return round(mm / _MM_PER_INCH * _DPI)


def generate_marker_bitmap(marker_id: int, size_mm: float, dictionary=_ARUCO_DICTIONARY) -> Image.Image:
    """Genereer de kale ArUco-bitmap (zonder rustzone/label), op schaal."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary)
    size_px = _mm_to_px(size_mm)
    marker_array = cv2.aruco.generateImageMarker(aruco_dict, marker_id, size_px)
    return Image.fromarray(marker_array)


def _label_font(height_px: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype("arial.ttf", size=round(height_px * 0.5))
    except OSError:
        # Geen TrueType-font gevonden (bv. buiten Windows): nette fallback,
        # weliswaar op vaste (kleinere) grootte.
        return ImageFont.load_default()


def generate_marker_tile(marker_id: int, label: str, size_mm: float, dictionary=_ARUCO_DICTIONARY) -> Image.Image:
    """Plaats de marker-bitmap midden op een wit vlak met rustzone en het
    label (marker-ID + bewerking) eronder — dit is wat zowel als los PNG-
    bestand als op het PDF-vel terechtkomt."""
    marker_bitmap = generate_marker_bitmap(marker_id, size_mm, dictionary)
    quiet_px = _mm_to_px(_QUIET_ZONE_MM)
    label_px = _mm_to_px(_LABEL_HEIGHT_MM)
    marker_px = marker_bitmap.width

    tile_w = marker_px + 2 * quiet_px
    tile_h = marker_px + 2 * quiet_px + label_px

    tile = Image.new("L", (tile_w, tile_h), color=255)
    tile.paste(marker_bitmap, (quiet_px, quiet_px))

    draw = ImageDraw.Draw(tile)
    font = _label_font(label_px)
    text = f"#{marker_id}  {label}"
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_y = quiet_px + marker_px + (quiet_px - (text_bbox[3] - text_bbox[1])) // 2
    draw.text(((tile_w - text_w) / 2, text_y), text, fill=0, font=font)

    return tile


def build_pdf_pages(tiles: "list[Image.Image]", page_size_mm=_PAGE_SIZE_MM) -> "list[Image.Image]":
    """Verdeel de tegels verticaal gecentreerd over zoveel pagina's als nodig,
    op echte mm-schaal. Bij een groter --size-mm of meer bewerkingen in
    MARKER_ACTIONS past simpelweg niet alles op één A4-vel — dan komt er
    vanzelf een volgende pagina bij, in plaats van tegels van de pagina af te
    laten vallen."""
    page_w = _mm_to_px(page_size_mm[0])
    page_h = _mm_to_px(page_size_mm[1])
    margin = _mm_to_px(_PAGE_MARGIN_MM)
    gap = _mm_to_px(_PAGE_GAP_MM)

    pages: "list[Image.Image]" = []
    page = Image.new("L", (page_w, page_h), color=255)
    y = margin
    is_first_on_page = True

    for tile in tiles:
        if tile.height > page_h - 2 * margin:
            raise ValueError(
                f"Marker van {tile.height}px hoog past niet op een pagina van "
                f"{page_h}px (marges {margin}px boven/onder) — verklein --size-mm."
            )
        if not is_first_on_page and y + gap + tile.height > page_h - margin:
            pages.append(page.convert("RGB"))
            page = Image.new("L", (page_w, page_h), color=255)
            y = margin
            is_first_on_page = True
        elif not is_first_on_page:
            y += gap

        x = (page_w - tile.width) // 2
        page.paste(tile, (x, y))
        y += tile.height
        is_first_on_page = False

    pages.append(page.convert("RGB"))
    return pages


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genereer print-klare ArUco-objectmarkers (PNG per marker-ID + één PDF-vel)."
    )
    parser.add_argument(
        "--size-mm",
        type=float,
        default=60.0,
        help="Fysieke afdrukgrootte van elke marker in mm (default: 60). "
        "Tune dit na een proefafdruk, op basis van de leesafstand tot de camera.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "aruco_markers",
        help="Map om de PNG's en het PDF-vel in te zetten (default: digital-twin/aruco_markers/)",
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    tiles = []
    for marker_id, action_def in sorted(MARKER_ACTIONS.items()):
        tile = generate_marker_tile(marker_id, action_def["label"], args.size_mm)
        png_path = args.out_dir / f"aruco_marker_{marker_id}.png"
        tile.save(png_path, dpi=(_DPI, _DPI))
        print(f"[markers] {png_path}  (#{marker_id} {action_def['label']})")
        tiles.append(tile)

    pdf_path = args.out_dir / "aruco_markers.pdf"
    pages = build_pdf_pages(tiles)
    pages[0].save(pdf_path, "PDF", save_all=True, append_images=pages[1:], resolution=float(_DPI))
    print(
        f"[markers] {pdf_path}  (alle {len(tiles)} markers op schaal over "
        f"{len(pages)} pagina('s) — print op 100%, 'fit to page' uit)"
    )


if __name__ == "__main__":
    main()
