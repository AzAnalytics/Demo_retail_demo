"""
config.py — Configuration centralisée du Cockpit
=================================================
Toutes les variables ajustables (et les éventuels secrets) sont lues ICI, depuis
les variables d'environnement (ou un fichier .env local NON versionné), avec des
valeurs par défaut sûres. Aucune valeur secrète n'est écrite en dur dans le code.

Ordre de priorité pour chaque variable :
  1. variable d'environnement (ex. export COCKPIT_DATA_FILE=...)
  2. fichier .env à la racine du projet (non versionné, cf. .env.example)
  3. valeur par défaut ci-dessous

=> Pour ajouter un secret plus tard (clé API, mot de passe, URL de base de
   données), ajoute simplement une ligne ici via _get("NOM", "") et mets la vraie
   valeur dans ton .env local. Elle ne partira jamais sur GitHub.
"""
from __future__ import annotations
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """Charge un .env minimal (clé=valeur) sans dépendance externe."""
    if not path.exists():
        return
    for ligne in path.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, val = ligne.split("=", 1)
        os.environ.setdefault(cle.strip(), val.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")


def _get(nom: str, defaut: str = "") -> str:
    return os.environ.get(nom, defaut)


# ------------------------------------------------------------------
# Variables du dashboard (ajustables sans toucher au code)
# ------------------------------------------------------------------
# Fichier de données : pointe vers un autre CSV sans modifier app.py
DATA_FILE = BASE_DIR / _get("COCKPIT_DATA_FILE", "ventes_maison_lauret.csv")

# Paramètres métier
OBJECTIF_CROISSANCE = float(_get("COCKPIT_OBJECTIF_CROISSANCE", "1.08"))  # +8 % vs N-1
SEUIL_ALERTE = float(_get("COCKPIT_SEUIL_ALERTE", "10"))                  # % de variation
HORIZON_PREVISION = int(_get("COCKPIT_HORIZON_PREVISION", "12"))          # mois

# TVA : les prix du fichier de caisse sont des prix boutique, donc TTC. Tout ce
# qui est affiché (chiffre d'affaires, marge, panier moyen) est ramené hors
# taxes, parce que c'est la seule base dont parlent un dirigeant et son
# expert-comptable. Le coût d'achat, lui, est déjà hors taxes : le commerçant
# récupère la TVA qu'il paie à ses fournisseurs.
# Mettre 0 si le fichier d'un client contient déjà des prix hors taxes.
TAUX_TVA = float(_get("COCKPIT_TAUX_TVA", "0.20"))

# ------------------------------------------------------------------
# D'où viennent les ventes (voir source_donnees.py et BASES-DE-DONNEES.md)
# ------------------------------------------------------------------
# csv (défaut) | excel | sqlite | oracle | odbc | postgres | sqlserver | snowflake
SOURCE = _get("COCKPIT_SOURCE", "csv")

# La requête SQL qui renvoie les colonnes du Cockpit. À écrire une fois par
# client, et à faire relire par son informaticien : c'est le contrat.
SOURCE_REQUETE = _get("COCKPIT_SOURCE_REQUETE", "")

# Les identifiants ne sont jamais écrits ici : ils viennent de l'environnement
# ou du fichier .env local, qui n'est pas versionné.
_PARAMETRES_PAR_SOURCE = {
    "sqlite": {"chemin": _get("COCKPIT_DB_FICHIER", "")},
    "oracle": {"utilisateur": _get("COCKPIT_DB_UTILISATEUR", ""),
               "mot_de_passe": _get("COCKPIT_DB_MOTDEPASSE", ""),
               "dsn": _get("COCKPIT_DB_DSN", "")},
    "odbc": {"chaine": _get("COCKPIT_DB_CHAINE", "")},
    "postgres": {"url": _get("COCKPIT_DB_URL", "")},
    "snowflake": {"utilisateur": _get("COCKPIT_SF_UTILISATEUR", ""),
                  "compte": _get("COCKPIT_SF_COMPTE", ""),
                  "entrepot": _get("COCKPIT_SF_ENTREPOT", ""),
                  "base": _get("COCKPIT_SF_BASE", ""),
                  "schema": _get("COCKPIT_SF_SCHEMA", "PUBLIC"),
                  "role": _get("COCKPIT_SF_ROLE", "") or None,
                  "password": _get("COCKPIT_SF_MOTDEPASSE", "")},
    "sqlserver": {"chaine": _get("COCKPIT_DB_CHAINE", "")},
}
SOURCE_PARAMETRES = _PARAMETRES_PAR_SOURCE.get(SOURCE, {})

# Ce que l'application lit dans Snowflake : une vue sécurisée, pas la table.
# La vue filtre déjà sur le rôle Snowflake connecté (snowflake/02_securite.sql).
# Vide : l'application se rabat sur le fichier livré avec le dépôt.
TABLE_SNOWFLAKE = _get("COCKPIT_TABLE_SNOWFLAKE",
                       "MAISON_LAURET.VENTES.VENTES_PAR_ROLE")

# Export des données : désactivé par défaut. Sur une vitrine, un bouton qui
# renvoie vers Excel contredit la promesse du produit, et personne ne
# télécharge les ventes d'une boutique fictive. Chez un client, on le met à 1 :
# il devient alors visible pour les profils qui ont le droit « exporter ».
EXPORT_AUTORISE = _get("COCKPIT_EXPORT", "0") not in ("0", "false", "False", "")

# Démonstration : refabriquer le fichier de ventes quand il devient périmé.
# À mettre à 0 le jour où l'écran tourne sur les vraies données d'un client :
# on ne régénère évidemment jamais les données de quelqu'un.
DEMO_AUTO = _get("COCKPIT_DEMO_AUTO", "1") not in ("0", "false", "False", "")

# Vidéo du splash (logo animé Gemini)
SPLASH_VIDEO = BASE_DIR / "assets" / _get("COCKPIT_SPLASH_VIDEO", "cockpit_logo.mp4")

# ------------------------------------------------------------------
# Emplacement pour de futurs secrets (laissés vides ici, remplis dans .env)
# ------------------------------------------------------------------
# Exemple : mot de passe d'accès si tu ajoutes un jour un écran de connexion
ACCESS_PASSWORD = _get("COCKPIT_ACCESS_PASSWORD", "")   # vide = pas de protection
