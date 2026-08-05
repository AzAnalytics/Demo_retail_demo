# 🚀 Déployer Le Cockpit sur Google Cloud Run

Objectif : passer de `xxx.streamlit.app` (gratuit, limité) à un vrai service web
pro, **quasi gratuit** (scale à zéro), avec URL HTTPS et domaine perso possible.

---

## Ce dont tu as besoin (une fois)

1. Un compte Google Cloud avec la **facturation activée** (le free tier suffit ;
   sans carte, Cloud Run refuse de créer le service).
2. La CLI **gcloud** installée : https://cloud.google.com/sdk/docs/install
3. Un **projet** GCP (ex. `le-cockpit`).

```bash
# Connexion + sélection du projet
gcloud auth login
gcloud config set project TON_PROJECT_ID

# Activer les services nécessaires (une fois)
gcloud services enable run.googleapis.com cloudbuild.googleapis.com
```

---

## Déploiement (à relancer à chaque mise à jour)

Depuis le dossier du projet :

```bash
cd "/Volumes/Lexar/cerveau/01 - Projets/Démo Retail (projet clé)"

gcloud run deploy le-cockpit \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --session-affinity \
  --port 8080 \
  --memory 512Mi \
  --min-instances 0 \
  --max-instances 2
```

Détails importants :

- `--source .` : Cloud Run **build l'image à partir du Dockerfile** tout seul,
  pas besoin de Docker installé en local.
- `--session-affinity` : **indispensable** pour Streamlit (il utilise des
  websockets ; l'affinité garde l'utilisateur sur la même instance).
- `--min-instances 0` : **scale à zéro = le moins cher** (tu ne paies rien quand
  personne n'utilise l'app). Contrepartie : cold start de ~2–3 s au 1er accès.
  Si tu veux zéro attente pour une démo importante, mets `--min-instances 1`
  (petit coût mensuel, l'app reste chaude).
- `--region europe-west1` : Belgique, proche de la France (faible latence).

À la fin, la commande affiche l'URL : `https://le-cockpit-xxxxx.run.app`
C'est ton service web. Le client l'ouvre → logo animé → dashboard.

---

## Coût attendu

Avec `--min-instances 0`, le free tier Cloud Run (2 M requêtes/mois, temps CPU
offert) couvre une démo et les premiers clients : en pratique **~0 €/mois**.
Tu ne paies que si le trafic devient important, ou si tu forces `min-instances 1`
(quelques euros/mois pour rester toujours chaud).

---

## Domaine perso (optionnel, plus tard)

Pour `https://cockpit.ton-domaine.fr` au lieu de l'URL `run.app` :

```bash
gcloud beta run domain-mappings create \
  --service le-cockpit \
  --domain cockpit.ton-domaine.fr \
  --region europe-west1
```

Puis ajoute l'enregistrement DNS indiqué chez ton registrar (OVH, Gandi…).
Il te faut posséder un nom de domaine (~10 €/an). Le HTTPS est automatique.

---

## Variables / secrets sur Cloud Run

Ne mets jamais tes secrets dans le code. Passe-les à Cloud Run :

```bash
gcloud run services update le-cockpit --region europe-west1 \
  --set-env-vars COCKPIT_ACCESS_PASSWORD=ton_mot_de_passe
```

`config.py` les lira automatiquement (même mécanisme que ton `.env` local).

---

## Restreindre l'accès (deux approches)

- **Simple** : garder `--allow-unauthenticated` et ajouter un écran de mot de
  passe dans l'app (via `config.ACCESS_PASSWORD` — je peux te le coder).
- **Fort** : retirer `--allow-unauthenticated` et gérer l'accès via Google IAM
  (chaque client identifié par son compte Google). Plus verrouillé, un peu plus
  de mise en place.

---

## Mettre à jour l'app plus tard

Tu modifies ton code → tu relances **une seule commande** :

```bash
gcloud run deploy le-cockpit --source . --region europe-west1 --session-affinity --allow-unauthenticated
```

Nouvelle version en ligne en ~1 min, même URL.
