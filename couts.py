"""
couts.py — ce que l'entrepôt a coûté, demandé à l'entrepôt lui-même
=====================================================================
Devant une démonstration hébergée dans le cloud, la première question
d'un dirigeant n'est pas « comment c'est fait », c'est « combien ça me
coûtera ». Ce module va chercher la réponse là où elle est exacte : les
vues de facturation de Snowflake, pas une estimation de coin de table.

Trois idées tiennent le module :

  1. **On lit la facturation, pas un compteur maison.**
     `WAREHOUSE_METERING_HISTORY` est ce que Snowflake facture vraiment,
     crédit par crédit, heure par heure. Un compteur écrit par nous
     donnerait un chiffre invérifiable, donc inutile en rendez-vous.
  2. **Des crédits d'abord, des euros ensuite.** Le crédit est la seule
     unité exacte : le prix du crédit dépend du contrat, de la région et
     de l'édition. L'euro est donc une conversion, au prix indiqué dans
     la configuration, et l'écran dit que c'en est une.
  3. **Un refus de droits n'est pas une panne.** Lire la facturation
     demande le privilège MONITOR sur l'entrepôt. Sans lui, le module
     renvoie un message explicite et l'écran continue de fonctionner :
     personne ne doit perdre son tableau de bord parce qu'une vue
     d'administration est fermée.

Hors de Snowflake (vitrine publique, poste local, conteneur Docker), il
n'y a pas d'entrepôt, donc pas de coût : le résumé le dit, et c'est tout.
"""
from __future__ import annotations

import pandas as pd

from source_donnees import _litteral, session_snowflake

# QUERY_HISTORY, côté INFORMATION_SCHEMA, ne garde que sept jours. La
# facturation, elle, remonte à six mois. On ne promet donc pas la même
# profondeur sur les deux chiffres, et on l'écrit à l'écran.
JOURS_ACTIVITE_MAX = 7

REQUETE_CREDITS = """
SELECT TO_DATE(START_TIME)   AS "jour",
       SUM(CREDITS_USED)     AS "credits"
FROM TABLE({prefixe}WAREHOUSE_METERING_HISTORY(
         DATE_RANGE_START => DATEADD(day, -{jours}, CURRENT_DATE()),
         WAREHOUSE_NAME   => {entrepot}))
GROUP BY 1
ORDER BY 1
"""

REQUETE_ACTIVITE = """
SELECT COUNT(*)                                    AS "requetes",
       COALESCE(SUM(TOTAL_ELAPSED_TIME), 0) / 1000 AS "secondes"
FROM TABLE({prefixe}QUERY_HISTORY(
         END_TIME_RANGE_START => DATEADD(day, -{jours}, CURRENT_TIMESTAMP()),
         RESULT_LIMIT => 10000))
WHERE WAREHOUSE_NAME = {entrepot}
"""


REQUETE_PAR_ENTREPOT = """
SELECT WAREHOUSE_NAME    AS "entrepot",
       SUM(CREDITS_USED) AS "credits"
FROM TABLE({prefixe}WAREHOUSE_METERING_HISTORY(
         DATE_RANGE_START => DATEADD(day, -{jours}, CURRENT_DATE())))
GROUP BY 1
HAVING SUM(CREDITS_USED) > 0
ORDER BY 2 DESC
"""

# ------------------------------------------------------------------
# Les prix publics des entrepôts du marché
# ------------------------------------------------------------------
# Relevés à la main sur les pages officielles, avec leur date : un prix de
# cloud bouge, et un tableau non daté finit par faire mentir celui qui le
# montre. Les montants sont des prix catalogue, hors stockage, hors
# remises contractuelles : ils servent à expliquer un modèle de
# facturation, jamais à établir un devis.
RELEVE_TARIFS = "27 novembre 2026"

