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


# ------------------------------------------------------------------
# Hors Snowflake : la charge demandée à la base du client
# ------------------------------------------------------------------
def test_un_registre_neuf_est_vide():
    r = couts.registre_neuf()
    assert r["lectures"] == 0 and r["duree_totale_ms"] == 0.0


def test_une_lecture_est_comptee_avec_sa_duree_et_ses_lignes():
    r = couts.suit(None, {"lu_a": 100.0, "duree_ms": 120, "lignes": 33840,
                          "origine": "VENTES.TICKETS"})
    assert r["lectures"] == 1
    assert r["duree_totale_ms"] == 120.0
    assert r["plus_lente_ms"] == 120.0
    assert r["lignes"] == 33840
    assert r["origine"] == "VENTES.TICKETS"


def test_un_redessin_de_l_ecran_ne_compte_pas_une_seconde_lecture():
    # Même `lu_a` : la donnée vient du cache, la base n'a rien fait.
    attrs = {"lu_a": 100.0, "duree_ms": 120, "lignes": 10}
    r = couts.suit(couts.suit(None, attrs), attrs)
    assert r["lectures"] == 1


def test_deux_vraies_lectures_s_additionnent_et_gardent_la_plus_lente():
    r = couts.suit(None, {"lu_a": 100.0, "duree_ms": 120, "lignes": 10})
    r = couts.suit(r, {"lu_a": 200.0, "duree_ms": 80, "lignes": 7})
    assert r["lectures"] == 2
    assert r["duree_totale_ms"] == 200.0
    assert r["plus_lente_ms"] == 120.0      # la plus lente, pas la dernière
    assert r["lignes"] == 7                 # la dernière lecture
    assert r["lignes_cumul"] == 17


def test_un_tableau_sans_horodatage_ne_fausse_pas_le_compteur():
    r = couts.suit(None, {})
    assert r["lectures"] == 0


def test_la_phrase_de_charge_parle_a_un_informaticien():
    r = couts.suit(None, {"lu_a": 1.0, "duree_ms": 450, "lignes": 33840})
    texte = couts.phrase_charge(r)
    assert "1 lecture" in texte
    assert "0,45 s" in texte
    assert "33 840 lignes" in texte


def test_sans_lecture_la_phrase_le_dit_au_lieu_d_afficher_zero():
    assert couts.phrase_charge(None) == "aucune lecture depuis l'ouverture de l'écran"


# ------------------------------------------------------------------
# Le comparatif : les entrepôts du compte, puis ceux du marché
# ------------------------------------------------------------------
def test_les_credits_sont_donnes_entrepot_par_entrepot():
    session = FausseSession(credits=[{"entrepot": "WH_XS", "credits": 5.692},
                                     {"entrepot": "COMPUTE_WH", "credits": 1.2}])
    tableau = couts.par_entrepot(30, session=session, prix_credit=2.5)
    assert list(tableau["entrepot"]) == ["WH_XS", "COMPUTE_WH"]
    assert tableau["credits"].iloc[0] == 5.692
    # La conversion suit, au prix indiqué, et seulement s'il est renseigné.
    assert tableau["euros"].iloc[0] == 14.23


def test_sans_prix_du_credit_on_n_invente_pas_d_euros():
    session = FausseSession(credits=[{"entrepot": "WH_XS", "credits": 1.0}])
    tableau = couts.par_entrepot(30, session=session)
    assert "euros" not in tableau.columns


def test_la_requete_par_entrepot_ne_filtre_sur_aucun_entrepot():
    # Tout l'intérêt : voir aussi celui qu'on a oublié allumé.
    session = FausseSession(credits=[{"entrepot": "WH_XS", "credits": 1.0}])
    couts.par_entrepot(30, session=session)
    requete = [r for r in session.requetes if "METERING" in r][0]
    assert "WAREHOUSE_NAME =>" not in requete
    assert "GROUP BY 1" in requete


def test_un_refus_de_droits_rend_un_tableau_vide_pas_une_exception():
    tableau = couts.par_entrepot(30, session=FausseSession(casse_facturation=True))
    assert tableau.empty


def test_le_comparatif_du_marche_est_date_et_source():
    marche = couts.tarifs()
    assert len(marche) >= 5
    assert "Snowflake (Standard)" in list(marche["Entrepôt"])
    assert "Google BigQuery (à la demande)" in list(marche["Entrepôt"])
    # Aucun prix sans sa source : c'est ce qui distingue un comparatif
    # d'une affirmation.
    assert all(str(s).strip() for s in marche["Source"])
    assert "2026" in couts.RELEVE_TARIFS


def test_chaque_ligne_du_comparatif_porte_une_estimation_en_euros():
    marche = couts.tarifs()
    assert all(str(e).strip() for e in marche["Estimation par mois"])
    # Snowflake : 6,67 h × 1 crédit × 2,60 $ × 0,90 = 15,61 €. Le chiffre
    # doit être recalculable à la main par celui qui lit le tableau.
    snowflake = marche.loc[marche["Entrepôt"].str.startswith("Snowflake")]
    attendu = couts.en_euros(round(couts.SCENARIO_HEURES * 2.60, 2),
                             couts.TAUX_USD_EUR)
    assert snowflake["Estimation par mois"].iloc[0] == f"{couts.fr(attendu)} €"


