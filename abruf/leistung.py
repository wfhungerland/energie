"""Installierte Kraftwerksleistung nach Energieträger: Deutschland seit 1990 und die EU-Staaten.

Quellen:
- Eurostat, nrg_inf_epc (Electricity production capacities), maximale elektrische Nettoleistung in MW,
  alle Betreiber, Lizenz CC BY 4.0. Jahresende, bis zum jüngsten Berichtsjahr.
- Eurostat, demo_pjan (Bevölkerung am 1.1.), für die Leistung je Einwohner im Ländervergleich.
- Marktstammdatenregister (Bundesnetzagentur, DL-DE-BY 2.0) über mastr_kreis_jahr.csv (siehe
  abruf/kreise.py): Bruttoleistung von Wind an Land und Photovoltaik für Jahre nach dem jüngsten
  Eurostat-Jahr, als jüngster Stand für Deutschland. Brutto liegt etwas über netto. Wind auf See fehlt
  dort und wird mit dem Stand des jüngsten Eurostat-Jahres ergänzt.

Aufruf: python abruf/leistung.py [--mastr PFAD_ODER_URL]
Ergebnis: daten/leistung.csv (geo, land, traeger, jahr, gw, quelle; quelle mastr = Bruttoleistung), daten/leistung_stand.json
"""
import argparse
import csv
import json
import os
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATEN = ROOT / "daten"
API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
EU27 = ["BE", "BG", "CZ", "DK", "DE", "EE", "IE", "EL", "ES", "FR", "HR", "IT", "CY", "LV", "LT", "LU",
        "HU", "MT", "NL", "AT", "PL", "PT", "RO", "SI", "SK", "FI", "SE"]
NAMEN = {"EU27_2020": "EU", "EL": "Griechenland", "CZ": "Tschechien"}
TRAEGER = {  # Eurostat-Code -> Gruppe. Gröber als möglich, weil für Deutschland 2005 bis 2017 Kohle, Gas,
    # Öl und Biomasse einzeln fehlen und Wind erst ab 2022 nach Land und See getrennt vorliegt.
    "CF": "brennstoffe", "N9000": "kern", "RA300": "wind", "RA420": "sonne",
    "RA110": "wasser", "RA120": "wasser", "RA200": "wasser", "RA500": "wasser",
}
MASTR = {"Wind": "wind", "Solare Strahlungsenergie": "sonne"}   # Wind nur an Land


