"""
permissions.py — qui a le droit de voir quelles lignes
========================================================
L'équivalent du RLS de Power BI : chaque personne ouvre le même tableau de
bord et n'y voit que son périmètre. Le responsable de Toulouse voit Toulouse,
le commercial voit ses clients, le dirigeant voit tout.

Trois niveaux existent, et il faut savoir lequel on vend :

  1. **Dans l'écran** : on cache des graphiques. Ce n'est PAS de la sécurité,
     les données sont quand même chargées. À ne jamais présenter comme telle.
  2. **Dans l'application** (ce module) : les lignes hors périmètre sont
     retirées juste après la lecture, avant tout calcul et avant la prévision.
     C'est le niveau qui convient à une PME, et c'est ce que fait Power BI.
  3. **Dans la base** : la requête ne ramène que les lignes autorisées
     (`filtre_sql`), ou Oracle le fait lui-même (VPD, comptes par personne).
     C'est le plus solide, et ça se décide avec l'informatique du client.

Le niveau 2 est en place ici, et le niveau 3 est préparé : `filtre_sql` produit
la clause `WHERE` correspondant au profil, à coller dans la requête.

Les profils vivent dans un fichier JSON **non versionné** (`profils.json`) :

    {
      "profils": [
        {"identifiant": "direction", "nom": "Direction", "role": "direction",
         "empreinte": "pbkdf2_sha256$..."},
        {"identifiant": "toulouse", "nom": "Boutique Toulouse",
         "role": "magasin", "magasins": ["Toulouse"],
         "empreinte": "pbkdf2_sha256$..."}
      ]
    }

Fabriquer une empreinte (le mot de passe n'est jamais stocké en clair) :

    python permissions.py "le mot de passe"
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

FICHIER_PROFILS = Path(__file__).with_name("profils.json")

ITERATIONS = 240_000          # coût de calcul d'une empreinte, volontairement élevé
ALGORITHME = "pbkdf2_sha256"

# Les colonnes sur lesquelles un périmètre peut porter, et le champ du profil
# qui les restreint. Ajouter une dimension ici suffit à l'activer partout.
DIMENSIONS = {
    "magasins": "magasin",
    "categories": "categorie",
    "clients": "client",
}

# ------------------------------------------------------------------
# Les droits (ce qu'on a le droit de FAIRE) et les rôles qui les portent
# ------------------------------------------------------------------
# À ne pas confondre avec le périmètre, qui dit ce qu'on a le droit de VOIR.
# Les deux se combinent : un contributeur restreint à Toulouse exporte les
# données de Toulouse, et rien d'autre.
#
# Un droit n'existe que s'il correspond à une action réelle de l'écran. On
# n'invente pas de rôle décoratif : chaque ligne ci-dessous change ce qui
# s'affiche.
DROITS = {
    "voir": "ouvrir le tableau de bord sur son périmètre",
    "exporter": "télécharger les données de son périmètre",
    "reglages": "ajuster l'objectif de croissance et le seuil d'alerte",
    "diagnostic": "voir l'état technique : source, fraîcheur, volumétrie",
    "administrer": "voir les comptes et fabriquer un mot de passe",
}

ROLES: dict[str, set[str]] = {
    "lecteur": {"voir"},
    "contributeur": {"voir", "exporter", "reglages"},
    "admin": set(DROITS),
}
ROLE_PAR_DEFAUT = "lecteur"


# ------------------------------------------------------------------
# Les mots de passe
# ------------------------------------------------------------------
def empreinte(mot_de_passe: str, sel: bytes | None = None,
              iterations: int = ITERATIONS) -> str:
    """Transforme un mot de passe en empreinte stockable.

    Format : `pbkdf2_sha256$iterations$sel$empreinte`. On ne stocke jamais le
    mot de passe : si le fichier de profils fuite, il ne donne rien.
    """
    sel = sel or secrets.token_bytes(16)
    brut = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), sel, iterations)
    return "$".join([ALGORITHME, str(iterations),
                     base64.b64encode(sel).decode(), base64.b64encode(brut).decode()])


def verifie_mot_de_passe(mot_de_passe: str, stockee: str) -> bool:
    """Comparaison à temps constant contre une empreinte stockée."""
    try:
        algo, iterations, sel, attendu = stockee.split("$")
        if algo != ALGORITHME:
            return False
        calcule = hashlib.pbkdf2_hmac(
            "sha256", mot_de_passe.encode("utf-8"),
            base64.b64decode(sel), int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calcule, base64.b64decode(attendu))


# ------------------------------------------------------------------
# Les profils
# ------------------------------------------------------------------
@dataclass
class Profil:
    """Une personne et son périmètre. Une liste vide veut dire : tout voir."""

    identifiant: str
    nom: str = ""
    role: str = ROLE_PAR_DEFAUT
    magasins: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    clients: list[str] = field(default_factory=list)
    empreinte: str = ""

    @property
    def droits(self) -> set[str]:
        """Ce que ce rôle autorise. Un rôle inconnu n'autorise rien."""
        return set(ROLES.get(self.role, set()))

    def peut(self, droit: str) -> bool:
        """Cette personne a-t-elle le droit de faire cela ?

        Appelé avant d'afficher une action, jamais après : un bouton qu'on
        affiche puis qu'on refuse est une mauvaise expérience, et un bouton
        qu'on cache sans vérifier côté serveur n'est pas une protection. Ici
        l'écran est calculé sur le serveur : ne pas l'afficher, c'est ne pas
        l'offrir.
        """
        return droit in self.droits

    @property
    def voit_tout(self) -> bool:
        return not (self.magasins or self.categories or self.clients)

    def resume_role(self) -> str:
        """« Contributeur, peut exporter et régler les seuils »."""
        actions = [DROITS[d] for d in sorted(self.droits) if d != "voir"]
        if not actions:
            return f"{self.role.capitalize()}, lecture seule."
        return f"{self.role.capitalize()}, peut {', '.join(actions)}."

    def resume(self) -> str:
        """La phrase affichée à l'écran : chacun sait ce qu'il regarde."""
        if self.voit_tout:
            return "Périmètre : l'ensemble de l'activité."
        morceaux = []
        for champ, libelle in (("magasins", "magasin"), ("categories", "catégorie"),
                               ("clients", "client")):
            valeurs = getattr(self, champ)
            if valeurs:
                pluriel = "s" if len(valeurs) > 1 else ""
                morceaux.append(f"{libelle}{pluriel} : {', '.join(valeurs)}")
        return "Périmètre, " + " ; ".join(morceaux) + "."


