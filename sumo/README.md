## Install sumo:

```sh
winget install --name sumo
```

## Gebruik:
```sh
python ./sumo/export_to_sumo.py --area-dir work/Hasselt --output-dir output/sumo/Hasselt --daypart mrh
python ./sumo/export_to_sumo.py --area-dir work/Vreden  --output-dir output/sumo/Vreden  --daypart erh
```

## Gegenereerde bestanden:

nodes.nod.xml
edges.edg.xml
routes.rou.xml
flows_observed.xml
sumo.cfg
README.txt

## Opties:
- --daypart mrh/erh/rest — selecteer dagdeel (flows worden omgezet naar veh/h)
- --include-feedlinks — voedingslinks (zone-connectors) meenemen
- --min-flow 0.1 — ondergrens voor routes in veh/h
- --no-observed-flows — geen flows_observed.xml

## Daarna (in een aparte cmd):
netconvert --node-files nodes.nod.xml --edge-files edges.edg.xml --output-file network.net.xml --no-internal-links --proj.utm
sumo-gui -c sumo.cfg