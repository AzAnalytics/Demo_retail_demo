"""
generate_dataset.py — les ventes fictives de Maison Lauret
===========================================================
Fabrique `ventes_maison_lauret.csv` : 18 mois de tickets de caisse pour un
concept store déco-maison à trois boutiques. Données 100 % fictives.

Deux règles que ce fichier respecte, et qui font la différence entre une démo
qu'on montre et une démo qu'on cache :

1. **La période glisse avec la date du jour.** Le fichier se termine au dernier
   mois complet, jamais à une date écrite en dur. Une démo qui s'arrête il y a
   cinq mois dit au prospect que le produit est abandonné.
2. **Le décrochage du Textile est posé volontairement**, pas tiré au sort. Une
   démonstration doit toujours montrer quelque chose : si l'alerte dépendait du
   hasard du tirage, elle disparaîtrait un jour sans prévenir, au pire moment.

Les prix sont des **prix boutique, donc TTC** : c'est l'écran qui les ramène
hors taxes (voir `config.TAUX_TVA`). La colonne `marge` écrite ici est donc une
marge sur prix TTC, gardée pour compatibilité ; l'écran recalcule lui-même la
marge hors taxes.

Lancer :  python generate_dataset.py
"""
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

# Au-delà de ce retard, le fichier livré est considéré comme périmé et
# l'écran le refabrique tout seul (voir `est_perime`). Sept jours laissent
# passer le décalage normal entre la fin d'un mois et sa régénération.
JOURS_TOLERANCE = 7

MOIS_HISTORIQUE = 18

# Entreprise fictive : "Maison Lauret", concept store déco-maison (Sud-Ouest)
magasins = {
    "Toulouse":   {"poids": 0.50, "ticket": 1.15},
    "Auch":       {"poids": 0.22, "ticket": 0.90},
    "Montauban":  {"poids": 0.28, "ticket": 1.00},
}
# Catégories : prix de vente moyen (TTC) et taux de marge sur ce prix
categories = {
    "Décoration":  {"pv": 32, "marge": 0.55, "poids": 0.30},
    "Cuisine":     {"pv": 24, "marge": 0.48, "poids": 0.22},
    "Textile":     {"pv": 40, "marge": 0.52, "poids": 0.18},
    "Cadeaux":     {"pv": 18, "marge": 0.60, "poids": 0.17},
    "Papeterie":   {"pv": 9,  "marge": 0.50, "poids": 0.13},
}
produits = {
 "Décoration": ["Vase céramique", "Bougie parfumée", "Cadre photo", "Miroir rond", "Coussin lin"],
 "Cuisine": ["Mug grès", "Planche à découper", "Set torchons", "Bol émaillé", "Théière fonte"],
 "Textile": ["Plaid laine", "Nappe coton", "Rideau lin", "Tapis tissé", "Serviettes (x4)"],
 "Cadeaux": ["Coffret thé", "Savon artisanal", "Carnet cuir", "Mini plante", "Bougie voyage"],
 "Papeterie": ["Carnet A5", "Stylo plume", "Carte postale", "Marque-page", "Stickers"],
}

# --- Le décrochage posé volontairement ---------------------------------
# Le Textile perd ce volume sur les derniers mois. Il déclenche l'alerte de
# l'écran (seuil de 10 % dans config.py) : c'est l'histoire que raconte la démo.
CATEGORIE_EN_RECUL = "Textile"
PERTE_VOLUME = 0.20          # 20 % de tickets en moins
MOIS_DE_RECUL = 3            # sur les 3 derniers mois


def dernier_mois_complet(aujourdhui: date | None = None) -> date:
    """Le dernier jour du dernier mois terminé."""
    jour = aujourdhui or date.today()
    return jour.replace(day=1) - timedelta(days=1)


