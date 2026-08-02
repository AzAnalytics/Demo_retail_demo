# 🧭 Le Cockpit — Maison Lauret (démo)

Démonstrateur du produit **Le Cockpit** — réalisé par **Alexis Zueras**, Data Analyst freelance.
Charte **navy / or**, écran d'ouverture animé, puis tableau de bord de pilotage.
Données **100% fictives** (aucune donnée client réelle).

Un tableau de bord de pilotage pour une petite chaîne de boutiques déco-maison :
chiffre d'affaires, marge, comparaison vs l'an dernier, alertes automatiques,
analyse par magasin, par produit et par jour de la semaine.

## Aperçu des fonctionnalités
- KPI du mois avec comparaison explicite (juin 2026 vs juin 2025)
- Alertes automatiques quand une catégorie décroche
- Évolution mensuelle du CA par magasin (graphiques interactifs)
- Top / flop produits, contribution à la marge par catégorie
- Habitudes : CA par jour de la semaine
- Réel vs objectif
- **🔮 Prévisions** : projection du CA sur 12 mois (global / par magasin / par catégorie),
  avec zone d'incertitude, croissance anticipée et alerte automatique
- Filtres (magasin, catégorie, période) et export CSV

## Prévisions (module `cockpit_forecast.py`)

L'onglet 🔮 Prévisions projette le chiffre d'affaires sur 12 mois (global, par
magasin ou par catégorie), avec zone d'incertitude, croissance anticipée et alerte
automatique.

### Comment le modèle est choisi

Le moteur ne se repose pas sur un seul algorithme : il en met **trois en compétition**
et **retient automatiquement le plus fiable pour chaque série**.

1. **Saisonnier ajusté** — « même mois l'an dernier × croissance annuelle ». Méthode
   statistique de référence, sans dépendance externe.
2. **Régression Ridge + saisonnalité de Fourier** — modèle linéaire régularisé (codé
   en numpy) qui apprend tendance de fond + cycles annuels sur le log du CA.
3. **Tendance log-linéaire × profil saisonnier mensuel** — décomposition classique.

Le choix se fait par **backtest**, la règle d'or de la prévision : on entraîne chaque
modèle sur tout l'historique **sauf les 3 derniers mois**, on lui fait prédire ces
3 mois, puis on compare à la réalité. L'écart moyen (MAPE) départage les modèles ;
le plus précis gagne. On teste ainsi la capacité à prédire du *jamais vu*, pas à
réciter le passé. Le nom du modèle retenu et son erreur de test sont affichés dans
l'onglet, pour la transparence côté client.

### Critères de sélection appliqués

- **Précision mesurée** (backtest), jamais le choix « au feeling » ni le buzzword.
- **Volume de données** : 18 mois → modèles simples. Un modèle lourd sur peu de
  données mémorise au lieu d'apprendre (surapprentissage).
- **Nature du problème** : une série temporelle a besoin d'un modèle capable
  d'extrapoler une tendance et de gérer la saisonnalité.
- **Parcimonie** : à performance égale, le plus simple gagne (robuste + explicable).
- **Bon sens métier** : une prévision doit rester crédible (croissance cohérente
  avec le YoY réel), pas seulement afficher un bon MAPE.

### Pourquoi pas Random Forest / gradient boosting ?

Avec seulement 18 mois de données, un modèle à arbres surapprendrait, et surtout les
arbres sont **incapables d'extrapoler** — ils ne prédisent jamais au-delà des valeurs
vues à l'entraînement, ce qui est rédhibitoire pour projeter une tendance ou un pic de
Noël. Ces modèles deviendraient pertinents avec plusieurs années d'historique et des
variables externes (météo, promotions, trafic) ; ils pourraient alors être ajoutés à
la compétition sans changer la logique de sélection.

### Résultats sur les données de démo

Le modèle « Saisonnier ajusté » l'emporte sur toutes les séries. Précision (backtest
sur 3 mois) : **~97 % en global** (erreur 3,4 %) et **93–98 % par segment** (erreur
2–7 %). La zone d'incertitude à 95 % s'élargit avec l'horizon : fiable à court terme,
plus prudente vers la fin des 12 mois.

### API

```python
import cockpit_forecast as cf
r = cf.prevoir(df, group_col=None, entity=None, horizon=12)
# -> dict : history, forecast, lower, upper, model, mape, growth, total_next, total_prev
tableau = cf.recap_entites(df, "magasin")   # récap par entité (CA prévu, croissance, modèle, fiabilité)
```

## Lancer en local
```bash
pip install -r requirements.txt
streamlit run app.py
```
Le dashboard s'ouvre sur http://localhost:8501

## Identité « Le Cockpit »
Le look premium est fourni par le module réutilisable **`cockpit_theme.py`** :
- `apply_theme()` — charte navy/or (typo Playfair + Inter, cartes KPI, onglets, sidebar).
- `splash(...)` — écran d'ouverture plein écran : joue la vidéo Gemini `assets/cockpit_logo.mp4`
  si elle existe, sinon une animation CSS/SVG de secours. Ne se rejoue pas sur les filtres.
- `header(...)` — en-tête avec logo/emblème et sur-titre « LE COCKPIT ».
- `plotly_layout(fig)` — applique la charte à chaque graphique.

### Ajouter le logo animé (Gemini)
Voir **`assets/GEMINI_logo_anime.md`** : génère un clip 2–3 s sur Gemini, nomme-le
`cockpit_logo.mp4`, dépose-le dans `assets/`. Sans fichier, l'animation CSS prend le relais.

### Réutiliser la charte sur un autre dashboard
1. Copie `cockpit_theme.py` (et `.streamlit/config.toml`) dans le projet cible.
2. En haut de l'app : `from cockpit_theme import apply_theme, splash, header, footer, plotly_layout, COCKPIT`
3. Appelle `apply_theme()` puis `splash(...)` juste après `st.set_page_config(...)`,
   remplace `st.title/caption` par `header(...)`, et passe tes figures dans `plotly_layout(fig)`.

## Stack
Python · Pandas · NumPy · Streamlit · Plotly
(Prévisions codées en NumPy pur — aucune dépendance ML lourde.)

## Données
`ventes_maison_lauret.csv` : 33 940 transactions sur 18 mois (jan. 2025 → juin 2026),
générées par `generate_dataset.py` avec une saisonnalité réaliste.
