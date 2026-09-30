# Lokale FusionAuth voor de GMT-apps

Deze map start één FusionAuth met een `GMT`-applicatie erin, gedeeld door de
speeltuin (`:5000`) en de gmt-planner (`:5100`). Zolang de `GMT_AUTH_*`-regels in
`speeltuin/.env` staan gebruiken beide apps hem; haal je ze weg, dan draaien de
apps weer volledig zonder inloggen.

## Starten

```bash
docker compose -f dev/docker-compose.yml up -d     # eerste keer ~60 s
docker compose -f dev/docker-compose.yml down      # stoppen, gegevens bewaren
docker compose -f dev/docker-compose.yml down -v   # ook wissen
```

**Kickstart draait alleen op een lege database.** Wijzig je `kickstart-gmt.json`,
dan is `down -v` gevolgd door `up -d` de enige manier om die wijziging te zien.
Handmatige aanpassingen in de admin-UI gaan daarbij dus ook verloren.

## Accounts

| Waar | Gebruiker | Wachtwoord | Rollen |
|---|---|---|---|
| FusionAuth-beheer, http://localhost:9011/admin | `admin@gmt.local` | `GmtAdmin#1` | FusionAuth `admin` |
| GMT-apps | `evdbelt@dat.nl` | `GmtLokaal#1` | `viewer`, `editor`, `admin` |
| GMT-apps (rolcontroles testen) | `test@dat.nl` | `TestPass#1` | alleen `viewer` |

Wachtwoordregels van de tenant: minimaal 8 tekens, hoofd- én kleine letters, een
cijfer en een leesteken.

## Wat er in de kickstart staat

- **Tenant `GMT`** — issuer `localhost:9011`, access token 1 uur, refresh token 10 uur
  (sliding window, **herbruikbaar** — one-time-use zou stuklopen op parallelle
  verzoeken van de browser tegen een `threaded=True` server).
- **Applicatie `GMT`** — alleen `authorization_code` + `refresh_token`, PKCE
  verplicht, consent uit (`NeverPrompt`, first-party), redirect-URI's voor beide
  poorten, rollen `viewer` (standaard) / `editor` / `admin`.
- **Lambda `GMT populate JWT`** — hangt aan zowel het access- als het id-token en
  kopieert de registratierollen naar de claim `roles`, plus `email` en `name`.
  Zonder deze lambda zitten er géén rollen in het id_token.

## Twee dingen om te weten

**De `iss`-claim is `localhost:9011`, zonder schema.** De tenant-issuer is een naam,
geen URL — net als in de OTN-kickstart. De basis-URL voor de endpoints
(`GMT_AUTH_ISSUER=http://localhost:9011`) is dus iets anders dan de waarde waarmee
je de `iss`-claim vergelijkt (`GMT_AUTH_EXPECTED_ISS=localhost:9011`). Op
productie zijn ze wél gelijk (`https://sso.dat.nl`).

**`localhost` en `127.0.0.1` zijn voor FusionAuth twee verschillende hosts.**
De apps leiden hun `redirect_uri` af uit de host in de adresbalk, dus beide
varianten staan als Authorized Redirect URL geregistreerd. Open je de app op een
derde adres (je machinenaam, een LAN-IP), dan krijg je
`invalid_redirect_uri` — voeg dat adres dan toe aan de applicatie, of zet
`GMT_AUTH_REDIRECT_URI` vast. Let op dat de sessiecookie per host geldt: wissel je
halverwege van `localhost` naar `127.0.0.1`, dan moet je opnieuw inloggen.

**De discovery op de hoofd-URL hoort bij de standaardtenant** en geeft
`issuer: acme.com`. De onze staat op
`/.well-known/openid-configuration/11111111-1111-1111-1111-111111111111`.
De JWKS-URL is voor beide dezelfde.

## Controleren of alles klopt

```bash
curl -s localhost:9011/.well-known/openid-configuration/11111111-1111-1111-1111-111111111111
```

Voor een volledige code-flow zonder browser staat er een testscript in
`dev/flowtest.py`: het logt in als `evdbelt@dat.nl`, wisselt de code in en laat
zien welke rollen in het id_token belanden.

```bash
python dev/flowtest.py
```