def premier_jour(fin: date, mois: int = MOIS_HISTORIQUE) -> date:
    """Le 1er du mois situé `mois` rangs avant la fin, fin incluse."""
    total = fin.year * 12 + (fin.month - 1) - (mois - 1)
    return date(total // 12, total % 12 + 1, 1)


def saison(d: date) -> float:
    """Pic de Noël, creux d'été, week-ends plus forts."""
    m = d.month
    base = 1.0
    if m in (11, 12):
        base = 1.8
    elif m in (1, 2):
        base = 0.8
    elif m in (7, 8):
        base = 0.7
    elif m in (5, 6):
        base = 1.1
    if d.weekday() >= 5:
        base *= 1.4
    return base


def genere(fin: date | None = None, mois: int = MOIS_HISTORIQUE) -> pd.DataFrame:
    """Les tickets des `mois` derniers mois, le décrochage Textile compris."""
    fin = fin or dernier_mois_complet()
    debut = premier_jour(fin, mois)
    debut_recul = premier_jour(fin, MOIS_DE_RECUL)

    cat_names = list(categories)
    cat_poids = [categories[c]["poids"] for c in cat_names]
    rows = []
    d = debut
    while d <= fin:
        for mag, info in magasins.items():
            lam = 9 * info["poids"] * 6 * saison(d)       # nb de tickets par jour
            for _ in range(rng.poisson(lam)):
                cat = rng.choice(cat_names, p=cat_poids)
                # Le décrochage : certains tickets Textile n'ont plus lieu.
                if (cat == CATEGORIE_EN_RECUL and d >= debut_recul
                        and rng.random() < PERTE_VOLUME):
                    continue
                prod = rng.choice(produits[cat])
                pv_base = categories[cat]["pv"] * info["ticket"]
                pv = round(max(2, rng.normal(pv_base, pv_base * 0.18)), 2)
                qte = int(rng.choice([1, 1, 1, 2, 2, 3], p=[.45, .2, .1, .13, .08, .04]))
                cout = round(pv * (1 - categories[cat]["marge"]) * rng.normal(1, 0.05), 2)
                paiement = rng.choice(["CB", "Espèces", "Sans contact"], p=[.55, .2, .25])
                rows.append([d.isoformat(), mag, cat, prod, qte, pv, round(cout, 2), paiement])
        d += timedelta(days=1)

    df = pd.DataFrame(rows, columns=["date", "magasin", "categorie", "produit",
                                     "quantite", "prix_unitaire", "cout_unitaire", "paiement"])
    df["ca_ttc"] = (df["quantite"] * df["prix_unitaire"]).round(2)
    df["marge"] = (df["quantite"] * (df["prix_unitaire"] - df["cout_unitaire"])).round(2)
    return df


def est_perime(chemin: str | Path, jours_tolerance: int = JOURS_TOLERANCE,
               aujourdhui: date | None = None) -> bool:
    """Le fichier livré s'arrête-t-il trop loin dans le passé ?

    Sert à l'écran : sur un hébergement où personne ne relance le script, la
    démonstration se refabrique toute seule plutôt que d'afficher un mois
    vieux de cinq mois. Un fichier absent ou illisible est périmé par défaut.
    """
    chemin = Path(chemin)
    if not chemin.exists():
        return True
    try:
        dates = pd.read_csv(chemin, usecols=["date"])["date"]
    except Exception:
        return True
    derniere = pd.to_datetime(dates, errors="coerce").max()
    if pd.isna(derniere):
        return True
    return (dernier_mois_complet(aujourdhui) - derniere.date()).days > jours_tolerance


if __name__ == "__main__":
    df = genere()
    df.to_csv("ventes_maison_lauret.csv", index=False)

    tva = 0.20
    ca_ht = df.ca_ttc.sum() / (1 + tva)
    marge_ht = ca_ht - (df.quantite * df.cout_unitaire).sum()
    print("Lignes :", len(df))
    print("Période : du", df.date.min(), "au", df.date.max())
    print("CA TTC : {:,.0f} €".format(df.ca_ttc.sum()))
    print("CA HT : {:,.0f} €".format(ca_ht))
    print("Marge HT : {:,.0f} € ({:.1f} %)".format(marge_ht, 100 * marge_ht / ca_ht))
    print("Panier moyen HT : {:.2f} €".format(ca_ht / len(df)))
    print("\nCA TTC par magasin :")
    print(df.groupby("magasin").ca_ttc.sum().round(0))
    print("\nCA TTC par catégorie :")
    print(df.groupby("categorie").ca_ttc.sum().round(0))

    # Contrôle du décrochage posé : le Textile du dernier mois face à l'an dernier.
    d2 = df.assign(mois=pd.to_datetime(df.date).dt.to_period("M"))
    dernier = d2.mois.max()
    textile = d2[d2.categorie == CATEGORIE_EN_RECUL].groupby("mois").ca_ttc.sum()
    if dernier - 12 in textile.index:
        recul = (textile[dernier] / textile[dernier - 12] - 1) * 100
        print("\nTextile {} vs {} : {:+.1f} %".format(dernier, dernier - 12, recul))
