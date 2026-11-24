# Energie

Bausteine für den Makrowolf: aus welchen Quellen Strom, Wärme und Verkehr in Deutschland und der EU versorgt werden, wie viel Leistung installiert ist und wie das vor Ort aussieht. Je Baustein ein Abrufskript, fertige Daten und eine Vorschau. Die Übernahme in den Monitor folgt je Baustein getrennt.

## Baustein 1: Energiewende vor Ort

Kreiskarte mit Wind und Sonne je Einwohner, Anteil der Elektroautos und öffentlichen Ladepunkten. Alle 400 Kreise, Gebietsstand 2024.

    pip install pandas numpy openpyxl
    python abruf/kreise.py --mastr <Pfad oder Adresse von mastr_kreis_jahr.csv>
    python -m http.server   # dann /vorschau/ im Browser öffnen

Ergebnisse in `daten/`:

| Datei | Inhalt |
|---|---|
| `kreise_energie.csv` | ags, nuts3, kennzahl, jahr, wert (Format wie die Kreisatlas-Dateien im Monitor) |
| `kreise_namen.csv` | ags, nuts3, Name nach Regionaldatenbank |
| `kreise_stand.json` | Stand je Quelle, Werte für Deutschland, Beschreibung der Kennzahlen |
| `kreise_karte.json` | vereinfachte Kreisflächen als SVG-Pfade |
| `gliederung_entwurf.yaml` | Entwurf des Abschnitts für die Gliederung des Monitors |

Kennzahlen:

| Kennzahl | Bedeutung | Stand |
|---|---|---|
| `wind_kw_ew` | Windkraft an Land, Bruttoleistung in kW je Einwohner | Ende 2025 |
| `sonne_kw_ew` | Photovoltaik, Bruttoleistung in kW je Einwohner | Ende 2025 |
| `wind_sonne_kw_ew` | beides zusammen | Ende 2025 |
| `eauto_anteil` | reine Elektroautos in % aller Pkw | 1.1.2026 |
| `plugin_anteil` | Plug-in-Hybride in % aller Pkw | 1.1.2026 |
| `ladepunkte_10t_ew` | öffentliche Ladepunkte in Betrieb je 10.000 Einwohner | 12.11.2026 |
| `eautos_je_ladepunkt` | reine Elektroautos je öffentlichem Ladepunkt | 1.1.2026 und 12.11.2026 |

Quellen:

| Quelle | Inhalt | Lizenz |
|---|---|---|
| Marktstammdatenregister (Bundesnetzagentur) | Einheiten mit Gemeindeschlüssel, je Kreis, Jahr und Energieträger summiert; Wind auf See hat keinen Gemeindeschlüssel und fehlt | Datenlizenz Deutschland 2.0 |
| Regionaldatenbank Deutschland, 12411-01-01-4 | Bevölkerung am 31.12. | Datenlizenz Deutschland 2.0 |
| Regionaldatenbank Deutschland, 46251-02-01-4 | Pkw nach Kraftstoffarten am 1.1. (Kraftfahrt-Bundesamt) | Datenlizenz Deutschland 2.0 |
| Ladesäulenregister (Bundesnetzagentur) | Ladeeinrichtungen mit abgeschlossener Anzeige, Status „In Betrieb“; Kreis über die Koordinaten | Lizenz auf der Seite nicht genannt, vor Übernahme klären |
| GISCO (Eurostat) | NUTS-3-Flächen 2024, Zuordnung Gemeinde zu NUTS 3 (LAU 2025) | © EuroGeographics, Nutzung nach GISCO-Bedingungen |

Prüfung: Deutschland Ende 2025 rund 68 GW Wind an Land und 118 GW Photovoltaik (brutto), 2,03 Mio. Elektroautos am 1.1.2026, 214.398 Ladepunkte in Betrieb. Bei 99,3 % der Ladeeinrichtungen passt die Fläche zum Kreisnamen im Register.

Die Regionaldatenbank verlangt ein Konto: `RDB_USER` und `RDB_PASS` oder das Netzwerk-Secret der Cloud-Umgebung.

Offen: Wärmepumpen im Bestand aus dem Zensus 2022 (Heizungsart je Gemeinde); die Zensus-Datenbank verlangt ein eigenes Konto.