def eurostat(ds, params):
    url = API + ds + "?format=JSON&lang=de&" + "&".join(f"{k}={v}" for k, vs in params.items() for v in (vs if isinstance(vs, list) else [vs]))
    j = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (energie-abruf)"}), timeout=600).read())
    ids, size, dim = j["id"], j["size"], j["dimension"]
    cats = {k: list(dim[k]["category"]["index"].keys()) for k in ids}
    out = []
    for idx, v in j["value"].items():
        i, pos = int(idx), []
        for s in reversed(size):
            pos.append(i % s)
            i //= s
        out.append({**{k: cats[k][p] for k, p in zip(ids, reversed(pos))}, "wert": v})
    return pd.DataFrame(out), dim["geo"]["category"]["label"], j["updated"][:10]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mastr", default=os.environ.get("MASTR_KREIS_JAHR"))
    a = ap.parse_args()
    geos = EU27 + ["EU27_2020"]
    d, labels, stand = eurostat("nrg_inf_epc", {"geo": geos, "plant_tec": "CAP_NET_ELC", "operator": "TOTAL",
                                                "siec": ["TOTAL", "RA320", *TRAEGER]})
    d["jahr"] = d.time.astype(int)
    tot = d[d.siec == "TOTAL"].set_index(["geo", "jahr"]).wert
    see = d[(d.siec == "RA320") & (d.geo == "DE")].set_index("jahr").wert   # Wind auf See, für die MaStR-Fortschreibung
    d = d[~d.siec.isin(["TOTAL", "RA320"])].assign(traeger=lambda x: x.siec.map(TRAEGER))
    g = d.groupby(["geo", "traeger", "jahr"]).wert.sum().reset_index()
    # Prüfung: Summe der Gruppen gegen Gesamtleistung (Pumpspeicher fehlen bewusst; DE 2021 ist die Gesamtzahl bei Eurostat lückenhaft)
    summe = g.groupby(["geo", "jahr"]).wert.sum()
    abw = ((summe - tot.reindex(summe.index)) / tot.reindex(summe.index)).abs()
    jung = int(g.jahr.max())
    print(f"Eurostat {stand}: {g.geo.nunique()} Gebiete, {g.jahr.min()} bis {jung}; "
          f"Abweichung zur Gesamtleistung ohne Pumpspeicher im Mittel {abw.xs(jung, level='jahr').median():.1%}")
    g["quelle"] = "eurostat"
    zeilen = g.rename(columns={"wert": "mw"})

    if a.mastr:
        m = pd.read_csv(a.mastr, dtype={"kreis": str})
        m = m[(m.jahr > jung) & m.energietraeger.isin(MASTR)]
        # nur abgeschlossene Jahre: das laufende Jahr fehlt, solange der Export aus ihm stammt
        m = m[m.jahr < pd.Timestamp.today().year]
        mm = m.groupby(["energietraeger", "jahr"]).brutto_mw.sum().reset_index()
        mm = pd.DataFrame({"geo": "DE", "traeger": mm.energietraeger.map(MASTR), "jahr": mm.jahr, "mw": mm.brutto_mw, "quelle": "mastr"})
        # Wind auf See fehlt im MaStR-Auszug (kein Gemeindeschlüssel): Stand des jüngsten Eurostat-Jahres dazu
        mm.loc[mm.traeger == "wind", "mw"] += see.get(jung, 0)
        zeilen = pd.concat([zeilen, mm])
        print("MaStR ergänzt:", ", ".join(f"{r.traeger} {r.jahr} {r.mw / 1000:.1f} GW" for r in mm.itertuples()))

    bev, _, _ = eurostat("demo_pjan", {"geo": geos, "sex": "T", "age": "TOTAL", "sinceTimePeriod": str(jung - 1)})
    bev = bev.assign(jahr=bev.time.astype(int)).set_index(["geo", "jahr"]).wert
    DATEN.mkdir(exist_ok=True)
    with (DATEN / "leistung.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["geo", "land", "traeger", "jahr", "gw", "quelle"])
        for r in zeilen.sort_values(["geo", "traeger", "jahr"]).itertuples():
            if r.mw:
                w.writerow([r.geo, NAMEN.get(r.geo, labels.get(r.geo, r.geo)), r.traeger, r.jahr, round(r.mw / 1000, 3), r.quelle])
    # Einwohner am 1.1. des Folgejahres = Jahresende
    ew = {geo: int(bev[(geo, jung + 1)]) if (geo, jung + 1) in bev.index else int(bev[(geo, jung)]) for geo in geos}
    out = {"aktualisiert": stand, "jahr": jung, "wind_see_gw": round(see.get(jung, 0) / 1000, 1), "einwohner_jahresende": ew,
           "namen": {"brennstoffe": "Kohle, Gas, Öl, Biomasse", "kern": "Kernkraft", "wind": "Wind",
                     "sonne": "Photovoltaik", "wasser": "Wasser und Sonstige"}}
    (DATEN / "leistung_stand.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    de = zeilen[(zeilen.geo == "DE") & (zeilen.jahr == jung)].set_index("traeger").mw / 1000
    print(f"Deutschland {jung}: " + ", ".join(f"{k} {v:.1f}" for k, v in de.sort_values(ascending=False).items()) + f"; zusammen {de.sum():.0f} GW")


if __name__ == "__main__":
    main()
