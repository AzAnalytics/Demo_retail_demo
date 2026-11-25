"""
source_donnees.py — d'où viennent les ventes
==============================================
Le Cockpit lit un CSV aujourd'hui, une base Oracle demain, un export mensuel
chez le client d'après. Tout passe par ici, et **rien d'autre ne change** :
l'écran, les calculs et la prévision ne voient qu'un tableau au format du
Cockpit (date, magasin, categorie, produit, quantite, prix_unitaire,
cout_unitaire, ca_ttc).

C'est le seul endroit qui connaît une base de données. C'est aussi ce qui
permet de répondre « oui » quand un dirigeant demande « et si mes données sont
dans notre ERP ? » : on écrit une requête, pas une application.

Trois sources, la même sortie :

    import source_donnees as src

    ventes = src.depuis_csv("ventes_maison_lauret.csv")
    ventes = src.depuis_base(src.connexion_sqlite("ventes.db"), "SELECT ...")
    ventes = src.charge()        # ce que dit config / les secrets

Les identifiants ne sont jamais écrits dans le code : ils viennent de
`.streamlit/secrets.toml` (jamais versionné) ou de variables d'environnement.
Voir `BASES-DE-DONNEES.md`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pandas as pd

# Les colonnes que le reste du Cockpit attend, quelle que soit la source.
COLONNES = ("date", "magasin", "categorie", "produit", "quantite",
            "prix_unitaire", "cout_unitaire", "ca_ttc")


class SourceInvalide(ValueError):
    """La source répond, mais pas avec ce qu'il faut pour calculer."""


# ------------------------------------------------------------------
# Contrôle commun
# ------------------------------------------------------------------
def valide(df: pd.DataFrame, origine: str = "la source") -> pd.DataFrame:
    """Vérifie la forme du tableau, quelle que soit la provenance.

    Une base de données ne protège de rien : une vue modifiée, une colonne
    renommée par l'éditeur de l'ERP, et le tableau de bord afficherait des
    chiffres faux. On contrôle donc à l'entrée, toujours.
    """
    manquantes = [c for c in COLONNES if c not in df.columns]
    if manquantes:
        raise SourceInvalide(
            f"{origine} ne fournit pas : {', '.join(manquantes)}. "
            f"Colonnes reçues : {', '.join(map(str, df.columns))}"
        )
    if df.empty:
        raise SourceInvalide(f"{origine} ne renvoie aucune ligne")

    sortie = df.copy()
    sortie["date"] = pd.to_datetime(sortie["date"], errors="coerce")
    sortie = sortie.dropna(subset=["date"])
    if sortie.empty:
        raise SourceInvalide(f"{origine} ne renvoie aucune date exploitable")
    for colonne in ("quantite", "prix_unitaire", "cout_unitaire", "ca_ttc"):
        sortie[colonne] = pd.to_numeric(sortie[colonne], errors="coerce")
    return sortie.dropna(subset=["quantite", "ca_ttc"]).reset_index(drop=True)


# ------------------------------------------------------------------
# Un fichier
# ------------------------------------------------------------------
def depuis_csv(chemin: str | Path, **options: Any) -> pd.DataFrame:
    """Un export CSV, le point de départ de toutes les missions."""
    return valide(pd.read_csv(chemin, **options), origine=Path(chemin).name)


def depuis_excel(chemin: str | Path, feuille: Any = 0, **options: Any) -> pd.DataFrame:
    """Un classeur Excel, ce que le client envoie le plus souvent au début."""
    return valide(pd.read_excel(chemin, sheet_name=feuille, **options),
                  origine=Path(chemin).name)


# ------------------------------------------------------------------
# Une base de données
# ------------------------------------------------------------------
def depuis_base(connexion: Any, requete: str, parametres: Any = None,
                origine: str = "la base") -> pd.DataFrame:
    """Exécute une requête et renvoie les ventes au format du Cockpit.

    `connexion` est une connexion DBAPI ordinaire (sqlite3, oracledb, psycopg,
    pyodbc...) : aucune dépendance supplémentaire n'est imposée ici, c'est le
    projet qui installe le pilote dont il a besoin.

    La requête doit renvoyer les colonnes du Cockpit, renommées côté SQL
    (`AS`) plutôt que côté Python : la traduction reste lisible par
    l'informaticien du client, qui est souvent celui qui la relira.
    """
    df = pd.read_sql(requete, connexion, params=parametres)
    return valide(df, origine=origine)


