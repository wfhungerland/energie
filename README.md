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

Offen (Baustein 1): Wärmepumpen im Bestand aus dem Zensus 2022 (Heizungsart je Gemeinde); die Zensus-Datenbank verlangt ein eigenes Konto.

## Baustein 2: Erneuerbare in der EU

Anteile der Erneuerbaren insgesamt, im Strom, in Wärme und Kälte und im Verkehr je EU-Land, dazu der Verlauf für Deutschland und die EU seit 2004.

    python abruf/eu_anteile.py   # dann /vorschau/eu.html

Ergebnisse: `daten/eu_erneuerbare.csv` (geo, land, sektor, jahr, wert, status; status p = vorläufig) und `daten/eu_erneuerbare_stand.json`.

Quelle: Eurostat, SHARES (`nrg_ind_ren`), Lizenz CC BY 4.0. Anteil am Bruttoendenergieverbrauch nach den Regeln der Erneuerbare-Energien-Richtlinie; im Verkehr mit Mehrfachanrechnung. Alle vier Sektoren liegen für alle 27 Länder bis 2024 vor; für 2025 gibt es vorläufige Werte nur insgesamt und für Strom (und für einzelne Länder bei Wärme).

Prüfung 2024: Deutschland insgesamt 22,5 % (Platz 16 von 27, EU 25,2 %), Strom 54,1 % (Platz 9, EU 47,5 %), Wärme und Kälte 17,7 % (Platz 24, EU 26,7 %), Verkehr 12,4 % (Platz 8, EU 11,2 %).

Ort im Monitor: Teil Wachstum, Kapitel Welt, mit Verweis aus dem Teil Energie.

## Baustein 3: Endenergie in Deutschland

Energetischer Endenergieverbrauch nach Sektor (Industrie, Verkehr, Haushalte, Gewerbe/Handel/Dienstleistungen, Land- und Forstwirtschaft und Sonstige) und Quelle (Öl, Erdgas, Kohle, Strom, Fernwärme, Erneuerbare direkt, Abfall und Sonstige), 1990 bis 2024. Als Sankey-Ersatz: oben ein Balken je Sektor mit den Quellen, unten der Verlauf als gestapelte Fläche.

    python abruf/endenergie.py   # dann /vorschau/endenergie.html

Ergebnisse: `daten/endenergie_de.csv` (jahr, sektor, quelle, twh) und `daten/endenergie_stand.json`.

Quelle: Eurostat, Energiebilanzen (`nrg_bal_c`), Deutschland, GWh, Lizenz CC BY 4.0. Das Skript prüft je Jahr, dass die Teile den Gesamtwert ergeben. Strom und Fernwärme sind eigene Quellen; ihre Erzeugung zeigt dieses Bild nicht. Eurostat grenzt teils anders ab als die AG Energiebilanzen (deren Seite ist aus der Cloud nicht erreichbar).

Prüfung 2024: 2.067 TWh (1990: 2.543 TWh). Industrie 563 TWh (Strom und Erdgas je 35 %), Verkehr 576 TWh (Öl 90 %), Haushalte 610 TWh (Erdgas 37 %, Strom 22 %, Öl 19 %, Erneuerbare direkt 16 %), Gewerbe 277 TWh (Strom 44 %).

Ort im Monitor: Teil Energie, neues Kapitel „Quellen“, mit Verweis auf „Leben vor Ort › Energie“ und auf den EU-Vergleich.

## Baustein 4: Installierte Leistung

Deutschland: Kraftwerksleistung nach Energieträger seit 1990, fortgeschrieben mit dem Marktstammdatenregister. EU: Wind und Photovoltaik in kW je Einwohner je Land.

    python abruf/leistung.py --mastr <Pfad oder Adresse von mastr_kreis_jahr.csv>   # dann /vorschau/leistung.html

Ergebnisse: `daten/leistung.csv` (geo, land, traeger, jahr, gw, quelle) und `daten/leistung_stand.json` (Einwohner am Jahresende, Namen).

Quellen: Eurostat `nrg_inf_epc` (maximale elektrische Nettoleistung, alle Betreiber) und `demo_pjan` (Bevölkerung am 1.1. des Folgejahres), CC BY 4.0; Marktstammdatenregister (Bruttoleistung, DL-DE-BY 2.0) für Jahre nach dem jüngsten Eurostat-Jahr.

Grenzen: Für Deutschland fehlen bei Eurostat 2005 bis 2017 Kohle, Gas, Öl und Biomasse einzeln und Wind bis 2021 nach Land und See; die Gruppen sind deshalb grob (Kohle, Gas, Öl, Biomasse zusammen; Wind zusammen). Pumpspeicher fehlen. Eurostat führt für 2023 noch 4,2 GW Kernkraft, obwohl die letzten Kernkraftwerke am 15.4.2023 vom Netz gingen. Die MaStR-Fortschreibung zählt Wind auf See mit dem Eurostat-Stand des Vorjahres. ENTSO-E ist aus der Cloud nicht erreichbar und wurde nicht genutzt.

Prüfung: Deutschland Ende 2024 91,2 GW Photovoltaik, 72,7 GW Wind (davon 9,2 GW auf See), 90,2 GW Kohle, Gas, Öl und Biomasse; Wind und Photovoltaik 1,96 kW je Einwohner, Platz 3 der EU hinter Schweden und den Niederlanden (EU 1,19 kW).

Ort im Monitor: Teil Energie, Kapitel „Quellen“, neben der Endenergie; der EU-Vergleich mit Verweis nach Wachstum › Welt.
