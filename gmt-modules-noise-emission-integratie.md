# Integratie: noise_estimator & emission_estimator (gmt_calculation_lib)

Twee nieuwe standalone rekenmodules in `gmt_calculation_lib` (>= 0.2.0):

| Module | Doel | Output (per link) |
|---|---|---|
| `noise_estimator` | Wegverkeersgeluid (emissie/bronvermogen) | `noiseDay/Evening/Night`, `noiseLden`, `noiseLnight`, `noiseSourceType` (dB(A)) |
| `emission_estimator` | Luchtverontreiniging (CO2/NOx/PM10/PM2.5) | `co2Kg`, `noxKg`, `pm10Kg`, `pm25Kg`, `vehicleKm` (kg/etmaal) |

Beide kernen zijn **puur `fc -> fc`** (GeoJSON `FeatureCollection` in, verrijkte
`FeatureCollection` uit). Geen I/O, geen boto3, geen netwerkcalls. Bedoeld om
**on-the-fly** in de server aangeroepen te worden - snel genoeg voor realtime.

De server (speeltuin) doet de API-afhandeling en roept de kern **rechtstreeks**
aan; er is geen aparte Lambda/dispatcher in de lib (net als `buildings_fetcher`).

---

## 1. Verwachte invoer

De links moeten de prepare-flowschema-velden dragen (aanwezig op de
`NETWORK-{mode}.parquet` output van prepare):

- `flow24hrs` - voertuigen/etmaal (beide modules)
- `length` - lengte in meter (emission)
- `speed` - km/h (noise; emission stage 2)
- `flowsPerDaypart` - `{mrh, erh, rest}` uurintensiteiten (emission stage 2)

Ontbrekende velden -> die link krijgt 0 / `None` (geen crash).

---

## 2. Import (zoals de bestaande modules in server.py)

```python
try:
    from noise_estimator.core.noise_estimator_core import estimate_noise_emission
    _NOISE_AVAILABLE = True
except ImportError as _e:
    estimate_noise_emission = None  # type: ignore[assignment]
    _NOISE_AVAILABLE = False
    print(f"[server] WAARSCHUWING: noise_estimator niet beschikbaar - {_e}")

try:
    from emission_estimator.core.emission_estimator_core import (
        estimate_emissions,
        estimate_emissions_detailed,
    )
    _EMISSION_AVAILABLE = True
except ImportError as _e:
    estimate_emissions = estimate_emissions_detailed = None  # type: ignore[assignment]
    _EMISSION_AVAILABLE = False
    print(f"[server] WAARSCHUWING: emission_estimator niet beschikbaar - {_e}")
```

---

## 3. Aanroepen

Beide nemen een GeoJSON `FeatureCollection` (dict) en geven een **nieuwe**
verrijkte `FeatureCollection` terug (geometrie + bestaande properties blijven
behouden, de nieuwe velden worden toegevoegd).

### Geluid

```python
noise_fc = estimate_noise_emission(network_fc)
# elke feature heeft nu: noiseDay, noiseEvening, noiseNight,
#                        noiseLden, noiseLnight, noiseSourceType
```

### Emissie - 2-traps raket

```python
# Trap 1: snel (default) - emissiefactor * voertuigkm
emis_fc = estimate_emissions(network_fc)
# per link: co2Kg, noxKg, pm10Kg, pm25Kg, vehicleKm

# Trap 2: uitgebreid (mag trager) - snelheidsafhankelijke factoren,
#         licht/zwaar-mix, koudestart/hellinghooks, dagdeelsplitsing
emis_fc = estimate_emissions_detailed(network_fc)
# per link: bovenstaande totalen + per dagdeel, bv.
#           co2KgMrh / co2KgErh / co2KgRest (idem voor nox/pm10/pm25)
```

Gebruik voor de viewer standaard **trap 1** (snel). Trap 2 alleen wanneer je de
dagdeel-uitsplitsing of de verfijnde factoren nodig hebt.

---

## 4. Uit een netwerk-parquet inlezen (indien nodig)

Heb je nog geen FC in het geheugen maar wel een parquet-URI, gebruik de
gedeelde helper:

```python
from shared.geoparquet import from_geoparquet
network_fc = from_geoparquet(raw_bytes)   # raw_bytes = inhoud van NETWORK-{mode}.parquet
```

De kernen hoeven nooit zelf iets weg te schrijven; dat is optioneel en alleen
in de runner/notebook geregeld.

---

## 5. Calibratie via environment (optioneel)

Beide modules lezen coefficienten uit de omgeving (met plausibele defaults):

- Geluid: `NOISE_EMISSION_C0/CV/VREF/CSURFACE/CHEAVY`, `NOISE_MIN_FLOW`
- Emissie: `EMISSION_FACTOR_CO2/NOX/PM10/PM25` (en `_HEAVY` varianten),
  `EMISSION_HEAVY_FRACTION`, `EMISSION_SPEED_REF`, `EMISSION_SPEED_SENSITIVITY`,
  `EMISSION_COLD_START_FACTOR`, `EMISSION_GRADIENT_FACTOR`

Niet zetten = defaults. De waarden zijn indicatief (geen officiele
Emissieregistratie-cijfers) en bedoeld om te tunen.

---

## 6. Samengevat

- Installeer de nieuwe wheel (`gmt_calculation_lib-<versie>-py3-none-any.whl`).
- Importeer de core-functies met dezelfde try/except-guard als de andere modules.
- Roep `estimate_noise_emission(fc)` en/of `estimate_emissions(fc)` aan op een
  netwerk-FC met flowvelden; gebruik de verrijkte FC in de response/viewer.