def connexion_sqlite(chemin: str | Path) -> Any:
    """Une base locale. Sert aux tests, et à un client qui tient sur un fichier."""
    import sqlite3

    return sqlite3.connect(str(chemin))


def connexion_oracle(utilisateur: str, mot_de_passe: str, dsn: str) -> Any:
    """Oracle en mode « thin » : aucun client Oracle à installer sur la machine.

        pip install oracledb
        dsn = "serveur.client.fr:1521/NOM_DU_SERVICE"

    Demander un compte **en lecture seule** et, si possible, une **vue** dédiée
    côté client : on ne se connecte jamais en écriture à la production de
    quelqu'un, et une vue protège le tableau de bord des changements de schéma.
    """
    import oracledb        # pilote officiel, successeur de cx_Oracle

    return oracledb.connect(user=utilisateur, password=mot_de_passe, dsn=dsn)


def connexion_postgres(url: str) -> Any:
    """PostgreSQL : `pip install psycopg`, url `postgresql://user:mdp@hote/base`."""
    import psycopg

    return psycopg.connect(url)


def connexion_snowflake(utilisateur: str, compte: str, entrepot: str,
                        base: str, schema: str = "PUBLIC",
                        role: str | None = None, **identification: Any) -> Any:
    """Snowflake : `pip install snowflake-connector-python`.

        compte    = l'identifiant de compte, par exemple "xy12345.eu-west-1"
        entrepot  = le warehouse qui exécutera la requête (il démarre tout seul)
        role      = le rôle Snowflake, et c'est lui qui décide des lignes
                    visibles si le client a des row access policies

    L'identification passe en mots-clés : `password=...`, ou `private_key=...`
    pour une clé, ou `authenticator="externalbrowser"` pour un SSO. Rien de
    tout cela n'est écrit dans le code (voir config.py).

    Un entrepôt dimensionné XS suffit largement pour un tableau de bord, et il
    se met en pause tout seul : c'est le poste de coût à surveiller, pas le
    stockage.
    """
    import snowflake.connector

    return snowflake.connector.connect(
        user=utilisateur, account=compte, warehouse=entrepot,
        database=base, schema=schema, role=role, **identification,
    )


def connexion_sqlserver(chaine: str) -> Any:
    """SQL Server : `pip install pyodbc`, avec le pilote ODBC 18 installé."""
    return connexion_odbc(chaine)


def connexion_odbc(chaine: str) -> Any:
    """N'importe quelle source ODBC, avec la chaîne de connexion telle quelle.

    C'est la voie la plus rapide quand une connexion existe déjà sur le poste,
    par exemple celle d'un classeur Excel qui interroge l'ERP : on reprend la
    même chaîne, sans rien redécouvrir du réseau du client.

        pip install pyodbc
        chaine = "DRIVER={Oracle in instantclient_19_5x64};SERVER=...;UID=...;PWD=..."

    Le mot de passe ne s'écrit jamais ici : il arrive par l'environnement
    (voir `config.py` et BASES-DE-DONNEES.md).
    """
    try:
        import pyodbc
    except ImportError as erreur:           # message utile plutôt qu'une trace
        raise SourceInvalide(
            "le pilote ODBC Python n'est pas installé : pip install pyodbc"
        ) from erreur
    return pyodbc.connect(chaine)


# ------------------------------------------------------------------
# Quand l'application tourne DANS Snowflake
# ------------------------------------------------------------------
# La requête qui alimente le Cockpit depuis l'entrepôt. Les alias sont entre
# guillemets pour garder des noms de colonnes en minuscules : Snowflake met
# tout en majuscules sinon, et le reste du code ne reconnaîtrait rien.
REQUETE_TICKETS = """
SELECT DATE_VENTE     AS "date",
       MAGASIN        AS "magasin",
       CATEGORIE      AS "categorie",
       PRODUIT        AS "produit",
       QUANTITE       AS "quantite",
       PRIX_UNITAIRE  AS "prix_unitaire",
       COUT_UNITAIRE  AS "cout_unitaire",
       PAIEMENT       AS "paiement",
       CA_TTC         AS "ca_ttc"
FROM {table}
ORDER BY DATE_VENTE
"""


