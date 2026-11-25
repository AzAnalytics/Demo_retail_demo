"""
comptes.py — les personnes et leurs droits, rangés dans l'entrepôt
====================================================================
Un dirigeant n'édite pas un fichier JSON pour donner un accès à sa
responsable de magasin. Les comptes vivent donc dans une table Snowflake,
et l'administrateur les gère depuis l'écran du Cockpit.

Ce qui est stocké : l'identifiant, le nom, le rôle, le périmètre, et
**l'empreinte** du mot de passe (PBKDF2, 240 000 tours). Jamais le mot de
passe lui-même : même avec un accès complet à l'entrepôt, personne ne peut
le relire.

Hors de Snowflake (poste local, Streamlit Cloud), le Cockpit retombe sur
`profils.json`, qui reste la voie de secours.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

import permissions as perm
from source_donnees import _litteral, session_snowflake

TABLE_COMPTES = "MAISON_LAURET.VENTES.COMPTES"

DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    IDENTIFIANT VARCHAR NOT NULL,
    NOM         VARCHAR,
    ROLE        VARCHAR,
    MAGASINS    VARCHAR,
    CATEGORIES  VARCHAR,
    EMPREINTE   VARCHAR,
    ACTIF       BOOLEAN DEFAULT TRUE,
    CREE_LE     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
"""

REQUETE_LISTE = """
SELECT IDENTIFIANT AS "identifiant",
       NOM         AS "nom",
       ROLE        AS "role",
       MAGASINS    AS "magasins",
       CATEGORIES  AS "categories",
       EMPREINTE   AS "empreinte",
       ACTIF       AS "actif"
FROM {table}
ORDER BY IDENTIFIANT
"""


class CompteInvalide(ValueError):
    """La demande ne peut pas être exécutée, et on dit pourquoi en français."""


# ------------------------------------------------------------------
# Traduction entre la table et les profils du Cockpit
# ------------------------------------------------------------------
def _liste(valeur: Any) -> list[str]:
    """« Toulouse, Auch » -> ['Toulouse', 'Auch']. Vide veut dire : tout voir."""
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return []
    return [morceau.strip() for morceau in str(valeur).split(",") if morceau.strip()]


def profils_depuis_lignes(lignes: list[dict]) -> dict[str, perm.Profil]:
    """Les lignes de la table deviennent les profils que l'écran connaît déjà.

    Un compte désactivé n'est pas chargé : il ne peut donc pas se connecter,
    sans qu'on ait eu à supprimer son historique.
    """
    profils: dict[str, perm.Profil] = {}
    for ligne in lignes:
        if not ligne.get("actif", True):
            continue
        identifiant = str(ligne.get("identifiant") or "").strip()
        if not identifiant:
            continue
        profils[identifiant] = perm.Profil(
            identifiant=identifiant,
            nom=str(ligne.get("nom") or ""),
            role=str(ligne.get("role") or perm.ROLE_PAR_DEFAUT),
            magasins=_liste(ligne.get("magasins")),
            categories=_liste(ligne.get("categories")),
            empreinte=str(ligne.get("empreinte") or ""),
        )
    return profils


# ------------------------------------------------------------------
# Lire
# ------------------------------------------------------------------
def assure_table(session=None, table: str = TABLE_COMPTES) -> None:
    """Crée la table si elle n'existe pas. Sans effet si elle est déjà là."""
    session = session or session_snowflake()
    if session is None:
        raise CompteInvalide("hors de Snowflake, les comptes restent dans profils.json")
    session.sql(DDL.format(table=table)).collect()


def lire(session=None, table: str = TABLE_COMPTES) -> list[dict]:
    """Toutes les lignes de la table, désactivés compris (pour l'écran d'admin)."""
    session = session or session_snowflake()
    if session is None:
        return []
    df = session.sql(REQUETE_LISTE.format(table=table)).to_pandas()
    return df.to_dict("records")


def sème_les_comptes_de_demonstration(profils: dict[str, perm.Profil],
                                      session=None,
                                      table: str = TABLE_COMPTES) -> int:
    """Recopie les profils du fichier dans la table, une seule fois.

    Sans cela, la première personne créée depuis l'écran ferait disparaître
    les comptes de démonstration, et l'administrateur se retrouverait dehors.
    Renvoie le nombre de comptes semés.
    """
    if not profils:
        return 0
    session = session or session_snowflake()
    if session is None or lire(session, table):
        return 0
    for profil in profils.values():
        _insere(session, table, profil.identifiant, profil.nom, profil.role,
                profil.magasins, profil.categories, profil.empreinte)
    return len(profils)


# ------------------------------------------------------------------
# Écrire
# ------------------------------------------------------------------
def _insere(session, table, identifiant, nom, role, magasins, categories,
            empreinte) -> None:
    session.sql(
        f"INSERT INTO {table} "
        "(IDENTIFIANT, NOM, ROLE, MAGASINS, CATEGORIES, EMPREINTE, ACTIF) VALUES ("
        f"{_litteral(identifiant)}, {_litteral(nom)}, {_litteral(role)}, "
        f"{_litteral(', '.join(magasins))}, {_litteral(', '.join(categories))}, "
        f"{_litteral(empreinte)}, TRUE)"
    ).collect()


