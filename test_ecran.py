"""
test_ecran.py — l'écran s'affiche-t-il vraiment, de haut en bas ?
==================================================================
Exécute `app.py` comme Streamlit l'exécute, sans navigateur. Attrape ce que les
tests de calcul ne voient pas : une fonction Streamlit qui change de nom, un
graphique qui refuse une colonne, un onglet qui plante. C'est le test qui évite
d'ouvrir un écran blanc devant un prospect.

Lancer :
    python -m pytest -q test_ecran.py
"""
from __future__ import annotations

import importlib

import pytest
from streamlit.testing.v1 import AppTest

DUREE_MAX = 120     # le fichier fait 33 000 lignes et la prévision tourne au chargement


@pytest.fixture(scope="module", autouse=True)
def sans_profils(tmp_path_factory):
    """Ces tests portent sur l'écran ouvert, pas sur les comptes.

    Un `profils.json` laissé dans le dossier mettrait un écran de connexion
    devant le tableau de bord et ferait échouer les tests pour une mauvaise
    raison. On force donc l'absence de profils.
    """
    import os

    import config

    ancien = os.environ.get("COCKPIT_PROFILS")
    os.environ["COCKPIT_PROFILS"] = str(tmp_path_factory.mktemp("comptes") / "aucun.json")
    importlib.reload(config)
    yield
    if ancien is None:
        os.environ.pop("COCKPIT_PROFILS", None)
    else:
        os.environ["COCKPIT_PROFILS"] = ancien
    importlib.reload(config)


@pytest.fixture(scope="module")
def ecran() -> AppTest:
    app = AppTest.from_file("app.py", default_timeout=DUREE_MAX)
    app.run()
    return app


def test_l_ecran_s_affiche_sans_exception(ecran: AppTest):
    assert not ecran.exception, [str(e) for e in ecran.exception]


def test_les_quatre_indicateurs_sont_la_et_annonces_hors_taxes(ecran: AppTest):
    etiquettes = [m.label for m in ecran.metric]
    assert "Chiffre d'affaires HT" in etiquettes
    assert "Marge HT" in etiquettes
    assert "Taux de marge" in etiquettes
    assert "Panier moyen HT" in etiquettes
    ca = next(m for m in ecran.metric if m.label == "Chiffre d'affaires HT")
    assert ca.value.endswith("€") and ca.value != "0 €"


def test_le_mois_affiche_est_le_dernier_mois_complet(ecran: AppTest):
    """Une démo qui s'arrête il y a cinq mois se voit dans ce titre."""
    import generate_dataset as gen
    import cockpit_calculs as cal

    attendu = cal.libelle_mois(gen.dernier_mois_complet())
    titre = next(s.value for s in ecran.subheader if s.value.startswith("Indicateurs"))
    assert attendu in titre, f"titre affiché : {titre}"


def test_la_tva_est_annoncee_a_l_ecran(ecran: AppTest):
    assert any("hors taxes" in c.value for c in ecran.caption)


def test_le_decrochage_textile_remonte_en_alerte(ecran: AppTest):
    assert ecran.error, "aucune alerte affichée alors que le Textile décroche"
    textes = " ".join(e.value for e in ecran.error)
    assert "Textile" in textes
    assert "€" in textes, "l'alerte doit chiffrer la perte en euros"


def test_l_onglet_prevision_previent_qu_il_ignore_les_filtres(ecran: AppTest):
    assert any("sans tenir compte des filtres" in i.value for i in ecran.info)


def test_un_fichier_absent_affiche_un_message_et_pas_une_erreur_python(monkeypatch, tmp_path):
    """Le prospect doit lire une phrase en français, jamais une trace Python.

    On passe par les variables d'environnement, et pas par un attribut de
    `config` : Streamlit réimporte les modules locaux à chaque exécution, ce
    qui effacerait la modification.
    """
    import importlib

    import streamlit as st

    import config

    # Un chemin hors du projet : on ne veut rien écrire dans le dossier livré.
    monkeypatch.setenv("COCKPIT_DATA_FILE", str(tmp_path / "ventes_absentes.csv"))
    # Fichier client : on ne régénère jamais les données de quelqu'un.
    monkeypatch.setenv("COCKPIT_DEMO_AUTO", "0")
    importlib.reload(config)
    st.cache_data.clear()
    try:
        app = AppTest.from_file("app.py", default_timeout=DUREE_MAX)
        app.run()
        assert not app.exception, [str(e) for e in app.exception]
        assert any("introuvable" in e.value for e in app.error),             [e.value for e in app.error]
    finally:
        monkeypatch.undo()
        importlib.reload(config)
        st.cache_data.clear()
