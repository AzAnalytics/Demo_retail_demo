"""
test_couts.py — le coût de l'entrepôt, affiché sans mentir
============================================================
Ce qui compte ici, et que ces tests tiennent :

  * la requête de facturation part avec le bon entrepôt, la bonne base et
    une apostrophe doublée (un nom d'entrepôt est une chaîne, donc une
    porte d'entrée s'il n'est pas échappé) ;
  * sept jours maximum pour le détail des requêtes, parce que Snowflake
    n'en garde pas plus : promettre trente jours afficherait un zéro ;
  * un refus de droits renvoie une phrase, jamais une exception : le
    tableau de bord d'un dirigeant ne tombe pas parce qu'une vue
    d'administration est fermée ;
  * les euros sont une conversion annoncée, calculée au prix indiqué.
"""
from __future__ import annotations

import pandas as pd

import couts


class FausseSession:
    """Une session Snowpark de laboratoire : elle répond selon la requête."""

    def __init__(self, credits=None, activite=None, entrepot="WH_XS",
                 casse_facturation=False, casse_activite=False):
        self.credits = credits if credits is not None else []
        self.activite = activite if activite is not None else []
        self.entrepot = entrepot
        self.casse_facturation = casse_facturation
        self.casse_activite = casse_activite
        self.requetes: list[str] = []
        self._derniere = ""

    def sql(self, requete: str):
        self.requetes.append(requete)
        self._derniere = requete
        return self

    def collect(self):
        return []

    def to_pandas(self):
        requete = self._derniere
        if "CURRENT_WAREHOUSE" in requete:
            return pd.DataFrame({"entrepot": [self.entrepot]})
        if "WAREHOUSE_METERING_HISTORY" in requete:
            if self.casse_facturation:
                raise RuntimeError("droits insuffisants sur l'entrepôt")
            return pd.DataFrame(self.credits)
        if "QUERY_HISTORY" in requete:
            if self.casse_activite:
                raise RuntimeError("historique indisponible")
            return pd.DataFrame(self.activite)
        return pd.DataFrame()


# ------------------------------------------------------------------
# Les briques
# ------------------------------------------------------------------
def test_base_de_extrait_la_base_d_un_nom_qualifie():
    assert couts.base_de("MAISON_LAURET.VENTES.TICKETS") == "MAISON_LAURET"


def test_base_de_rend_vide_sans_nom_complet():
    # Deux morceaux : on ne devine pas la base, on laissera la session
    # utiliser la sienne.
    assert couts.base_de("VENTES.TICKETS") == ""
    assert couts.base_de("") == ""
    assert couts.base_de(None) == ""


def test_prefixe_schema_qualifie_ou_non():
    assert couts.prefixe_schema("MAISON_LAURET") == "MAISON_LAURET.INFORMATION_SCHEMA."
    assert couts.prefixe_schema("") == "INFORMATION_SCHEMA."


def test_requete_credits_porte_entrepot_base_et_periode():
    sql = couts.requete_credits("WH_XS", jours=30, base="MAISON_LAURET")
    assert "MAISON_LAURET.INFORMATION_SCHEMA.WAREHOUSE_METERING_HISTORY" in sql
    assert "'WH_XS'" in sql
    assert "-30" in sql


def test_requete_credits_echappe_les_apostrophes():
    sql = couts.requete_credits("WH_L'ESSAI")
    assert "'WH_L''ESSAI'" in sql


def test_requete_activite_ne_depasse_jamais_sept_jours():
    sql = couts.requete_activite("WH_XS", jours=30)
    assert "-7" in sql and "-30" not in sql


def test_en_euros_convertit_et_resiste_au_vide():
    assert couts.en_euros(1.5, 2.5) == 3.75
    assert couts.en_euros(None, 2.5) == 0.0


def test_fr_ecrit_les_nombres_a_la_francaise():
    assert couts.fr(1234.5) == "1 234,50"
    assert couts.fr(0.125, 3) == "0,125"


# ------------------------------------------------------------------
# Le résumé
# ------------------------------------------------------------------
def test_resume_hors_snowflake_explique_au_lieu_de_planter():
    bilan = couts.resume(session=None)
    # Pas de session : on ne tourne pas dans l'entrepôt. Le module le dit.
    assert "erreur" in bilan
    assert "Snowflake" in bilan["erreur"]


def test_resume_additionne_les_credits_et_isole_la_journee():
    aujourdhui = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
    hier = aujourdhui - pd.Timedelta(days=1)
    session = FausseSession(
        credits=[{"jour": hier, "credits": 0.40},
                 {"jour": aujourdhui, "credits": 0.10}],
        activite=[{"requetes": 12, "secondes": 3.5}],
    )
    bilan = couts.resume(jours=30, session=session)
    assert bilan["entrepot"] == "WH_XS"
    assert bilan["credits"] == 0.5
    assert bilan["credits_aujourdhui"] == 0.1
    assert bilan["jours_actifs"] == 2
    assert bilan["requetes"] == 12
    assert bilan["secondes"] == 3.5
    assert bilan["jours_activite"] == 7      # le détail s'arrête à sept jours


def test_resume_sans_consommation_rend_zero_pas_une_erreur():
    bilan = couts.resume(session=FausseSession(credits=[], activite=[]))
    assert bilan.get("erreur") is None
    assert bilan["credits"] == 0.0
    assert bilan["jours_actifs"] == 0


def test_resume_sans_droits_rend_une_phrase():
    bilan = couts.resume(session=FausseSession(casse_facturation=True))
    assert "erreur" in bilan
    assert "droits insuffisants" in bilan["erreur"]
    assert bilan["entrepot"] == "WH_XS"      # on sait quand même où on est


def test_resume_garde_le_cout_si_le_detail_des_requetes_manque():
    # L'activité est un confort : son absence ne doit pas effacer le coût.
    session = FausseSession(credits=[{"jour": "2026-11-20", "credits": 1.0}],
                            casse_activite=True)
    bilan = couts.resume(session=session)
    assert bilan["credits"] == 1.0
    assert "requetes" not in bilan


def test_resume_sans_entrepot_actif_le_dit():
    bilan = couts.resume(session=FausseSession(entrepot=None))
    assert bilan["erreur"] == "aucun entrepôt actif sur cette session"


# ------------------------------------------------------------------
# La phrase lue à voix haute
# ------------------------------------------------------------------
def test_phrase_donne_credits_et_euros():
    texte = couts.phrase({"credits": 0.5, "jours": 30}, prix_credit=2.5)
    assert "0,50 crédit" in texte
    assert "1,25 €" in texte
    assert "30 jours" in texte


def test_phrase_repete_l_erreur_sans_inventer_de_chiffre():
    texte = couts.phrase({"erreur": "facturation illisible"}, prix_credit=2.5)
    assert texte == "facturation illisible"
    assert "€" not in texte