def test_bigquery_est_annonce_gratuit_et_pas_a_zero_sec():
    ligne = couts.tarifs()
    bq = ligne.loc[ligne["Entrepôt"].str.startswith("Google")]
    # « 0 € » tout seul ferait croire à une donnée manquante.
    assert "gratuit" in bq["Estimation par mois"].iloc[0]
    assert "tébioctet gratuit" in bq["Comment c'est calculé"].iloc[0]


def test_le_taux_du_dollar_se_regle_et_change_les_euros():
    cher = couts.tarifs(taux_usd_eur=2.0)
    pas_cher = couts.tarifs(taux_usd_eur=0.5)
    assert (cher["Estimation par mois"].iloc[0]
            != pas_cher["Estimation par mois"].iloc[0])


def test_le_scenario_est_ecrit_avec_l_estimation():
    phrase = couts.phrase_scenario()
    # Une estimation sans hypothèse n'est qu'un chiffre jeté.
    assert str(couts.SCENARIO_OUVERTURES) in phrase
    assert str(couts.SCENARIO_MINUTES) in phrase
    assert "le dollar" in phrase


# ------------------------------------------------------------------
# L'écran, hors Snowflake : c'est le cas d'un client sur Oracle
# ------------------------------------------------------------------
def test_l_ecran_montre_la_charge_quand_il_n_y_a_pas_d_entrepot():
    """Sans entrepôt, le panneau ne doit ni mentir ni rester muet.

    C'est exactement ce que verra un client sur Oracle : pas de crédits,
    mais le nombre de lectures, leur durée, et la phrase qui dit pourquoi
    il n'y a pas d'euros à afficher.
    """
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    st.cache_data.clear()
    try:
        app = AppTest.from_file("app.py", default_timeout=180)
        app.run()
        assert not app.exception, [str(e) for e in app.exception]
        textes = " ".join([m.value for m in app.markdown]
                          + [c.value for c in app.caption])
        assert "Ce que le Cockpit demande à votre base" in textes
        assert "Aucun crédit à afficher ici" in textes
        assert "votre serveur est déjà payé" in textes
        # Et surtout : le bloc Snowflake, lui, ne s'affiche pas. Son
        # indicateur « Crédits sur N jours » n'a rien à faire sur une base
        # qui ne facture pas à l'usage.
        labels = " ".join(m.label for m in app.get("metric"))
        assert "Crédits sur" not in labels
        assert "Lectures depuis l'ouverture" in labels
        # Et le compteur compte vraiment : le cache de Streamlit rend une
        # copie du tableau qui perd ses `attrs`, et l'écran affichait
        # « 0 lecture » sur une page qui venait d'en faire une.
        lectures = [m for m in app.get("metric")
                    if m.label == "Lectures depuis l'ouverture"]
        assert lectures and str(lectures[0].value) == "1"
    finally:
        st.cache_data.clear()


def test_le_comparatif_s_ouvre_depuis_l_ecran_et_reste_source():
    """Replié par défaut : c'est une référence, pas une mesure."""
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    st.cache_data.clear()
    try:
        app = AppTest.from_file("app.py", default_timeout=180)
        app.run()
        bascules = [t for t in app.toggle if "autres entrepôts" in t.label]
        assert bascules, [t.label for t in app.toggle]
        # Fermé au départ : le tableau n'encombre pas le panneau.
        assert not any("Prix publics relevés" in c.value for c in app.caption)
        app = bascules[0].set_value(True).run()
        assert not app.exception, [str(e) for e in app.exception]
        assert any("Prix publics relevés" in c.value for c in app.caption)
    finally:
        st.cache_data.clear()


def test_une_mise_a_jour_a_moitie_rechargee_ne_casse_pas_l_ecran(monkeypatch):
    """Arrivé en vrai le 27/11/2026 sur la copie publique.

    L'hébergeur recharge `app.py` mais garde en mémoire le `couts.py` de la
    version précédente : la fonction toute neuve est introuvable pendant
    quelques secondes. Un compteur d'usage n'a pas le droit de faire tomber
    le tableau de bord de quelqu'un pour si peu.
    """
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    monkeypatch.delattr(couts, "suit")
    monkeypatch.delattr(couts, "phrase_charge")
    st.cache_data.clear()
    try:
        app = AppTest.from_file("app.py", default_timeout=180)
        app.run()
        assert not app.exception, [str(e) for e in app.exception]
        # L'écran tourne, simplement sans le bloc de charge.
        labels = " ".join(m.label for m in app.get("metric"))
        assert "Lectures depuis l'ouverture" not in labels
    finally:
        st.cache_data.clear()
