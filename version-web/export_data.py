"""
export_data.py — prepare les donnees du Cockpit pour la version web.

Lit ventes_maison_lauret.csv, produit un fichier JSON compact destine au
navigateur. Les previsions sont calculees ici une fois pour toutes avec le
module Python d'origine (cockpit_forecast), puis figees : elles ne dependent
pas des filtres dans l'application Streamlit.

Usage : python export_data.py <dossier_du_depot> <fichier_de_sortie.json>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(REPO))

import cockpit_calculs as cal  # noqa: E402  (apres l'ajout au sys.path)
import cockpit_forecast as cf  # noqa: E402

OBJECTIF_CROISSANCE = 1.08
SEUIL_ALERTE = 10.0
HORIZON = 12

# Les prix du fichier de caisse sont des prix boutique, donc TTC. Tout ce qui
# est publie est hors taxes, exactement comme dans l'application : les deux
# supports doivent annoncer le meme taux de marge.
TAUX_TVA = 0.20

df = pd.read_csv(REPO / "ventes_maison_lauret.csv", parse_dates=["date"])
df = cal.montants_hors_taxes(df, TAUX_TVA)

stores = sorted(df["magasin"].unique())
cats = sorted(df["categorie"].unique())
prods = sorted(df["produit"].unique())
cat_of_prod = (df.groupby("produit")["categorie"].first()
                 .reindex(prods).map({c: i for i, c in enumerate(cats)}).tolist())

day0 = df["date"].min().normalize()

d = df.sort_values("date")
cols = {
    "d": (d["date"].dt.normalize() - day0).dt.days.astype(int).tolist(),
    "m": d["magasin"].map({s: i for i, s in enumerate(stores)}).astype(int).tolist(),
    "c": d["categorie"].map({c: i for i, c in enumerate(cats)}).astype(int).tolist(),
    "p": d["produit"].map({p: i for i, p in enumerate(prods)}).astype(int).tolist(),
    "q": d["quantite"].astype(int).tolist(),
    # montants en centimes : des entiers, donc un JSON plus leger et pas d'erreur de virgule
    "ca": (d["ca"] * 100).round().astype(int).tolist(),
    "mg": (d["marge"] * 100).round().astype(int).tolist(),
}


def serie(s):
    """Serie pandas indexee par mois -> listes (mois 'AAAA-MM', valeurs arrondies)."""
    return {"x": [f"{t.year:04d}-{t.month:02d}" for t in s.index],
            "y": [round(float(v)) for v in s.values]}


def prevision(group_col, entity):
    r = cf.prevoir(df, group_col, entity, HORIZON)
    h, f = serie(r["history"]), serie(r["forecast"])
    return {
        "hist": h,
        "fc": f,
        "lo": [round(float(v)) for v in r["lower"].values],
        "hi": [round(float(v)) for v in r["upper"].values],
        "model": r["model"],
        "mape": None if pd.isna(r["mape"]) else round(float(r["mape"]), 1),
        "growth": round(float(r["growth"]), 1),
        "total_next": round(float(r["total_next"])),
    }


forecast = {"global": prevision(None, None), "magasin": {}, "categorie": {}}
for s in stores:
    forecast["magasin"][s] = prevision("magasin", s)
for c in cats:
    forecast["categorie"][c] = prevision("categorie", c)


def recap(group_col):
    t = cf.recap_entites(df, group_col, HORIZON)
    return [{"nom": str(row[group_col.capitalize()]),
             "ca": int(row["CA prévu 12 mois"]),
             "croissance": float(row["Croissance"]),
             "modele": str(row["Modèle retenu"]),
             "mape": None if pd.isna(row["Fiabilité (MAPE)"]) else float(row["Fiabilité (MAPE)"])}
            for _, row in t.iterrows()]


data = {
    "meta": {
        "stores": stores,
        "cats": cats,
        "prods": prods,
        "cat_of_prod": cat_of_prod,
        "day0": day0.strftime("%Y-%m-%d"),
        "ndays": int((df["date"].max().normalize() - day0).days),
        "nrows": int(len(df)),
        "objectif": OBJECTIF_CROISSANCE,
        "seuil": SEUIL_ALERTE,
        "horizon": HORIZON,
        "tva": TAUX_TVA,
    },
    "cols": cols,
    "forecast": forecast,
    "recap": {"magasin": recap("magasin"), "categorie": recap("categorie")},
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

print(f"ecrit : {OUT}")
print(f"ventes : {data['meta']['nrows']} | magasins : {len(stores)} | "
      f"categories : {len(cats)} | produits : {len(prods)}")
print(f"periode : {data['meta']['day0']} + {data['meta']['ndays']} jours")
print(f"taille : {OUT.stat().st_size} octets")