def session_snowflake():
    """La session de l'application quand elle tourne dans Snowflake, sinon None.

    Aucune connexion à ouvrir ni identifiant à fournir : à l'intérieur de
    Snowflake, l'application hérite de la session de la personne connectée.
    C'est tout l'intérêt, et c'est aussi ce qui fait que les données ne
    sortent jamais de l'entrepôt.
    """
    try:
        from snowflake.snowpark.context import get_active_session

        return get_active_session()
    except Exception:
        return None


def depuis_table_snowflake(table: str, session=None) -> pd.DataFrame:
    """Lit la table de ventes de l'entrepôt et la rend au format du Cockpit."""
    session = session or session_snowflake()
    if session is None:
        raise SourceInvalide("l'application ne tourne pas dans Snowflake")
    df = session.sql(REQUETE_TICKETS.format(table=table)).to_pandas()
    # Snowflake renvoie des décimaux : on repasse en nombres ordinaires.
    for colonne in ("quantite", "prix_unitaire", "cout_unitaire", "ca_ttc"):
        if colonne in df.columns:
            df[colonne] = pd.to_numeric(df[colonne], errors="coerce").astype("float64")
    return valide(df, origine=f"la table {table}")


# ------------------------------------------------------------------
# Ce que la configuration demande
# ------------------------------------------------------------------
# Une requête d'exemple, à adapter au schéma du client. Deux principes :
#   - filtrer sur la période côté SQL (on ne rapatrie pas dix ans de lignes) ;
#   - renommer côté SQL, pour que la correspondance soit lisible par le client.
REQUETE_EXEMPLE = """
SELECT
    v.date_vente        AS date,
    m.libelle           AS magasin,
    f.libelle           AS categorie,
    a.libelle           AS produit,
    l.quantite          AS quantite,
    l.prix_unitaire     AS prix_unitaire,
    a.cout_standard     AS cout_unitaire,
    l.montant_ttc       AS ca_ttc
FROM lignes_vente l
JOIN ventes     v ON v.id = l.vente_id
JOIN magasins   m ON m.id = v.magasin_id
JOIN articles   a ON a.id = l.article_id
JOIN familles   f ON f.id = a.famille_id
WHERE v.date_vente >= :debut
"""

FABRIQUES: dict[str, Callable[..., Any]] = {
    "sqlite": connexion_sqlite,
    "oracle": connexion_oracle,
    "odbc": connexion_odbc,              # reprend une chaîne de connexion existante
    "postgres": connexion_postgres,
    "snowflake": connexion_snowflake,
    "sqlserver": connexion_sqlserver,
}


def charge(configuration: Any = None) -> pd.DataFrame:
    """La source décrite par la configuration : fichier par défaut.

    `configuration` est le module `config` (ou n'importe quel objet qui porte
    les mêmes attributs), pour pouvoir le remplacer dans les tests.
    """
    if configuration is None:
        import config as configuration        # import tardif : les tests le remplacent

    type_source = getattr(configuration, "SOURCE", "csv")
    if type_source == "csv":
        return depuis_csv(configuration.DATA_FILE)
    if type_source == "excel":
        return depuis_excel(configuration.DATA_FILE)

    fabrique = FABRIQUES.get(type_source)
    if fabrique is None:
        raise SourceInvalide(
            f"source inconnue : {type_source} "
            f"(connues : csv, excel, {', '.join(sorted(FABRIQUES))})"
        )
    connexion = fabrique(**getattr(configuration, "SOURCE_PARAMETRES", {}))
    try:
        return depuis_base(connexion, configuration.SOURCE_REQUETE,
                           origine=f"la base {type_source}")
    finally:
        connexion.close()
