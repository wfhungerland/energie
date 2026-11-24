"""Energiewende vor Ort: Kennzahlen je Kreis (400 Kreise, Gebietsstand 2024).

Quellen (alle frei, siehe README):
- Marktstammdatenregister (Bundesnetzagentur, DL-DE-BY 2.0), je Kreis, Jahr und Energieträger
  aggregiert. Die 3,3 GB des Gesamtexports werden nicht hier gerechnet; das Skript liest die
  fertige Datei mastr_kreis_jahr.csv (kreis, jahr, energietraeger, anzahl, brutto_mw), Pfad oder
  Adresse in --mastr oder in der Umgebungsvariable MASTR_KREIS_JAHR.
- Regionaldatenbank Deutschland (DL-DE-BY 2.0): 12411-01-01-4 Bevölkerung am 31.12.,
  46251-02-01-4 Pkw nach Kraftstoffarten am 1.1. (Kraftfahrt-Bundesamt). Abruf über die
  REST-Schnittstelle; Konto in RDB_USER und RDB_PASS oder über das Netzwerk-Secret der Umgebung.
- Ladesäulenregister der Bundesnetzagentur (CSV), Ladepunkte in Betrieb; Zuordnung zum Kreis
  über die Koordinaten (Punkt in NUTS-3-Fläche), geprüft gegen den Kreisnamen im Register.
- Zensus 2022 (Statistische Ämter des Bundes und der Länder, DL-DE-BY 2.0), Tabelle 4000W-1012
  Wohnungen nach Energieträger der Heizung, Kreise (GEOLK4). Konto der Zensus-Datenbank in ZENSUS_USER
  und ZENSUS_PASS oder über das Netzwerk-Secret der Umgebung; ohne Zugang entfallen die Heizungswerte.
- GISCO (Eurostat): NUTS-3-Flächen 2024 und Zuordnung Gemeinde zu NUTS 3 (EU-27-LAU-2025-NUTS-2024).

Aufruf: python abruf/kreise.py [--mastr PFAD_ODER_URL] [--cache ORDNER]
Ergebnis: daten/kreise_energie.csv (ags, nuts3, kennzahl, jahr, wert),
          daten/kreise_namen.csv (ags, nuts3, name), daten/kreise_karte.json (Flächen für die Vorschau).
"""
import argparse
import csv
import io
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATEN = ROOT / "daten"
RDB = "https://www.regionalstatistik.de/genesisws/rest/2020/"
BNETZA_SEITE = "https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/E-Mobilitaet/start.html"
LAU_SEITE = "https://ec.europa.eu/eurostat/web/nuts/local-administrative-units"
GISCO = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_{m}M_2024_4326_LEVL_3.geojson"
UA = {"User-Agent": "Mozilla/5.0 (energie-abruf)"}
ZENSUS = "https://ergebnisse.zensus2022.de/api/rest/2020/"

# Kennzahlen: Name -> Beschreibung (für README und Prüfung)
KENNZAHLEN = {
    "wind_kw_ew": "Windkraft an Land, installierte Bruttoleistung in kW je Einwohner, Jahresende",
    "sonne_kw_ew": "Photovoltaik, installierte Bruttoleistung in kW je Einwohner, Jahresende",
    "wind_sonne_kw_ew": "Wind an Land und Photovoltaik zusammen, kW je Einwohner, Jahresende",
    "eauto_anteil": "Anteil reiner Elektroautos am Pkw-Bestand in %, Stichtag 1.1.",
    "plugin_anteil": "Anteil der Plug-in-Hybride am Pkw-Bestand in %, Stichtag 1.1.",
    "ladepunkte_10t_ew": "öffentliche Ladepunkte in Betrieb je 10.000 Einwohner",
    "eautos_je_ladepunkt": "reine Elektroautos je öffentlichem Ladepunkt",
    "waermepumpe_anteil": "Anteil der Wohnungen mit Wärmepumpe, Solar- oder Geothermie als Energieträger der Heizung in %, Zensus 15.5.2022",
    "gas_oel_anteil": "Anteil der Wohnungen mit Gas oder Heizöl als Energieträger der Heizung in %, Zensus 15.5.2022",
    "fernwaerme_anteil": "Anteil der Wohnungen mit Fernwärme in %, Zensus 15.5.2022",
}


