"""
test_cockpit.py — les chiffres du Cockpit sont-ils ceux qu'on annonce ?
========================================================================
Chaque test est écrit avec des montants ronds, pour qu'on puisse vérifier à la
main ce que la machine répond. C'est ce qui permet de modifier l'écran sans
découvrir un chiffre faux devant un client.

Lancer :
    python -m pytest -q
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

import cockpit_calculs as cal
import cockpit_forecast as cf
import generate_dataset as gen


# ------------------------------------------------------------------
# Fabrique de ventes
# ------------------------------------------------------------------
def ventes(lignes: list[dict]) -> pd.DataFrame:
    """Un tableau au format du fichier de caisse, prêt pour les calculs."""
    df = pd.DataFrame(lignes)
    df["date"] = pd.to_datetime(df["date"])
    df = cal.montants_hors_taxes(df, 0.20)
    df["mois"] = df["date"].dt.to_period("M").dt.to_timestamp()
    return df


def ticket(jour: str, categorie: str = "Textile", ttc: float = 120.0,
           cout: float = 40.0, quantite: int = 1, magasin: str = "Toulouse") -> dict:
    return {"date": jour, "magasin": magasin, "categorie": categorie,
            "produit": "Article", "quantite": quantite,
            "prix_unitaire": ttc / quantite, "cout_unitaire": cout, "ca_ttc": ttc}


# ------------------------------------------------------------------
# La conversion TTC vers HT
# ------------------------------------------------------------------
def test_les_prix_boutique_sont_ramenes_hors_taxes():
    d = ventes([ticket("2026-10-05", ttc=120.0, cout=40.0)])
    assert d["ca"].iloc[0] == pytest.approx(100.0)      # 120 TTC / 1,20
    assert d["marge"].iloc[0] == pytest.approx(60.0)    # 100 HT - 40 de coût


def test_un_fichier_deja_hors_taxes_n_est_pas_retouche():
    brut = pd.DataFrame([ticket("2026-10-05", ttc=100.0, cout=40.0)])
    d = cal.montants_hors_taxes(brut, 0.0)
    assert d["ca"].iloc[0] == pytest.approx(100.0)
    assert d["marge"].iloc[0] == pytest.approx(60.0)


def test_le_cout_d_achat_est_multiplie_par_la_quantite():
    d = ventes([ticket("2026-10-05", ttc=240.0, cout=40.0, quantite=2)])
    assert d["ca"].iloc[0] == pytest.approx(200.0)
    assert d["marge"].iloc[0] == pytest.approx(120.0)   # 200 - 2 x 40


# ------------------------------------------------------------------
# Le mois de référence
# ------------------------------------------------------------------
def test_on_compare_au_meme_mois_un_an_avant():
    d = ventes([ticket("2025-10-05"), ticket("2026-09-05"), ticket("2026-10-05")])
    p = cal.periode_de_reference(d)
    assert p.mois == pd.Timestamp("2026-10-01")
    assert p.comparaison == pd.Timestamp("2025-10-01")
    assert p.type_comparaison == "au même mois un an avant"


def test_sans_an_dernier_on_se_rabat_sur_le_mois_precedent_et_on_le_dit():
    d = ventes([ticket("2026-09-05"), ticket("2026-10-05")])
    p = cal.periode_de_reference(d)
    assert p.comparaison == pd.Timestamp("2026-09-01")
    assert p.type_comparaison == "au mois précédent disponible"


def test_un_mois_en_cours_est_compare_a_perimetre_egal():
    """Opposer 10 jours a un mois entier fabriquerait une baisse inexistante."""
    d = ventes(
        [ticket("2025-10-05", ttc=1200.0), ticket("2025-10-25", ttc=1200.0)]
        + [ticket("2026-10-05", ttc=1200.0)]
    )
    p = cal.periode_de_reference(d, aujourdhui="2026-10-10")
    assert p.en_cours is True
    assert p.jour_arret == 5
    assert "perimetre egal" in p.note.replace("é", "e").replace("è", "e")

    cmp = cal.a_perimetre_egal(d[d["mois"] == pd.Timestamp("2025-10-01")], p)
    assert len(cmp) == 1                       # la vente du 25 est hors perimetre
    cur = d[d["mois"] == pd.Timestamp("2026-10-01")]
    assert cal.indicateurs(cur).ca == pytest.approx(cal.indicateurs(cmp).ca)


def test_un_mois_clos_n_est_pas_tronque():
    """La derniere vente du 29 ne fait pas un mois en cours : le calendrier tranche."""
    d = ventes([ticket("2025-10-05"), ticket("2026-10-29")])
    p = cal.periode_de_reference(d, aujourdhui="2026-11-23")
    assert p.en_cours is False
    assert p.note == ""
    cmp = d[d["mois"] == pd.Timestamp("2025-10-01")]
    assert len(cal.a_perimetre_egal(cmp, p)) == len(cmp)


def test_un_seul_mois_ne_compare_rien():
    p = cal.periode_de_reference(ventes([ticket("2026-10-05")]))
    assert p.comparaison is None


# ------------------------------------------------------------------
# Les quatre indicateurs
# ------------------------------------------------------------------
def test_les_quatre_indicateurs_sur_des_montants_ronds():
    d = ventes([
        ticket("2026-10-05", ttc=120.0, cout=40.0),     # 100 HT, marge 60
        ticket("2026-10-06", ttc=240.0, cout=100.0),    # 200 HT, marge 100
    ])
    i = cal.indicateurs(d)
    assert i.ca == pytest.approx(300.0)
    assert i.marge == pytest.approx(160.0)
    assert i.taux_marge == pytest.approx(53.333, rel=1e-3)
    assert i.panier == pytest.approx(150.0)             # 300 / 2 tickets
    assert i.tickets == 2


def test_une_selection_vide_ne_divise_pas_par_zero():
    i = cal.indicateurs(ventes([ticket("2026-10-05")]).iloc[0:0])
    assert (i.ca, i.marge, i.taux_marge, i.panier, i.tickets) == (0.0, 0.0, 0.0, 0.0, 0)


def test_la_variation_est_nulle_quand_la_reference_est_nulle():
    assert cal.variation(100, 0) is None
    assert cal.variation(110, 100) == "+10.0%"
    assert cal.variation(90, 100) == "-10.0%"


# ------------------------------------------------------------------
# Les alertes
# ------------------------------------------------------------------
def _mois_categorie(categorie: str, jour: str, total_ttc: float, nb: int = 10):
    return [ticket(jour, categorie=categorie, ttc=total_ttc / nb, cout=0.0)
            for _ in range(nb)]


def test_une_categorie_qui_recule_declenche_une_alerte_chiffree_en_euros():
    d = ventes(_mois_categorie("Textile", "2025-10-10", 12_000.0)
               + _mois_categorie("Textile", "2026-10-10", 9_600.0))
    cur = d[d["mois"] == pd.Timestamp("2026-10-01")]
    cmp = d[d["mois"] == pd.Timestamp("2025-10-01")]
    baisses, hausses = cal.alertes_categories(cur, cmp, seuil_pct=10)
    assert hausses == []
    assert len(baisses) == 1
    a = baisses[0]
    assert a.categorie == "Textile"
    assert a.variation_pct == pytest.approx(-20.0)
    assert a.ecart_eur == pytest.approx(-2_000.0)        # 10 000 HT contre 8 000 HT
    assert "2 000 €" in a.phrase("au même mois un an avant")


def test_une_petite_categorie_ne_declenche_rien_meme_en_forte_baisse():
    """-40 % sur 400 € n'est pas une alerte : c'est du bruit."""
    d = ventes(_mois_categorie("Papeterie", "2025-10-10", 600.0)
               + _mois_categorie("Papeterie", "2026-10-10", 360.0))
    cur = d[d["mois"] == pd.Timestamp("2026-10-01")]
    cmp = d[d["mois"] == pd.Timestamp("2025-10-01")]
    baisses, hausses = cal.alertes_categories(cur, cmp, seuil_pct=10)
    assert baisses == [] and hausses == []


def test_les_baisses_sont_triees_par_euros_perdus():
    d = ventes(
        _mois_categorie("Textile", "2025-10-10", 12_000.0)
        + _mois_categorie("Textile", "2026-10-10", 9_600.0)      # -2 000 € HT
        + _mois_categorie("Décoration", "2025-10-10", 60_000.0)
        + _mois_categorie("Décoration", "2026-10-10", 48_000.0)  # -10 000 € HT
    )
    cur = d[d["mois"] == pd.Timestamp("2026-10-01")]
    cmp = d[d["mois"] == pd.Timestamp("2025-10-01")]
    baisses, _ = cal.alertes_categories(cur, cmp, seuil_pct=10)
    assert [a.categorie for a in baisses] == ["Décoration", "Textile"]


def test_une_categorie_qui_progresse_est_annoncee_comme_telle():
    d = ventes(_mois_categorie("Cadeaux", "2025-10-10", 12_000.0)
               + _mois_categorie("Cadeaux", "2026-10-10", 18_000.0))
    cur = d[d["mois"] == pd.Timestamp("2026-10-01")]
    cmp = d[d["mois"] == pd.Timestamp("2025-10-01")]
    baisses, hausses = cal.alertes_categories(cur, cmp, seuil_pct=10)
    assert baisses == []
    assert hausses[0].variation_pct == pytest.approx(50.0)
    assert "progresse" in hausses[0].phrase("au même mois un an avant")


# ------------------------------------------------------------------
# L'objectif
# ------------------------------------------------------------------
def test_l_objectif_est_l_an_dernier_augmente():
    assert cal.objectif_du_mois(10_000, 1.08) == pytest.approx(10_800)
    assert cal.objectif_du_mois(0, 1.08) is None


# ------------------------------------------------------------------
# La prévision
# ------------------------------------------------------------------
def _serie_reguliere(mois: int = 24, valeur: float = 10_000.0) -> pd.DataFrame:
    jours = pd.date_range("2024-01-01", periods=mois, freq="MS")
    return pd.DataFrame({
        "date": jours,
        "magasin": "Toulouse",
        "categorie": "Décoration",
        "ca": valeur,
    })


def test_une_serie_parfaitement_plate_est_prevue_plate():
    r = cf.prevoir(_serie_reguliere(), horizon=12)
    assert len(r["forecast"]) == 12
    assert r["forecast"].min() == pytest.approx(10_000.0, rel=0.02)
    assert abs(r["growth"]) < 2.0
    assert r["mape"] < 1.0                     # aucune erreur à faire sur du plat


def test_l_intervalle_s_elargit_avec_le_temps():
    r = cf.prevoir(_serie_reguliere(), horizon=12)
    largeurs = (r["upper"] - r["lower"]).values
    assert largeurs[-1] > largeurs[0]
    assert (r["lower"] >= 0).all()             # un CA prévu négatif n'a pas de sens


def test_le_modele_retenu_et_son_erreur_sont_annonces():
    r = cf.prevoir(_serie_reguliere(), horizon=12)
    assert r["model"] in ("Saisonnier ajusté", "Ridge + Fourier", "Tendance × saisonnalité")
    assert r["mape"] >= 0


def test_la_prevision_suit_une_croissance_reelle():
    """+2 % par mois pendant 24 mois : la prévision doit monter, pas stagner."""
    serie = _serie_reguliere()
    serie["ca"] = [10_000 * (1.02 ** i) for i in range(len(serie))]
    r = cf.prevoir(serie, horizon=12)
    assert r["growth"] > 10            # au moins dix points de croissance annoncés
    assert r["forecast"].iloc[-1] > serie["ca"].iloc[-1]


def test_la_prevision_travaille_bien_en_hors_taxes():
    """Diviser le CA par 1,2 doit diviser la prévision par 1,2, pas autre chose."""
    serie = _serie_reguliere()
    ht = serie.copy()
    ht["ca"] = ht["ca"] / 1.2
    assert (cf.prevoir(ht, horizon=12)["total_next"]
            == pytest.approx(cf.prevoir(serie, horizon=12)["total_next"] / 1.2, rel=1e-6))


def test_le_recapitulatif_couvre_toutes_les_entites():
    serie = pd.concat([_serie_reguliere(), _serie_reguliere().assign(magasin="Auch")])
    recap = cf.recap_entites(serie, "magasin", horizon=12)
    assert sorted(recap["Magasin"]) == ["Auch", "Toulouse"]
    assert recap["CA prévu 12 mois"].min() > 0


# ------------------------------------------------------------------
# Le jeu de données de démonstration
# ------------------------------------------------------------------
def test_un_fichier_perime_est_detecte(tmp_path):
    """Sur un hebergement, personne ne relance le script : l'ecran doit le voir."""
    fichier = tmp_path / "vieux.csv"
    fichier.write_text("date\n2026-01-15\n", encoding="utf-8")
    assert gen.est_perime(fichier, aujourdhui=date(2026, 11, 23)) is True
    assert gen.est_perime(tmp_path / "absent.csv") is True

    recent = tmp_path / "recent.csv"
    recent.write_text("date\n2026-10-31\n", encoding="utf-8")
    assert gen.est_perime(recent, aujourdhui=date(2026, 11, 23)) is False