def charge_profils(chemin: str | Path | None = None) -> dict[str, Profil]:
    """Lit le fichier de profils. Fichier absent : aucun profil, donc pas de RLS.

    Le chemin peut être imposé par `COCKPIT_PROFILS` : un client peut vouloir
    ranger ses profils ailleurs que dans le dossier du code.
    """
    chemin = Path(chemin or os.environ.get("COCKPIT_PROFILS") or FICHIER_PROFILS)
    if not chemin.exists():
        return {}
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    profils = {}
    for brut in donnees.get("profils", []):
        inconnues = set(brut) - {"identifiant", "nom", "role", "magasins",
                                 "categories", "clients", "empreinte"}
        if inconnues:
            raise ValueError(f"clé(s) inconnue(s) dans profils.json : "
                             f"{', '.join(sorted(inconnues))}")
        profil = Profil(**brut)
        if not profil.identifiant:
            raise ValueError("un profil sans identifiant")
        if profil.role not in ROLES:
            raise ValueError(
                f"rôle inconnu pour {profil.identifiant} : {profil.role} "
                f"(connus : {', '.join(sorted(ROLES))})")
        profils[profil.identifiant] = profil
    return profils


def authentifie(identifiant: str, mot_de_passe: str,
                profils: dict[str, Profil]) -> Profil | None:
    """Renvoie le profil si le couple est bon, None sinon.

    Un identifiant inconnu coûte le même temps qu'un mot de passe faux : on ne
    renseigne pas sur l'existence d'un compte.
    """
    profil = profils.get(identifiant)
    reference = profil.empreinte if profil else empreinte("inexistant", iterations=1)
    valide = verifie_mot_de_passe(mot_de_passe, reference)
    return profil if (profil and valide) else None


# ------------------------------------------------------------------
# Appliquer le périmètre
# ------------------------------------------------------------------
def applique(df: pd.DataFrame, profil: Profil | None) -> pd.DataFrame:
    """Retire les lignes hors périmètre, avant tout calcul.

    À appeler juste après la lecture des données, pas au moment de l'affichage :
    un graphique caché n'est pas une protection, et la prévision travaillerait
    sinon sur des lignes que la personne n'a pas le droit de voir.
    """
    if profil is None or profil.voit_tout:
        return df
    sortie = df
    for champ, colonne in DIMENSIONS.items():
        valeurs = getattr(profil, champ)
        if valeurs and colonne in sortie.columns:
            sortie = sortie[sortie[colonne].isin(valeurs)]
    return sortie.reset_index(drop=True)


def filtre_sql(profil: Profil | None,
               colonnes: dict[str, str] | None = None) -> tuple[str, list[Any]]:
    """La clause WHERE correspondant au périmètre, et ses paramètres.

    Sert à pousser la restriction **dans la base** : les lignes interdites ne
    sortent alors jamais du serveur du client. Les valeurs passent en
    paramètres, jamais concaténées dans le texte de la requête.
    """
    if profil is None or profil.voit_tout:
        return "", []
    colonnes = colonnes or {c: c for c in DIMENSIONS.values()}
    clauses, parametres = [], []
    for champ, colonne in DIMENSIONS.items():
        valeurs = getattr(profil, champ)
        if not valeurs:
            continue
        nom = colonnes.get(colonne, colonne)
        marques = ", ".join(["?"] * len(valeurs))
        clauses.append(f"{nom} IN ({marques})")
        parametres.extend(valeurs)
    return " AND ".join(clauses), parametres


if __name__ == "__main__":        # python permissions.py "mot de passe"
    import sys

    if len(sys.argv) != 2:
        print('Usage : python permissions.py "le mot de passe"')
        raise SystemExit(1)
    print(empreinte(sys.argv[1]))
