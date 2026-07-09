# GMT Speeltuin — Docker image
# Gebruik: zie startDocker.bat
#
# De work/-map (verwerkte gebieden) wordt als volume gemount zodat data
# buiten de container bewaard blijft en herstarts zonder dataverlies zijn.

FROM python:3.12-slim

WORKDIR /app

# ── Python-afhankelijkheden ───────────────────────────────────────────────────
# Wheels eerst zodat requirements.txt ze lokaal kan vinden (./gmt_calculation_lib-*.whl)
COPY *.whl ./
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ── Applicatiebestanden ───────────────────────────────────────────────────────
COPY server.py index.html download_traffic_sign_icons.py ./
COPY daylight.json holiday_indices.csv purpose_index.json ndw_traffic_signs.json ./
COPY traffic_sign_icons/    traffic_sign_icons/
COPY buildings_fetcher/     buildings_fetcher/
COPY traffic_signs_fetcher/ traffic_signs_fetcher/

# ── work/-map aanmaken (wordt bij `docker run` overschreven door volume-mount) ─
RUN mkdir -p /app/work

EXPOSE 5000

CMD ["python", "server.py"]