TARIFS_ENTREPOTS = [
    {
        "entrepot": "Snowflake (Standard)",
        "facturation": "au crédit, à la seconde, minimum 1 minute par réveil",
        "prix": "environ 2,60 $ le crédit en Europe (2,00 $ aux États-Unis) ; "
                "un entrepôt XS brûle 1 crédit par heure allumée",
        "pour_ce_cockpit": "on ne paie que les secondes d'entrepôt allumé, "
                           "mais une page laissée ouverte le tient éveillé",
        "source": "snowflake.com/pricing (prix régionaux : sources secondaires)",
    },
    {
        "entrepot": "Google BigQuery (à la demande)",
        "facturation": "au volume analysé par les requêtes",
        "prix": "6,25 $ le tébioctet analysé, le premier tébioctet du mois "
                "étant gratuit",
        "pour_ce_cockpit": "nos lectures pèsent quelques mégaoctets : elles "
                           "tiennent dans la part gratuite",
        "source": "cloud.google.com/bigquery/pricing",
    },
    {
        "entrepot": "Amazon Redshift Serverless",
        "facturation": "à l'heure de calcul (RPU), minimum 4 RPU et 60 s",
        "prix": "environ 0,375 $ par RPU-heure aux États-Unis, soit à partir "
                "d'environ 1,50 $ l'heure de requêtes ; tarif européen non "
                "publié dans nos sources",
        "pour_ce_cockpit": "une minute facturée par lecture, le reste du "
                           "temps rien",
        "source": "aws.amazon.com/redshift/pricing",
    },
    {
        "entrepot": "Databricks SQL Serverless",
        "facturation": "à l'unité de calcul (DBU), arrêt automatique",
        "prix": "0,70 $ le DBU ; un entrepôt 2X-Small consomme 4 DBU par "
                "heure, soit environ 2,80 $ l'heure",
        "pour_ce_cockpit": "le plus cher à l'heure allumée, mais il s'arrête "
                           "tout seul comme Snowflake",
        "source": "databricks.com/product/pricing",
    },
    {
        "entrepot": "Microsoft Fabric (F2, paiement à l'usage)",
        "facturation": "à la capacité réservée, à la seconde, en pause possible",
        "prix": "0,18 $ par CU-heure aux États-Unis, soit environ 0,36 $ "
                "l'heure pour un F2 ; environ 22 % de plus en Europe de l'Ouest",
        "pour_ce_cockpit": "la capacité se paie même quand personne ne "
                           "regarde, sauf à la mettre en pause",
        "source": "azure.microsoft.com/pricing/details/microsoft-fabric",
    },
]


def tarifs() -> pd.DataFrame:
    """Le comparatif, prêt à afficher, avec ses colonnes en français."""
    return pd.DataFrame(TARIFS_ENTREPOTS).rename(columns={
        "entrepot": "Entrepôt",
        "facturation": "Ce qui est facturé",
        "prix": "Prix public",
        "pour_ce_cockpit": "Pour un écran comme celui-ci",
        "source": "Source",
    })


def par_entrepot(jours: int = 30, session=None, base: str = "",
                 prix_credit: float = 0.0) -> pd.DataFrame:
    """Les crédits consommés par chaque entrepôt du compte, sur la période.

    Un tableau vide si la facturation n'est pas lisible depuis ce rôle :
    comme partout ici, un refus de droits ne casse rien.
    """
    session = session or session_snowflake()
    if session is None:
        return pd.DataFrame()
    requete = REQUETE_PAR_ENTREPOT.format(prefixe=prefixe_schema(base),
                                          jours=max(1, int(jours)))
    try:
        lignes = session.sql(requete).to_pandas()
    except Exception:
        return pd.DataFrame()
    if lignes.empty:
        return lignes
    lignes["credits"] = lignes["credits"].map(lambda v: round(_nombre(v), 3))
    if prix_credit:
        lignes["euros"] = lignes["credits"].map(
            lambda c: en_euros(c, prix_credit))
    return lignes


def base_de(objet: str) -> str:
    """La base d'un nom qualifié.

    `MAISON_LAURET.VENTES.TICKETS` donne `MAISON_LAURET`. Un nom non
    qualifié ne donne rien : on se rabattra sur la base courante de la
    session, qui est la bonne dans l'application.
    """
    morceaux = [m for m in str(objet or "").split(".") if m]
    return morceaux[0] if len(morceaux) >= 3 else ""


def prefixe_schema(base: str = "") -> str:
    """Le préfixe des fonctions d'information, qualifié quand on sait où chercher."""
    return f"{base}.INFORMATION_SCHEMA." if base else "INFORMATION_SCHEMA."


