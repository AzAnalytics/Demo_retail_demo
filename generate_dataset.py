import numpy as np, pandas as pd
from datetime import date, timedelta
rng = np.random.default_rng(42)

# Entreprise fictive : "Maison Lauret", concept store déco-maison, 3 boutiques (Sud-Ouest)
magasins = {
    "Toulouse":   {"poids": 0.50, "ticket": 1.15},
    "Auch":       {"poids": 0.22, "ticket": 0.90},
    "Montauban":  {"poids": 0.28, "ticket": 1.00},
}
# Catégories : prix de vente moyen et taux de marge
categories = {
    "Décoration":  {"pv": 32, "marge": 0.55, "poids": 0.30},
    "Cuisine":     {"pv": 24, "marge": 0.48, "poids": 0.22},
    "Textile":     {"pv": 40, "marge": 0.52, "poids": 0.18},
    "Cadeaux":     {"pv": 18, "marge": 0.60, "poids": 0.17},
    "Papeterie":   {"pv": 9,  "marge": 0.50, "poids": 0.13},
}
produits = {
 "Décoration": ["Vase céramique","Bougie parfumée","Cadre photo","Miroir rond","Coussin lin"],
 "Cuisine": ["Mug grès","Planche à découper","Set torchons","Bol émaillé","Théière fonte"],
 "Textile": ["Plaid laine","Nappe coton","Rideau lin","Tapis tissé","Serviettes (x4)"],
 "Cadeaux": ["Coffret thé","Savon artisanal","Carnet cuir","Mini plante","Bougie voyage"],
 "Papeterie": ["Carnet A5","Stylo plume","Carte postale","Marque-page","Stickers"],
}

def saison(d):
    # pic de Noël (nov-déc), creux d'été (juil-août)
    m = d.month
    base = 1.0
    if m in (11,12): base = 1.8
    elif m in (1,2): base = 0.8
    elif m in (7,8): base = 0.7
    elif m in (5,6): base = 1.1
    # week-end plus fort
    if d.weekday() >= 5: base *= 1.4
    return base

start = date(2025,1,1); end = date(2026,6,30)
rows = []
d = start
cat_names = list(categories); cat_poids = [categories[c]["poids"] for c in cat_names]
mag_names = list(magasins)
while d <= end:
    for mag in mag_names:
        lam = 9 * magasins[mag]["poids"] * 6 * saison(d)  # nb de tickets/jour
        n = rng.poisson(lam)
        for _ in range(n):
            cat = rng.choice(cat_names, p=cat_poids)
            prod = rng.choice(produits[cat])
            pv_base = categories[cat]["pv"] * magasins[mag]["ticket"]
            pv = round(max(2, rng.normal(pv_base, pv_base*0.18)), 2)
            qte = int(rng.choice([1,1,1,2,2,3], p=[.45,.2,.1,.13,.08,.04]))
            cout = round(pv * (1 - categories[cat]["marge"]) * rng.normal(1,0.05), 2)
            paiement = rng.choice(["CB","Espèces","Sans contact"], p=[.55,.2,.25])
            rows.append([d.isoformat(), mag, cat, prod, qte, pv, round(cout,2), paiement])
    d += timedelta(days=1)

df = pd.DataFrame(rows, columns=["date","magasin","categorie","produit","quantite","prix_unitaire","cout_unitaire","paiement"])
df["ca_ttc"] = (df["quantite"]*df["prix_unitaire"]).round(2)
df["marge"] = (df["quantite"]*(df["prix_unitaire"]-df["cout_unitaire"])).round(2)
df.to_csv("ventes_maison_lauret.csv", index=False)

print("Lignes :", len(df))
print("Période :", df.date.min(), "→", df.date.max())
print("CA total : {:,.0f} €".format(df.ca_ttc.sum()))
print("Marge totale : {:,.0f} €".format(df.marge.sum()))
print("Taux de marge : {:.1f}%".format(100*df.marge.sum()/df.ca_ttc.sum()))
print("Panier moyen : {:.2f} €".format(df.ca_ttc.sum()/len(df)))
print("\nCA par magasin :"); print(df.groupby("magasin").ca_ttc.sum().round(0))
print("\nCA par catégorie :"); print(df.groupby("categorie").ca_ttc.sum().round(0))
