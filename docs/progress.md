De nieuwe versie van de gmt-lib heeft output in dit formaat. Gebruik het om de voortgang beter weer te geven in de GUI (analyser).

Het format: GMT-STAGE-regel

Elke stap-overgang in de pipeline logt precies één regel, pipe-gescheiden, altijd 9 velden:

GMT-STAGE|<process>|<stage>|<total>|<status>|<name>|<source>|<percent>|<elapsed_s>

┌───────────┬───────────────────────────────────────────────────────────────────────────────────────────────────┐
│   Veld    │                                             Betekenis                                             │
├───────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ process   │ prepare / osm_prepare / logistiek_prepare                                                         │
├───────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ stage     │ 1-based index van de huidige stap                                                                 │
├───────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ total     │ totaal aantal stappen van deze run                                                                │
├───────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ status    │ running | done | skipped | failed                                                                 │
├───────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ name      │ vaste stapnaam, bv. "Enrich with external assets"                                                 │
├───────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ source    │ aangeroepen bron (Databricks SQL, Overpass, PDOK BAG, ...), of -; bij skipped staat hier de reden │
├───────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ percent   │ 0–100, voortgang vóór de stap (running) of erna (done/skipped/failed)                             │
├───────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ elapsed_s │ duur in seconden, - bij running                                                                   │
└───────────┴───────────────────────────────────────────────────────────────────────────────────────────────────┘

Voorbeeld van een echte run:
GMT-STAGE|prepare|7|13|running|Enrich with external assets|Overpass / NDW / BGT|46|-
GMT-STAGE|prepare|7|13|done|Enrich with external assets|Overpass / NDW / BGT|54|41.2

Parser-kant is triviaal: zoek regels met "GMT-STAGE|" erin, split op |. Velden kunnen zelf nooit een | bevatten — StageTracker vervangt die defensief door /, dus het contract houdt altijd stand.

Dit zit nu in src/progress/__init__.py (StageTracker) en wordt gebruikt door alle drie de pipelines. De gewone detail-/telling-regels (bv. "245/312 links matched to OSM") blijven vrije tekst — alleen de proces/stap-overgangen volgen dit vaste stramien, en die komen ook 1-op-1 terecht in het message-veld van de job-status API.