def holen(url, ziel=None, daten=None, cache=None):
    """Lädt eine Adresse; mit cache wird die Datei dort abgelegt und wiederverwendet."""
    if cache and ziel and (cache / ziel).exists():
        return (cache / ziel).read_bytes()
    req = urllib.request.Request(url, data=daten, headers=UA)
    with urllib.request.urlopen(req, timeout=600) as r:
        b = r.read()
    if cache and ziel and not b.lstrip()[:1] in (b"{", b"<"):   # Fehlermeldungen nicht zwischenspeichern
        cache.mkdir(parents=True, exist_ok=True)
        (cache / ziel).write_bytes(b)
    return b


def rdb_tabelle(code, jahr, cache):
    """Regionaldatenbank: Tabelle als flache CSV (ffcsv) für ein Jahr."""
    p = {"name": code, "area": "all", "format": "ffcsv", "startyear": str(jahr), "endyear": str(jahr), "language": "de"}
    if os.environ.get("RDB_USER"):
        p.update(username=os.environ["RDB_USER"], password=os.environ.get("RDB_PASS", ""))
    b = holen(RDB + "data/tablefile", f"{code}_{jahr}.zip", urllib.parse.urlencode(p).encode(), cache)
    if not b.startswith(b"PK"):
        sys.exit(f"Regionaldatenbank {code}: keine Datei ({b[:200]!r})")
    z = zipfile.ZipFile(io.BytesIO(b))
    d = pd.read_csv(z.open(z.namelist()[0]), sep=";", dtype=str)
    d = d[d["1_variable_code"] == "KREISE"].copy()
    d["ags"] = d["1_variable_attribute_code"]
    d["wert"] = pd.to_numeric(d["value"], errors="coerce")
    return d


def lau_nuts(cache):
    """AGS (5 Stellen) -> NUTS 3 und die 400 heutigen Kreise."""
    html = holen(LAU_SEITE).decode("utf-8", "ignore")
    m = re.search(r'href="(/eurostat/documents/[^"]*EU-27-LAU-2025-NUTS-2024\.xlsx[^"]*)"', html)
    if not m:
        sys.exit("LAU-Datei nicht gefunden auf " + LAU_SEITE)
    b = holen("https://ec.europa.eu" + m.group(1).replace("&amp;", "&"), "lau_nuts.xlsx", cache=cache)
    de = pd.read_excel(io.BytesIO(b), sheet_name="DE", dtype=str)
    de["ags"] = de["LAU CODE"].str[:5]
    z = de.groupby("ags")["NUTS3"].agg(lambda s: s.mode().iat[0])
    if z.index.duplicated().any() or z.duplicated().any():
        sys.exit("Zuordnung AGS zu NUTS 3 nicht eindeutig")
    return z.to_dict()


def flaechen(cache, massstab="01"):
    """NUTS-3-Flächen Deutschlands: nuts3 -> Liste von Ringen (lon, lat)."""
    g = json.loads(holen(GISCO.format(m=massstab), f"nuts3_{massstab}M.geojson", cache=cache))
    out = {}
    for f in g["features"]:
        if f["properties"]["CNTR_CODE"] != "DE":
            continue
        geo = f["geometry"]
        polys = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
        out[f["properties"]["NUTS_ID"]] = [np.asarray(ring) for poly in polys for ring in poly]
    return out


def zensus_heizung(cache):
    """Wohnungen nach Energieträger der Heizung je Kreis (Anzahl), Zensus 15.5.2022."""
    p = {"name": "4000W-1012", "area": "all", "format": "ffcsv", "compress": "false", "regionalvariable": "GEOLK4", "language": "de"}
    h = dict(UA)
    if os.environ.get("ZENSUS_USER"):
        h.update(username=os.environ["ZENSUS_USER"], password=os.environ.get("ZENSUS_PASS", ""))
    ziel = cache / "zensus_4000W-1012_kreise.zip"
    if ziel.exists():
        b = ziel.read_bytes()
    else:
        req = urllib.request.Request(ZENSUS + "data/tablefile", data=urllib.parse.urlencode(p).encode(), headers=h)
        b = urllib.request.urlopen(req, timeout=900).read()
        if not b.startswith(b"PK"):
            print("Zensus: kein Zugang oder keine Datei, Heizung entfällt:", b[:160])
            return None
        cache.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(b)
    z = zipfile.ZipFile(io.BytesIO(b))
    d = pd.read_csv(z.open(z.namelist()[0]), sep=";", dtype=str)
    d = d[d.value_unit == "Anzahl"].copy()
    d["wert"] = pd.to_numeric(d.value.str.replace(",", "."), errors="coerce").fillna(0)   # "-" = keine
    t = d.pivot_table(index="1_variable_attribute_code", columns="2_variable_attribute_label", values="wert", aggfunc="sum")
    return t


