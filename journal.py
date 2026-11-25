"""
journal.py — qui s'est connecté, quand, et depuis quel compte
===============================================================
Trois lignes suffisent à répondre aux questions qu'une direction finit
toujours par poser : « qui a ouvert le Cockpit ce matin ? », « cette
personne est partie, s'est-elle reconnectée depuis ? », « est-ce que
quelqu'un essaie des mots de passe ? »

Le journal vit dans l'entrepôt, à côté des ventes et des comptes. On
enregistre l'événement, l'identifiant **saisi** (même quand il n'existe
pas, c'est justement ce qu'on veut voir) et le rôle quand la connexion a
réussi. Jamais le mot de passe, même faux : une frappe malheureuse dans le
champ identifiant ne doit pas laisser un mot de passe en clair dans une
table que des gens consultent.

Hors de Snowflake, l'écriture ne fait rien : la vitrine publique n'a pas
de journal, et c'est normal.
"""
from __future__ import annotations

import pandas as pd

from source_donnees import _litteral, session_snowflake

TABLE_JOURNAL = "MAISON_LAURET.VENTES.CONNEXIONS"

CONNEXION = "connexion"
ECHEC = "échec"
DECONNEXION = "déconnexion"

DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    HORODATAGE  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    IDENTIFIANT VARCHAR,
    EVENEMENT   VARCHAR,
    ROLE        VARCHAR
)
"""

REQUETE_LISTE = """
SELECT HORODATAGE  AS "horodatage",
       IDENTIFIANT AS "identifiant",
       EVENEMENT   AS "evenement",
       ROLE        AS "role"
FROM {table}
ORDER BY HORODATAGE DESC
LIMIT {limite}
"""

# Le résumé est calculé par l'entrepôt : une ligne par personne, c'est tout
# ce qui traverse le réseau, même si le journal compte un million de lignes.
REQUETE_RESUME = """
SELECT IDENTIFIANT                                   AS "identifiant",
       MAX(CASE WHEN EVENEMENT = '{connexion}'
                THEN HORODATAGE END)                 AS "derniere_connexion",
       COUNT_IF(EVENEMENT = '{connexion}')           AS "connexions",
       COUNT_IF(EVENEMENT = '{echec}')               AS "echecs"
FROM {table}
GROUP BY IDENTIFIANT
ORDER BY "derniere_connexion" DESC NULLS LAST
"""


def assure_table(session=None, table: str = TABLE_JOURNAL) -> None:
    """Crée la table si elle n'existe pas. Sans effet ensuite."""
    session = session or session_snowflake()
    if session is None:
        return
    session.sql(DDL.format(table=table)).collect()


def enregistre(identifiant: str, evenement: str, role: str = "",
               session=None, table: str = TABLE_JOURNAL) -> bool:
    """Écrit une ligne. Renvoie False si l'écriture n'a pas eu lieu.

    Le journal ne doit jamais empêcher quelqu'un de travailler : si
    l'écriture échoue, on le dit au retour, mais on ne lève rien.
    """
    session = session or session_snowflake()
    if session is None:
        return False
    # On tronque : un identifiant de trois cents caractères est une tentative,
    # pas une faute de frappe, et il n'a rien à faire dans un tableau.
    saisi = str(identifiant or "")[:60]
    try:
        session.sql(
            f"INSERT INTO {table} (IDENTIFIANT, EVENEMENT, ROLE) VALUES ("
            f"{_litteral(saisi)}, {_litteral(evenement)}, {_litteral(role or '')})"
        ).collect()
        return True
    except Exception:
        return False


def lire(limite: int = 200, session=None, table: str = TABLE_JOURNAL) -> pd.DataFrame:
    """Les derniers événements, du plus récent au plus ancien."""
    session = session or session_snowflake()
    if session is None:
        return pd.DataFrame()
    return session.sql(
        REQUETE_LISTE.format(table=table, limite=int(limite))
    ).to_pandas()


def resume(session=None, table: str = TABLE_JOURNAL) -> pd.DataFrame:
    """Une ligne par personne : dernière connexion, nombre de connexions, échecs."""
    session = session or session_snowflake()
    if session is None:
        return pd.DataFrame()
    return session.sql(
        REQUETE_RESUME.format(table=table, connexion=CONNEXION, echec=ECHEC)
    ).to_pandas()