def test_le_fichier_livre_n_est_pas_perime():
    assert gen.est_perime("ventes_maison_lauret.csv") is False


def test_la_demo_se_termine_au_dernier_mois_complet():
    assert gen.dernier_mois_complet(date(2026, 11, 23)) == date(2026, 10, 31)
    assert gen.dernier_mois_complet(date(2027, 1, 1)) == date(2026, 12, 31)


def test_la_fenetre_couvre_bien_dix_huit_mois():
    assert gen.premier_jour(date(2026, 10, 31), 18) == date(2025, 5, 1)


def test_le_fichier_livre_est_a_jour_et_raconte_le_decrochage_textile():
    """Le test qui évite de montrer une démo périmée ou sans histoire."""
    df = pd.read_csv("ventes_maison_lauret.csv", parse_dates=["date"])
    df["mois"] = df["date"].dt.to_period("M")
    dernier = df["mois"].max()
    assert dernier.to_timestamp().date() >= gen.dernier_mois_complet().replace(day=1), (
        "le fichier de démonstration est périmé : relance generate_dataset.py"
    )
    textile = df[df["categorie"] == gen.CATEGORIE_EN_RECUL].groupby("mois")["ca_ttc"].sum()
    recul = (textile[dernier] / textile[dernier - 12] - 1) * 100
    assert recul <= -10, f"le décrochage Textile ne se voit plus ({recul:.1f} %)"