def entrepot_actif(session=None) -> str:
    """Le nom de l'entrepôt qui exécute les requêtes, demandé à la session."""
    session = session or session_snowflake()
    if session is None:
        return ""
    try:
        reponse = session.sql("SELECT CURRENT_WAREHOUSE() AS \"entrepot\"").to_pandas()
        if reponse.empty:
            return ""
        valeur = reponse["entrepot"].iloc[0]
        return "" if valeur is None else str(valeur)
    except Exception:
        return ""


def requete_credits(entrepot: str, jours: int = 30, base: str = "") -> str:
    """La requête de facturation, telle qu'elle part dans l'entrepôt."""
    return REQUETE_CREDITS.format(prefixe=prefixe_schema(base),
                                  jours=max(1, int(jours)),
                                  entrepot=_litteral(entrepot)).strip()


def requete_activite(entrepot: str, jours: int = JOURS_ACTIVITE_MAX,
                     base: str = "") -> str:
    """La requête d'activité. Au-delà de sept jours, Snowflake n'a plus rien à dire."""
    return REQUETE_ACTIVITE.format(prefixe=prefixe_schema(base),
                                   jours=min(JOURS_ACTIVITE_MAX, max(1, int(jours))),
                                   entrepot=_litteral(entrepot)).strip()


def en_euros(credits: float, prix_credit: float) -> float:
    """La conversion, au prix du crédit indiqué dans la configuration."""
    try:
        return round(float(credits) * float(prix_credit), 2)
    except (TypeError, ValueError):
        return 0.0


def _nombre(valeur, defaut: float = 0.0) -> float:
    """Snowflake renvoie des décimaux ; l'écran veut des nombres ordinaires."""
    try:
        if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
            return defaut
        return float(valeur)
    except (TypeError, ValueError):
        return defaut


def resume(jours: int = 30, session=None, entrepot: str = "",
           base: str = "") -> dict:
    """Ce que l'entrepôt a coûté sur la période, et ce qu'il a fait pour ça.

    Renvoie toujours un dictionnaire. En cas d'absence de droits, de
    session ou d'entrepôt, la clé `erreur` porte la raison en français :
    l'appelant affiche la phrase au lieu de planter.
    """
    session = session or session_snowflake()
    if session is None:
        return {"erreur": "l'application ne tourne pas dans Snowflake, "
                          "il n'y a donc pas d'entrepôt à facturer"}
    nom = entrepot or entrepot_actif(session)
    if not nom:
        return {"erreur": "aucun entrepôt actif sur cette session"}

    sortie: dict = {"entrepot": nom, "jours": max(1, int(jours)),
                    "jours_activite": min(JOURS_ACTIVITE_MAX, max(1, int(jours)))}
    try:
        facture = session.sql(requete_credits(nom, jours, base)).to_pandas()
    except Exception as erreur:
        return {"entrepot": nom,
                "erreur": f"facturation illisible depuis ce rôle ({erreur})"}

    if facture.empty:
        sortie.update(credits=0.0, credits_aujourdhui=0.0, jours_actifs=0,
                      par_jour=facture)
    else:
        facture["credits"] = facture["credits"].map(_nombre)
        jours_vus = pd.to_datetime(facture["jour"], errors="coerce")
        # L'heure de référence est celle de Snowflake (UTC), pas celle du
        # poste : sinon « aujourd'hui » change de sens selon le fuseau de
        # la personne qui regarde l'écran.
        aujourdhui = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
        du_jour = facture.loc[jours_vus == aujourdhui, "credits"]
        sortie.update(
            credits=round(float(facture["credits"].sum()), 4),
            credits_aujourdhui=round(float(du_jour.sum()), 4),
            jours_actifs=int((facture["credits"] > 0).sum()),
            par_jour=facture,
        )

    # L'activité est un confort : si elle manque, le coût reste affichable.
    try:
        activite = session.sql(requete_activite(nom, jours, base)).to_pandas()
        if not activite.empty:
            sortie["requetes"] = int(_nombre(activite["requetes"].iloc[0]))
            sortie["secondes"] = round(_nombre(activite["secondes"].iloc[0]), 1)
    except Exception:
        pass
    return sortie