def ajoute(identifiant: str, nom: str, role: str, mot_de_passe: str,
           magasins: list[str] | None = None,
           categories: list[str] | None = None,
           session=None, table: str = TABLE_COMPTES) -> None:
    """Crée une personne. Le mot de passe n'est jamais stocké, seulement son empreinte."""
    identifiant = (identifiant or "").strip().lower()
    if not identifiant:
        raise CompteInvalide("il faut un identifiant")
    if " " in identifiant:
        raise CompteInvalide("l'identifiant ne doit pas contenir d'espace")
    if role not in perm.ROLES:
        raise CompteInvalide(f"rôle inconnu : {role}")
    if len(mot_de_passe or "") < 8:
        raise CompteInvalide("le mot de passe doit faire au moins huit caractères")

    session = session or session_snowflake()
    if session is None:
        raise CompteInvalide("hors de Snowflake, les comptes restent dans profils.json")
    if any(l["identifiant"] == identifiant for l in lire(session, table)):
        raise CompteInvalide(f"l'identifiant « {identifiant} » existe déjà")

    _insere(session, table, identifiant, nom or identifiant, role,
            magasins or [], categories or [], perm.empreinte(mot_de_passe))


def change_mot_de_passe(identifiant: str, mot_de_passe: str, session=None,
                        table: str = TABLE_COMPTES) -> None:
    """Remplace l'empreinte. Sert aussi quand quelqu'un a oublié son mot de passe."""
    if len(mot_de_passe or "") < 8:
        raise CompteInvalide("le mot de passe doit faire au moins huit caractères")
    session = session or session_snowflake()
    if session is None:
        raise CompteInvalide("hors de Snowflake, les comptes restent dans profils.json")
    session.sql(
        f"UPDATE {table} SET EMPREINTE = {_litteral(perm.empreinte(mot_de_passe))} "
        f"WHERE IDENTIFIANT = {_litteral(identifiant)}"
    ).collect()


def modifie(identifiant: str, role: str | None = None,
            magasins: list[str] | None = None, session=None,
            table: str = TABLE_COMPTES) -> None:
    """Change le rôle ou le périmètre d'une personne déjà créée."""
    if role is not None and role not in perm.ROLES:
        raise CompteInvalide(f"rôle inconnu : {role}")
    session = session or session_snowflake()
    if session is None:
        raise CompteInvalide("hors de Snowflake, les comptes restent dans profils.json")
    if role is not None and _dernier_admin(identifiant, session, table) and role != "admin":
        raise CompteInvalide("c'est le dernier administrateur : on ne retire pas son rôle")
    morceaux = []
    if role is not None:
        morceaux.append(f"ROLE = {_litteral(role)}")
    if magasins is not None:
        morceaux.append(f"MAGASINS = {_litteral(', '.join(magasins))}")
    if not morceaux:
        return
    session.sql(f"UPDATE {table} SET {', '.join(morceaux)} "
                f"WHERE IDENTIFIANT = {_litteral(identifiant)}").collect()


def _dernier_admin(identifiant: str, session, table: str) -> bool:
    """Cette personne est-elle le seul administrateur actif qui reste ?"""
    admins = [l["identifiant"] for l in lire(session, table)
              if l.get("role") == "admin" and l.get("actif", True)]
    return admins == [identifiant]


def active(identifiant: str, actif: bool, session=None,
           table: str = TABLE_COMPTES) -> None:
    """Coupe ou rend l'accès, sans rien effacer.

    C'est ce qu'on fait quand quelqu'un part : on désactive, on garde la trace.
    """
    session = session or session_snowflake()
    if session is None:
        raise CompteInvalide("hors de Snowflake, les comptes restent dans profils.json")
    if not actif and _dernier_admin(identifiant, session, table):
        raise CompteInvalide("c'est le dernier administrateur : on ne le désactive pas")
    session.sql(f"UPDATE {table} SET ACTIF = {'TRUE' if actif else 'FALSE'} "
                f"WHERE IDENTIFIANT = {_litteral(identifiant)}").collect()


def supprime(identifiant: str, session=None, table: str = TABLE_COMPTES) -> None:
    """Efface la ligne. Préférer `active(..., False)` dans la vraie vie."""
    session = session or session_snowflake()
    if session is None:
        raise CompteInvalide("hors de Snowflake, les comptes restent dans profils.json")
    if _dernier_admin(identifiant, session, table):
        raise CompteInvalide("c'est le dernier administrateur : on ne le supprime pas")
    session.sql(f"DELETE FROM {table} "
                f"WHERE IDENTIFIANT = {_litteral(identifiant)}").collect()
