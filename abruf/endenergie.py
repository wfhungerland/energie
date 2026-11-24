"""Endenergie in Deutschland nach Quelle und Sektor (Eurostat-Energiebilanz).

Quelle: Eurostat, Datensatz nrg_bal_c (Complete energy balances), Deutschland, Einheit GWh,
Abruf über die Statistik-API, Lizenz CC BY 4.0. Gezeigt ist der energetische Endenergieverbrauch
(FC_E) ohne nicht energetischen Verbrauch (etwa Rohbenzin für die Chemie). Strom und Fernwärme sind
Endenergie; aus welchen Quellen sie erzeugt werden, zeigt die Bilanz an anderer Stelle.

Aufruf: python abruf/endenergie.py
Ergebnis: daten/endenergie_de.csv (jahr, sektor, quelle, twh), daten/endenergie_stand.json
"""
import csv
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATEN = ROOT / "daten"
API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_bal_c?format=JSON&lang=de&geo=DE&unit=GWH"

SEKTOREN = {  # Eurostat-Code -> Sektor
    "FC_IND_E": "industrie", "FC_TRA_E": "verkehr", "FC_OTH_HH_E": "haushalte", "FC_OTH_CP_E": "gewerbe",
    "FC_OTH_AF_E": "sonstige", "FC_OTH_FISH_E": "sonstige", "FC_OTH_NSP_E": "sonstige",
}
QUELLEN = {  # Eurostat-Code -> Quelle
    "O4000XBIO": "oel", "G3000": "gas", "C0000X0350-0370": "kohle", "C0350-0370": "kohle",
    "P1000": "kohle", "S2000": "oel", "RA000": "erneuerbare", "E7000": "strom", "H8000": "waerme",
    "W6100_6220": "sonstige", "N900H": "sonstige",
}
NAMEN = {"industrie": "Industrie", "verkehr": "Verkehr", "haushalte": "Haushalte",
         "gewerbe": "Gewerbe, Handel, Dienstleistungen", "sonstige": "Land- und Forstwirtschaft, Sonstige",
         "oel": "Öl", "gas": "Erdgas", "kohle": "Kohle", "erneuerbare": "Erneuerbare direkt",
         "strom": "Strom", "waerme": "Fernwärme", "sonstige_q": "Abfall und Sonstige"}


def main():
    url = API + "".join(f"&nrg_bal={b}" for b in ["FC_E", *SEKTOREN]) + "".join(f"&siec={s}" for s in ["TOTAL", *QUELLEN])
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (energie-abruf)"})
    j = json.loads(urllib.request.urlopen(req, timeout=300).read())
    ids, size, dim = j["id"], j["size"], j["dimension"]
    cats = {k: list(dim[k]["category"]["index"].keys()) for k in ids}
    V = {}
    for idx, v in j["value"].items():
        i, pos = int(idx), []
        for s in reversed(size):
            pos.append(i % s)
            i //= s
        r = {k: cats[k][p] for k, p in zip(ids, reversed(pos))}
        V[(r["nrg_bal"], r["siec"], int(r["time"]))] = v
    jahre = sorted({k[2] for k in V})
    werte = {}
    for (b, s, t), v in V.items():
        if b in SEKTOREN and s in QUELLEN:
            q = QUELLEN[s] if QUELLEN[s] != "sonstige" else "sonstige_q"
            key = (t, SEKTOREN[b], q)
            werte[key] = werte.get(key, 0) + v / 1000
    # Prüfung: Summe der Teile gleich Gesamtwert FC_E/TOTAL je Jahr
    for t in jahre:
        tot = V.get(("FC_E", "TOTAL", t))
        teile = sum(v for (tt, _, _), v in werte.items() if tt == t)
        if tot and abs(teile - tot / 1000) > 0.5:
            raise SystemExit(f"{t}: Teile {teile:.1f} TWh, insgesamt {tot / 1000:.1f} TWh")
    DATEN.mkdir(exist_ok=True)
    with (DATEN / "endenergie_de.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["jahr", "sektor", "quelle", "twh"])
        for (t, se, q), v in sorted(werte.items()):
            w.writerow([t, se, q, round(v, 2)])
    neu = max(jahre)
    stand = {"aktualisiert": j["updated"][:10], "jahre": [min(jahre), neu], "namen": NAMEN,
             "insgesamt_twh": {t: round(V[("FC_E", "TOTAL", t)] / 1000, 1) for t in jahre if ("FC_E", "TOTAL", t) in V}}
    (DATEN / "endenergie_stand.json").write_text(json.dumps(stand, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Endenergie {min(jahre)} bis {neu}; {neu}: {stand['insgesamt_twh'][neu]} TWh")
    for se in dict.fromkeys(SEKTOREN.values()):
        s = {q: v for (t, s2, q), v in werte.items() if t == neu and s2 == se}
        tot = sum(s.values())
        print(f"  {NAMEN[se]}: {tot:.0f} TWh; " + ", ".join(f"{NAMEN[q]} {v / tot:.0%}" for q, v in sorted(s.items(), key=lambda x: -x[1]) if v / tot >= 0.05))


if __name__ == "__main__":
    main()
