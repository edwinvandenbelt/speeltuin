# GMT Digital Twin — Docker image
# Bouw vanaf de repo-root (build context = repo-root), zodat de gedeelde
# common/-map en de wheel-bestanden op repo-niveau meekomen:
#   docker build -f digital-twin/Dockerfile -t gmt-digital-twin .
#
# Let op: de fysieke maquette (camera, kalibratie) gebruikt Windows-specifieke
# API's en een camera-device, en draait in de praktijk lokaal op Windows, niet
# in deze container. Dit image is vooral bruikbaar voor de live 3D-weergave
# zonder maquette-hardware (bv. CI/tests) — zie digital-twin/README.md.
#
# De work/-map (verwerkte gebieden) wordt als volume gemount zodat data
# buiten de container bewaard blijft en herstarts zonder dataverlies zijn.

FROM python:3.12-slim

WORKDIR /app

# ── Python-afhankelijkheden ───────────────────────────────────────────────────
# Wheels staan op repo-niveau; kopieer ze rechtstreeks in digital-twin/, zodat
# requirements.txt (zonder ../) ze naast zichzelf vindt — net als bij de
# platgeslagen deploy-zip (zie digital-twin/deploy.ps1).
COPY *.whl digital-twin/
COPY digital-twin/requirements.txt digital-twin/requirements.txt
RUN pip install --no-cache-dir -r digital-twin/requirements.txt

# ── Gedeelde code (common/) en digital-twin-specifieke applicatiebestanden ───
COPY common/ common/
COPY digital-twin/ digital-twin/

# ── work/-map aanmaken (wordt bij `docker run` overschreven door volume-mount) ─
RUN mkdir -p /app/digital-twin/work

EXPOSE 5001
WORKDIR /app/digital-twin

CMD ["python", "server.py", "--port", "5001"]