# ==================================================================
# Hors Snowflake : ce que le Cockpit demande à la base du client
# ==================================================================
# Chez un client sur Oracle, SQL Server ou Postgres, il n'y a pas de crédit
# à afficher : le serveur est déjà payé, le tableau de bord ne coûte pas un
# euro de plus. Afficher « 0 € » serait un mensonge poli.
#
# La question de son informaticien existe pourtant, et c'est une autre :
# « qu'est-ce que votre écran va demander à ma base ? » Elle se mesure sans
# aucun privilège, puisque le Cockpit chronomètre déjà chacune de ses
# lectures (voir `_marque` dans source_donnees.py). On tient donc un petit
# registre, dans la session de la personne connectée, et on le montre.

CLEF_REGISTRE = "_cockpit_lectures"


def registre_neuf() -> dict:
    """Un registre vide : aucune lecture encore faite dans cette session."""
    return {"lectures": 0, "duree_totale_ms": 0.0, "plus_lente_ms": 0.0,
            "lignes": 0, "lignes_cumul": 0, "derniere": None, "origine": ""}


def suit(registre: dict | None, attrs=None) -> dict:
    """Ajoute une lecture au registre, mais seulement si elle est nouvelle.

    L'écran se redessine à chaque clic alors que la donnée, elle, vient du
    cache : compter une lecture à chaque passage gonflerait le chiffre et
    donnerait une fausse idée de la charge. L'horodatage `lu_a`, posé par
    la source au moment où elle a vraiment lu, sert de repère : même
    valeur, même lecture, on ne compte pas deux fois.
    """
    courant = dict(registre or registre_neuf())
    attrs = attrs or {}
    lu_a = attrs.get("lu_a")
    if lu_a is None or lu_a == courant.get("derniere"):
        return courant
    duree = _nombre(attrs.get("duree_ms"))
    lignes = int(_nombre(attrs.get("lignes")))
    courant["lectures"] = int(_nombre(courant.get("lectures"))) + 1
    courant["duree_totale_ms"] = round(
        _nombre(courant.get("duree_totale_ms")) + duree, 1)
    courant["plus_lente_ms"] = round(
        max(_nombre(courant.get("plus_lente_ms")), duree), 1)
    courant["lignes"] = lignes
    courant["lignes_cumul"] = int(_nombre(courant.get("lignes_cumul"))) + lignes
    courant["derniere"] = lu_a
    courant["origine"] = str(attrs.get("origine", "") or courant.get("origine", ""))
    return courant


def phrase_charge(registre: dict | None) -> str:
    """Ce que le Cockpit a demandé à la base, en une phrase pour un informaticien."""
    r = registre or registre_neuf()
    lectures = int(_nombre(r.get("lectures")))
    if not lectures:
        return "aucune lecture depuis l'ouverture de l'écran"
    total = _nombre(r.get("duree_totale_ms"))
    pire = _nombre(r.get("plus_lente_ms"))
    lignes = int(_nombre(r.get("lignes")))
    return (f"{lectures} lecture{'s' if lectures > 1 else ''} depuis l'ouverture, "
            f"{fr(total / 1000, 2)} s au total, "
            f"la plus lente {fr(pire / 1000, 2)} s, "
            f"{fr(lignes, 0)} lignes ramenées la dernière fois.")


def fr(nombre: float, decimales: int = 2) -> str:
    """Un nombre à la française : virgule décimale, espace entre les milliers."""
    texte = f"{_nombre(nombre):,.{int(decimales)}f}"
    return texte.replace(",", " ").replace(".", ",")


def phrase(bilan: dict, prix_credit: float) -> str:
    """Le résumé en une phrase, celle qu'on lit à voix haute en rendez-vous."""
    if not bilan:
        return "coût indisponible"
    if bilan.get("erreur"):
        return str(bilan["erreur"])
    credits = _nombre(bilan.get("credits"))
    euros = en_euros(credits, prix_credit)
    return (f"{fr(credits)} crédit sur {int(bilan.get('jours', 30))} jours, "
            f"soit environ {fr(euros)} € au prix de "
            f"{fr(prix_credit)} € le crédit.")