def punkt_in_flaeche(lon, lat, ringe):
    """Ray casting mit Gerade-ungerade-Regel über alle Ringe (Löcher eingeschlossen), vektorisiert."""
    innen = np.zeros(len(lon), dtype=bool)
    for r in ringe:
        x1, y1 = r[:-1, 0], r[:-1, 1]
        x2, y2 = r[1:, 0], r[1:, 1]
        for a, b, c, d in zip(x1, y1, x2, y2):
            if b == d:
                continue
            k = (b > lat) != (d > lat)
            if not k.any():
                continue
            xs = a + (lat - b) * (c - a) / (d - b)
            innen ^= k & (lon < xs)
    return innen


def ladepunkte(nuts_flaechen, nuts_ags, cache):
    """Ladepunkte in Betrieb je Kreis (AGS) aus dem Ladesäulenregister."""
    html = holen(BNETZA_SEITE).decode("utf-8", "ignore")
    m = re.search(r'href="(https://data\.bundesnetzagentur\.de/[^"]*Ladesaeulenregister[^"]*\.csv)"', html)
    if not m:
        sys.exit("Ladesäulenregister nicht gefunden auf " + BNETZA_SEITE)
    url = m.group(1)
    stand = re.search(r"(\d{4}-\d{2}-\d{2})", url).group(1)
    b = holen(url, "ladesaeulen_" + stand + ".csv", cache=cache)
    txt = b.decode("latin1")
    zeilen = txt.splitlines()
    kopf = next(i for i, z in enumerate(zeilen) if z.startswith("Ladeeinrichtungs-ID"))
    d = pd.read_csv(io.StringIO("\n".join(zeilen[kopf:])), sep=";", dtype=str, low_memory=False)
    d = d[d["Status"] == "In Betrieb"].copy()
    d["lp"] = pd.to_numeric(d["Anzahl Ladepunkte"], errors="coerce").fillna(0)
    lat = pd.to_numeric(d["Breitengrad"].str.replace(",", ".").str.strip().str.rstrip("."), errors="coerce").to_numpy()
    lon = pd.to_numeric(d["Längengrad"].str.replace(",", ".").str.strip().str.rstrip("."), errors="coerce").to_numpy()
    nuts = np.full(len(d), "", dtype=object)
    for n, ringe in nuts_flaechen.items():
        alle = np.concatenate(ringe)
        box = (lon >= alle[:, 0].min()) & (lon <= alle[:, 0].max()) & (lat >= alle[:, 1].min()) & (lat <= alle[:, 1].max()) & (nuts == "")
        if box.any():
            idx = np.where(box)[0]
            treffer = punkt_in_flaeche(lon[idx], lat[idx], ringe)
            nuts[idx[treffer]] = n
    d["nuts3"] = nuts
    # Punkte außerhalb aller Flächen (Küste, Grenze, falsche Koordinaten): über den Kreisnamen im Register
    name_nuts = d[d.nuts3 != ""].groupby("Kreis/kreisfreie Stadt")["nuts3"].agg(lambda s: s.mode().iat[0])
    rest = d.nuts3 == ""
    d.loc[rest, "nuts3"] = d.loc[rest, "Kreis/kreisfreie Stadt"].map(name_nuts).fillna("")
    # Prüfung: Anteil der Punkte, deren Fläche zum häufigsten Kreis ihres Registernamens passt
    passt = (d["nuts3"] == d["Kreis/kreisfreie Stadt"].map(name_nuts)).mean()
    ohne = (d.nuts3 == "").sum()
    print(f"Ladesäulenregister {stand}: {len(d)} Einrichtungen, {int(d.lp.sum())} Ladepunkte; "
          f"Fläche passt zum Namen bei {passt:.1%}, ohne Kreis {ohne}")
    lp = d[d.nuts3 != ""].groupby("nuts3")["lp"].sum()
    return {nuts_ags[n]: v for n, v in lp.items() if n in nuts_ags}, stand


