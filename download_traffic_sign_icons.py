#!/usr/bin/env python3
"""
Download realistische PNG-iconen voor Nederlandse RVV-verkeersborden van NDW.

Bron:  https://wegkenmerken.ndw.nu/assets/images/traffic-signs/{code}.png
Doel:  traffic_sign_icons/{code}.png

Gebruik:  python download_traffic_sign_icons.py
"""

import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE_URL = 'https://wegkenmerken.ndw.nu/assets/images/traffic-signs/{code}.png'

CODES = [
    # A-borden (snelheid / adviessnelheid) — basisvormen
    'A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8',
    # A1 snelheidsvarianten (rvvCode=A1, blackCode=<getal>)
    'A1-5', 'A1-10', 'A1-15', 'A1-20', 'A1-25', 'A1-30', 'A1-40', 'A1-50',
    'A1-60', 'A1-70', 'A1-80', 'A1-90', 'A1-100', 'A1-110', 'A1-120', 'A1-130',
    # A2 adviessnelheidsvarianten
    'A2-10', 'A2-20', 'A2-30', 'A2-40', 'A2-50', 'A2-60', 'A2-70', 'A2-80',
    'A2-90', 'A2-100', 'A2-120',
    # A3 adviessnelheid zone
    'A3-30', 'A3-50', 'A3-60', 'A3-70', 'A3-80', 'A3-100',
    # A4 adviessnelheid tijdelijk
    'A4-10', 'A4-15', 'A4-20', 'A4-25', 'A4-30', 'A4-40', 'A4-50',
    'A4-60', 'A4-70', 'A4-80', 'A4-100',
    # B-borden (voorrang)
    'B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7',
    # C-borden (geslotenverklaring) — basisvormen
    'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C7a', 'C7b', 'C8', 'C9',
    'C10', 'C11', 'C12', 'C13', 'C14', 'C15', 'C16', 'C17', 'C18', 'C19',
    'C20', 'C21', 'C22', 'C22a',
    # C4 rijrichting varianten
    'C4-L', 'C4-R',
    # C12 hoogtebeperkingen (m)
    'C12-1.8', 'C12-2.0', 'C12-2.1', 'C12-2.2', 'C12-2.3', 'C12-2.4',
    'C12-2.5', 'C12-2.7', 'C12-3.0', 'C12-3.5', 'C12-4.0', 'C12-4.5',
    'C12-5.0', 'C12-10',
    # C17 gewichtsbeperkingen (t)
    'C17-3.5', 'C17-5', 'C17-6', 'C17-7', 'C17-8', 'C17-10', 'C17-12',
    'C17-15', 'C17-20', 'C17-25', 'C17-30', 'C17-40', 'C17-50',
    # C18 breedtebeperkingen (m)
    'C18-1.8', 'C18-2.0', 'C18-2.2', 'C18-2.3', 'C18-2.4', 'C18-2.5',
    'C18-3.0', 'C18-3.5',
    # C19 aslastbeperkingen (t)
    'C19-3.0', 'C19-3.2', 'C19-3.3', 'C19-3.5', 'C19-3.8', 'C19-4.0', 'C19-5.0', 'C19-6.0',
    'C19-8.0', 'C19-10',
    # C20 rijwielbeperkingen (t)
    'C20-2.0', 'C20-2.5', 'C20-3.0', 'C20-3.5', 'C20-4.0', 'C20-4.2',
    'C20-4.8', 'C20-5.0', 'C20-6.0', 'C20-9',
    # C21 rijwiellastbeperkingen (t)
    'C21-3.5', 'C21-5', 'C21-40',
    # D-borden (rijrichting gebod) — basisvormen
    'D1', 'D2', 'D3', 'D4', 'D5', 'D5l', 'D5r', 'D6', 'D6l', 'D6r', 'D7',
    # D2 rotonde-varianten
    'D2-LO', 'D2-RO',
    # D5 / D6 richtingsvarianten (rvvCode=D5/D6, blackCode=L/R)
    'D5-L', 'D5-R',
    'D6-L', 'D6-R',
    # E-borden (parkeren / stoppen)
    'E1', 'E2', 'E3', 'E4', 'E5', 'E6', 'E7',
    'E8', 'E8a', 'E8b', 'E8c', 'E8d', 'E8e', 'E8f',
    'E8g', 'E8h', 'E8j', 'E8k', 'E8l', 'E8m', 'E8n',
    'E9', 'E10', 'E11', 'E12', 'E13', 'E14',
    # F-borden (rijstroken / inhaalverbod)
    'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11',
    'F12', 'F13', 'F14', 'F15', 'F16', 'F17', 'F18', 'F19', 'F20', 'F21',
    # G-borden (wegen / paden)
    'G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7', 'G8', 'G9', 'G10',
    'G11', 'G12', 'G12a', 'G13', 'G14',
    # H-borden (bebouwde kom)
    'H1', 'H2', 'H3', 'H4',
    # J-borden (gevaarswaarschuwing)
    'J1', 'J2', 'J3', 'J4', 'J5', 'J6', 'J7', 'J8', 'J9', 'J10',
    'J11', 'J12', 'J13', 'J14', 'J15', 'J16', 'J17', 'J18', 'J19', 'J20',
    'J21', 'J22', 'J23', 'J24', 'J25', 'J26', 'J27', 'J28', 'J29', 'J30',
    'J31', 'J32', 'J33', 'J34', 'J35', 'J36', 'J37', 'J38', 'J39', 'J40',
    'J41', 'J42', 'J43',
    # L-borden (informatie / zone)
    'L1', 'L1-4', 'L2', 'L3', 'L3b', 'L3c', 'L4', 'L5', 'L6', 'L7', 'L8', 'L9',
    'L10', 'L11', 'L12', 'L14', 'L51', 'L52',
    # OB-borden (onderborden)
    'OB501', 'OB502', 'OB503', 'OB504', 'OB54',
]

