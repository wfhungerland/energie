"""Erneuerbaren-Anteile in der EU: insgesamt, Strom, Wärme und Kälte, Verkehr (Eurostat SHARES).

Quelle: Eurostat, Datensatz nrg_ind_ren (Share of energy from renewable sources), Abruf über die
Statistik-API. Lizenz CC BY 4.0. Anteile nach den Rechenregeln der Erneuerbare-Energien-Richtlinie:
am Bruttoendenergieverbrauch; im Verkehr mit Mehrfachanrechnung etwa für Strom aus erneuerbaren
Quellen und fortschrittliche Biokraftstoffe, daher höher als der physische Anteil.

Aufruf: python abruf/eu_anteile.py
Ergebnis: daten/eu_erneuerbare.csv (geo, land, sektor, jahr, wert, status), daten/eu_erneuerbare_stand.json
"""
import csv
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATEN = ROOT / "daten"
API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_ind_ren?format=JSON&lang=de&sinceTimePeriod=2004"
SEKTOREN = {"REN": "insgesamt", "REN_ELC": "strom", "REN_HEAT_CL": "waerme", "REN_TRA": "verkehr"}
EU27 = ["BE", "BG", "CZ", "DK", "DE", "EE", "IE", "EL", "ES", "FR", "HR", "IT", "CY", "LV", "LT", "LU",
        "HU", "MT", "NL", "AT", "PL", "PT", "RO", "SI", "SK", "FI", "SE"]
NAMEN = {"EU27_2020": "EU", "EL": "Griechenland", "CZ": "Tschechien"}   # sonst Eurostat-Bezeichnung auf Deutsch


def main():
    req = urllib.request.Request(API, headers={"User-Agent": "Mozilla/5.0 (energie-abruf)"})
    j = json.loads(urllib.request.urlopen(req, timeout=300).read())
    ids, size, dim = j["id"], j["size"], j["dimension"]
    cats = {k: list(dim[k]["category"]["index"].keys()) for k in ids}
    labels = dim["geo"]["category"]["label"]
    status = j.get("status", {})
    zeilen = []
    for idx, v in j["value"].items():
        i, pos = int(idx), []
        for s in reversed(size):
            pos.append(i % s)
            i //= s
        r = {k: cats[k][p] for k, p in zip(ids, reversed(pos))}
        if r["nrg_bal"] not in SEKTOREN or r["geo"] not in EU27 + ["EU27_2020"]:
            continue
        zeilen.append([r["geo"], NAMEN.get(r["geo"], labels[r["geo"]]), SEKTOREN[r["nrg_bal"]], int(r["time"]), v, status.get(idx, "")])
    zeilen.sort(key=lambda z: (z[0] != "EU27_2020", z[1], z[2], z[3]))
    DATEN.mkdir(exist_ok=True)
    with (DATEN / "eu_erneuerbare.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["geo", "land", "sektor", "jahr", "wert", "status"])
        w.writerows(zeilen)
    # jüngstes Jahr, in dem alle 27 Länder und die EU alle vier Sektoren haben
    voll = max(t for t in {z[3] for z in zeilen}
               if all(sum(1 for z in zeilen if z[2] == s and z[3] == t) == 28 for s in SEKTOREN.values()))
    neu = max(z[3] for z in zeilen)
    stand = {"aktualisiert": j["updated"][:10], "jahr_voll": voll, "jahr_neu": neu,
             "neu_sektoren": sorted({z[2] for z in zeilen if z[3] == neu}),
             "status": {"p": "vorläufig", "e": "geschätzt", "b": "Bruch in der Reihe"}}
    (DATEN / "eu_erneuerbare_stand.json").write_text(json.dumps(stand, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(zeilen)} Werte, vollständig bis {voll}, jüngstes Jahr {neu} ({', '.join(stand['neu_sektoren'])})")
    for s in SEKTOREN.values():
        de = next(z[4] for z in zeilen if z[0] == "DE" and z[2] == s and z[3] == voll)
        eu = next(z[4] for z in zeilen if z[0] == "EU27_2020" and z[2] == s and z[3] == voll)
        rang = sorted((z[4] for z in zeilen if z[0] in EU27 and z[2] == s and z[3] == voll), reverse=True).index(de) + 1
        print(f"  {s} {voll}: Deutschland {de} %, EU {eu} %, Rang {rang} von 27")


if __name__ == "__main__":
    main()
