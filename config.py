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

# Vidéo du splash (logo animé Gemini)
SPLASH_VIDEO = BASE_DIR / "assets" / _get("COCKPIT_SPLASH_VIDEO", "cockpit_logo.mp4")

# ------------------------------------------------------------------
# Emplacement pour de futurs secrets (laissés vides ici, remplis dans .env)
# ------------------------------------------------------------------
# Exemple : mot de passe d'accès si tu ajoutes un jour un écran de connexion
ACCESS_PASSWORD = _get("COCKPIT_ACCESS_PASSWORD", "")   # vide = pas de protection
