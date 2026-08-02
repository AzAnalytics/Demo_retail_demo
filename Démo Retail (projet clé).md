---
type: projet-clé
statut: en cours
créé: 2026-06-22
tags: [projet, portfolio, retail, dashboard, démo]
---

# 🏆 Démo Retail, projet clé

> Démonstrateur public pour incarner mon offre. Données **100% fictives**, donc aucun souci de confidentialité. Sert de preuve + contenu (étude de cas).

## 🏪 L'entreprise (fictive)
**Maison Lauret**, concept store déco-maison, 3 boutiques dans le Sud-Ouest (Toulouse, Auch, Montauban). Vend déco, cuisine, textile, cadeaux, papeterie.

## 📦 Le dataset
Fichier : `ventes_maison_lauret.csv`
- **33 940 transactions** sur **18 mois** (janv. 2025 → juin 2026)
- Colonnes : date, magasin, categorie, produit, quantite, prix_unitaire, cout_unitaire, paiement, ca_ttc, marge
- Saisonnalité intégrée (pic de Noël, creux d'été, week-ends plus forts)

## 📊 Chiffres clés (le dashboard doit les faire ressortir)
- **CA total : 1 214 955 €**
- **Marge totale : 645 121 € (53,1%)**
- **Panier moyen : 35,80 €**
- CA par magasin : Toulouse 669k, Montauban 322k, Auch 223k
- Top catégories : Décoration 443k, Textile 336k, Cuisine 244k

## 🎯 KPI à mettre dans le dashboard (vue dirigeant)
1. CA et marge du mois, vs mois précédent et vs N-1
2. Évolution mensuelle du CA (courbe avec la saisonnalité)
3. Répartition par magasin et par catégorie
4. Top produits et panier moyen
5. Une alerte simple : catégorie ou magasin en baisse

## 🛠️ Choix de l'outil
- **Power BI** : idéal pour le public PME, format pro, partage facile.
- **Streamlit** : interactif, hébergeable en ligne gratuitement, montre ton côté Python.

## ➡️ Prochaines étapes
- [x] Choisir l'outil → **Streamlit** (Mac-friendly, met Python en avant)
- [x] Construire le dashboard orienté dirigeant → `app.py` (5 onglets, KPI, alertes, Plotly, export)
- [x] **Le mettre en ligne** → 🔗 https://demoretaildemo.streamlit.app
- [ ] En tirer le post étude de cas → [[02 - Domaines/Création/Post - Démo Retail (étude de cas)]]
- [ ] Ajouter le lien dans toutes les bios (LinkedIn, Malt, Insta, GitHub)

## 🖥️ Le dashboard (fait)
Fichiers : `app.py`, `requirements.txt`, `README.md`, `.streamlit/config.toml`, `generate_dataset.py`.
Lancer : `pip install -r requirements.txt` puis `streamlit run app.py`.
Fonctionnalités : KPI mois vs N-1 (dates explicites), alertes auto par catégorie, évolution par magasin, top/flop produits, contribution marge, CA par jour de semaine, réel vs objectif, filtres + export CSV.

## 🔗 Liens
- Projet : [[01 - Projets/Packager mon offre data]]
- Plan de contenu : [[02 - Domaines/Création/Plan de contenu - Semaine du 22 juin]]