def karte(cache):
    """Vereinfachte Kreisflächen als SVG-Pfade (Lambert-artige Projektion um 51° N)."""
    fl = flaechen(cache, "03")
    k = math.cos(math.radians(51.0))
    alle = np.concatenate([np.concatenate(r) for r in fl.values()])
    x0, x1 = alle[:, 0].min() * k, alle[:, 0].max() * k
    y0, y1 = alle[:, 1].min(), alle[:, 1].max()
    s = 1000 / max(x1 - x0, y1 - y0)
    pfade = {}
    for n, ringe in fl.items():
        teile = []
        for r in ringe:
            p = np.column_stack(((r[:, 0] * k - x0) * s, (y1 - r[:, 1]) * s)).round(1)
            keep = np.r_[True, (np.abs(np.diff(p, axis=0)).sum(axis=1) > 0.6)]
            p = p[keep]
            if len(p) < 4:
                continue
            teile.append("M" + "L".join(f"{a:g},{b:g}" for a, b in p) + "Z")
        pfade[n] = "".join(teile)
    return {"breite": round((x1 - x0) * s, 1), "hoehe": round((y1 - y0) * s, 1), "pfade": pfade}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mastr", default=os.environ.get("MASTR_KREIS_JAHR"), help="Pfad oder Adresse von mastr_kreis_jahr.csv")
    ap.add_argument("--cache", type=Path, default=ROOT / ".cache")
    a = ap.parse_args()
    if not a.mastr:
        sys.exit("mastr_kreis_jahr.csv fehlt: --mastr oder MASTR_KREIS_JAHR setzen")
    DATEN.mkdir(exist_ok=True)

    ags_nuts = lau_nuts(a.cache)
    nuts_ags = {v: k for k, v in ags_nuts.items()}
    print(f"{len(ags_nuts)} Kreise mit NUTS 3")

    # Bevölkerung: jüngster 31.12. mit allen Kreisen
    for jahr in range(2030, 2019, -1):
        try:
            bev = rdb_tabelle("12411-01-01-4", jahr, a.cache)
        except SystemExit:
            continue
        bev = bev[bev["2_variable_attribute_label"] == "Insgesamt"]
        bev = bev[bev.ags.isin(ags_nuts)].set_index("ags")["wert"].dropna()
        if len(bev) == len(ags_nuts):
            break
    print(f"Bevölkerung 31.12.{jahr}: {bev.sum():,.0f}")
    bev_jahr = jahr

    # MaStR: Wind und Sonne am Ende des Bevölkerungsjahres
    m = pd.read_csv(a.mastr, dtype={"kreis": str})
    m = m[m.jahr == bev_jahr]
    mw = m.pivot_table(index="kreis", columns="energietraeger", values="brutto_mw", aggfunc="sum").reindex(bev.index).fillna(0)
    wind, sonne = mw.get("Wind", 0), mw.get("Solare Strahlungsenergie", 0)
    print(f"MaStR Ende {bev_jahr}: Wind an Land {wind.sum()/1000:.1f} GW, Photovoltaik {sonne.sum()/1000:.1f} GW")

    # Pkw nach Kraftstoff: jüngster 1.1.
    for pjahr in range(2030, 2019, -1):
        try:
            pkw = rdb_tabelle("46251-02-01-4", pjahr, a.cache)
        except SystemExit:
            continue
        pkw = pkw[pkw.ags.isin(ags_nuts)].pivot_table(index="ags", columns="2_variable_attribute_label", values="wert", aggfunc="sum")
        if len(pkw) == len(ags_nuts) and pkw["Elektro"].notna().all():
            break
    print(f"Pkw 1.1.{pjahr}: {pkw['Insgesamt'].sum():,.0f}, davon Elektro {pkw['Elektro'].sum():,.0f}")

    lp, lp_stand = ladepunkte(flaechen(a.cache, "01"), nuts_ags, a.cache)
    lp = pd.Series(lp).reindex(bev.index).fillna(0)

    hz = zensus_heizung(a.cache)
    reihen = {
        "wind_kw_ew": (wind * 1000 / bev, bev_jahr),
        "sonne_kw_ew": (sonne * 1000 / bev, bev_jahr),
        "wind_sonne_kw_ew": ((wind + sonne) * 1000 / bev, bev_jahr),
        "eauto_anteil": (pkw["Elektro"] / pkw["Insgesamt"] * 100, pjahr),
        "plugin_anteil": (pkw["darunter Plug-In-Hybrid"] / pkw["Insgesamt"] * 100, pjahr),
        "ladepunkte_10t_ew": (lp / bev * 10000, int(lp_stand[:4])),
        "eautos_je_ladepunkt": (pkw["Elektro"] / lp.where(lp > 0), int(lp_stand[:4])),
    }
    if hz is not None:
        fehlt = set(bev.index) - set(hz.index)
        if fehlt:
            sys.exit(f"Zensus: Kreise fehlen {sorted(fehlt)}")
        alle = hz["Insgesamt"]
        reihen["waermepumpe_anteil"] = (hz["Solar-/Geothermie, Wärmepumpen"] / alle * 100, 2022)
        reihen["gas_oel_anteil"] = ((hz["Gas"] + hz["Heizöl"]) / alle * 100, 2022)
        reihen["fernwaerme_anteil"] = (hz["Fernwärme (verschiedene Energieträger)"] / alle * 100, 2022)
        print(f"Zensus 2022: {alle.sum():,.0f} Wohnungen, Wärmepumpe/Solar/Geothermie {hz['Solar-/Geothermie, Wärmepumpen'].sum() / alle.sum():.1%}")
    with (DATEN / "kreise_energie.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ags", "nuts3", "kennzahl", "jahr", "wert"])
        for kz, (s, j) in reihen.items():
            for ags in sorted(bev.index):
                v = s.get(ags)
                if v is not None and pd.notna(v):
                    w.writerow([ags, ags_nuts[ags], kz, j, f"{v:.4g}"])
    # Bund zum Vergleich
    bund = {
        "wind_kw_ew": wind.sum() * 1000 / bev.sum(), "sonne_kw_ew": sonne.sum() * 1000 / bev.sum(),
        "wind_sonne_kw_ew": (wind.sum() + sonne.sum()) * 1000 / bev.sum(),
        "eauto_anteil": pkw["Elektro"].sum() / pkw["Insgesamt"].sum() * 100,
        "plugin_anteil": pkw["darunter Plug-In-Hybrid"].sum() / pkw["Insgesamt"].sum() * 100,
        "ladepunkte_10t_ew": lp.sum() / bev.sum() * 10000, "eautos_je_ladepunkt": pkw["Elektro"].sum() / lp.sum(),
    }
    if hz is not None:
        bund.update(waermepumpe_anteil=hz["Solar-/Geothermie, Wärmepumpen"].sum() / hz["Insgesamt"].sum() * 100,
                    gas_oel_anteil=(hz["Gas"].sum() + hz["Heizöl"].sum()) / hz["Insgesamt"].sum() * 100,
                    fernwaerme_anteil=hz["Fernwärme (verschiedene Energieträger)"].sum() / hz["Insgesamt"].sum() * 100)
    namen = rdb_tabelle("12411-01-01-4", bev_jahr, a.cache)[["ags", "1_variable_attribute_label"]].drop_duplicates("ags").set_index("ags")["1_variable_attribute_label"]
    with (DATEN / "kreise_namen.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ags", "nuts3", "name"])
        for ags in sorted(bev.index):
            w.writerow([ags, ags_nuts[ags], namen.get(ags, "")])
    stand = {"bevoelkerung": f"31.12.{bev_jahr}", "mastr": f"Ende {bev_jahr}", "pkw": f"1.1.{pjahr}", "ladesaeulen": lp_stand, "zensus": "15.5.2022" if hz is not None else None,
             "bund": {k: round(float(v), 4) for k, v in bund.items()}, "kennzahlen": KENNZAHLEN}
    (DATEN / "kreise_stand.json").write_text(json.dumps(stand, ensure_ascii=False, indent=1), encoding="utf-8")
    (DATEN / "kreise_karte.json").write_text(json.dumps(karte(a.cache), separators=(",", ":")), encoding="utf-8")
    for k, v in bund.items():
        print(f"  Deutschland {k}: {v:.3g}")


if __name__ == "__main__":
    main()
