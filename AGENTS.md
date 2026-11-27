# Werkafspraken voor agents in deze repo

## Always

- Gebruik `127.0.0.1` in plaats van `localhost` voor elke lokale server-URL (in testscripts, en waar code een lokale server-URL opbouwt). Op deze machine kost DNS-resolutie van `localhost` ~2s per call, `127.0.0.1` ~0,04s.
- Los dataproblemen bij voorkeur op in de serve-laag (filteren/clippen bij het uitlezen) in plaats van brondata aan te passen of te verwijderen.
- Schrijf grotere plannen weg als `plan-<onderwerp>.md` in de repo-root, met een checkbox per stap. Voer stap voor stap uit en stop na elke stap voor test/akkoord van de gebruiker.
- Reproduceer rendering-bugs in digital-twin zelf via headless Chrome + CDP (`chrome --headless=new --remote-debugging-port=... --user-data-dir=<scratchpad> --enable-unsafe-swiftshader`) tegen de draaiende server, in plaats van de gebruiker veel console-rondes te laten doen. Dit geldt voor het diagnosticeren van een gemelde bug — niet voor verificatie achteraf (zie Never).
- Windows-first: gebruik `pathlib`, geen POSIX-only calls; houd rekening met backslashes en drive-letter casing.
- Geef subagents een expliciete scope: welke files ze mogen aanraken, dat ze niet zelf committen, geen processen op naam mogen killen, en dat servers die ze starten zichzelf stoppen (timeout + cleanup in `finally`).
- Rapporteer resultaten/getallen altijd met hun scope erbij (welk gebied/scenario, welke dataset, welke aannames) — geen kale cijfers.
- Draai taken die meerdere subagents parallel uitvoeren alleen op disjuncte bestanden; bij overlap in één bestand de wijzigingen na elkaar verwerken.
- Draai processen in `analyzer/Dockerfile` en `digital-twin/Dockerfile` als non-root user (expliciete `USER`-regel met een niet-root UID) in plaats van de image-default root.
- Pin het basisimage (`python:3.12-slim`) op een digest (`@sha256:...`) in plaats van alleen de tag, zodat een upstream-update van de tag niet ongemerkt een andere image binnenhaalt.
- Houd `.dockerignore` in sync met `.gitignore` voor alles dat secrets/credentials kan bevatten (`.env`, `.gmt-env`, …), zodat die nooit in een image-laag terechtkomen.

## Ask first

- Voordat een geprepareerd `work/`-bestand (bv. `{areaId}-*.parquet`, scenario-mappen) verwijderd wordt als "fix" — eerst nagaan hoe het geregenereerd wordt. Lukt dat niet, verplaats het bestand opzij (hernoemen) in plaats van te verwijderen, en vraag het na.
- Voordat je na het opleveren van een feature/fix zelf nog headless-Chrome-screenshots gaat maken ter controle — de gebruiker checkt het resultaat liever zelf in de browser. Vraag het alleen als er een concrete reden is om het toch zelf te willen zien.
- Voordat je `server.py` (digital-twin of elders) start tegen een map die ongeprepareerde of gedeelde data bevat, als er twijfel is of het script die map muteert.
- Voordat je een multi-stage build of `HEALTHCHECK` toevoegt aan een bestaand Dockerfile — functioneel verschil met de huidige deploy-flow (`deploy.ps1`) eerst checken.

## Never

- Start `server.py` nooit "even om te testen" tegen de échte `work/`-map. `_cleanup_work_dir()` draait automatisch bij opstarten en kan met `shutil.rmtree` scenario-mappen stilletjes wissen zodra de venv een optionele dependency (bv. `geopandas`) mist waardoor de parquet-detectie wordt overgeslagen. Wijs altijd een expliciete lege/aparte `--data`-map (of `DATA_DIR`) aan, en controleer vooraf of de venv alle deps heeft die `_cleanup_work_dir()`/`_work_dir_has_network_file()` nodig hebben.
- Spawn niet proactief een headless-Chrome-sessie om een zojuist afgeronde feature/fix zelf te verifiëren — dat is aan de gebruiker, tenzij expliciet gevraagd.
- Verwijder geen geprepareerde data (parquet, scenario-mappen in `work/`) zonder eerst te verifiëren hoe die opnieuw te genereren zijn.