HEADERS = {'User-Agent': 'GMP-speeltuin/1.0'}


def download_one(code: str, out_dir: Path) -> tuple[str, str]:
    """Download één PNG; geeft (code, 'ok'|'404'|'err:<msg>') terug."""
    url  = BASE_URL.format(code=code)
    dest = out_dir / f'{code}.png'
    req  = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        dest.write_bytes(data)
        return code, 'ok'
    except urllib.error.HTTPError as exc:
        return code, '404' if exc.code == 404 else f'err:{exc.code}'
    except Exception as exc:
        return code, f'err:{exc}'


def main() -> None:
    out_dir = Path(__file__).parent / 'traffic_sign_icons'
    out_dir.mkdir(exist_ok=True)

    # Verwijder oude SVG-bestanden
    old_svgs = list(out_dir.glob('*.svg'))
    if old_svgs:
        for svg in old_svgs:
            svg.unlink()
        print(f'Verwijderd: {len(old_svgs)} oude SVG-bestanden\n')

    print(f'Downloaden van {len(CODES)} iconen van NDW …\n')

    ok_codes:  list[str] = []
    not_found: list[str] = []
    errors:    list[str] = []

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(download_one, code, out_dir): code for code in CODES}
        for fut in as_completed(futures):
            code, result = fut.result()
            if result == 'ok':
                ok_codes.append(code)
                print(f'  OK  {code}')
            elif result == '404':
                not_found.append(code)
            else:
                errors.append(f'{code}: {result}')
                print(f'  !!  {code}  ({result})')

    print(f'\n---------------------------------------------')
    print(f'Gedownload      : {len(ok_codes)} iconen')
    if not_found:
        print(f'Niet gevonden   : {", ".join(sorted(not_found))}')
        print(f'  → canvas-fallback per categorie actief voor deze codes')
    if errors:
        print(f'Fouten          : {", ".join(errors)}')
    print(f'Opgeslagen in   : {out_dir}')


if __name__ == '__main__':
    main()
