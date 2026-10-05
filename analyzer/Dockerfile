# GMT Analyzer — Docker image
# Bouw vanaf de repo-root (build context = repo-root), zodat de gedeelde
# common/-map en de wheel-bestanden op repo-niveau meekomen:
#   docker build -f analyzer/Dockerfile -t gmt-analyzer .
#
# De work/-map (verwerkte gebieden) wordt als volume gemount zodat data
# buiten de container bewaard blijft en herstarts zonder dataverlies zijn.

FROM python:3.12-slim

WORKDIR /app

# ── Python-afhankelijkheden ───────────────────────────────────────────────────
# Wheels op repo-niveau eerst, zodat analyzer/requirements.txt ze via ../ vindt.
COPY *.whl ./
COPY analyzer/requirements.txt analyzer/requirements.txt
RUN pip install --no-cache-dir -r analyzer/requirements.txt

# ── Gedeelde code (common/) en analyzer-specifieke applicatiebestanden ───────
COPY common/ common/
COPY analyzer/ analyzer/

# ── work/-map aanmaken (wordt bij `docker run` overschreven door volume-mount) ─
RUN mkdir -p /app/analyzer/work

EXPOSE 5000
WORKDIR /app/analyzer

CMD ["python", "server.py"]
