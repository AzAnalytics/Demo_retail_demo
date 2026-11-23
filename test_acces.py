"""
test_acces.py — le verrou tient-il ?
======================================
Sur un poste chez le client, le Cockpit est joignable par tout le réseau de
l'entreprise. Ces tests vérifient qu'un mot de passe configuré ferme vraiment
la porte, et qu'aucun chiffre ne s'affiche avant qu'elle ne soit ouverte.
"""
from __future__ import annotations

import importlib

import streamlit as st
from streamlit.testing.v1 import AppTest

import acces

DUREE_MAX = 120
SECRET = "cockpit-2026"


def test_sans_mot_de_passe_configure_il_n_y_a_pas_de_verrou():
    assert acces.est_correct("", "") is True


def test_la_comparaison_refuse_un_mot_de_passe_faux():
    assert acces.est_correct("mauvais", SECRET) is False
    assert acces.est_correct(SECRET, SECRET) is True
    assert acces.est_correct(SECRET + " ", SECRET) is False


def _ecran_protege(monkeypatch) -> AppTest:
    import config

    monkeypatch.setenv("COCKPIT_ACCESS_PASSWORD", SECRET)
    importlib.reload(config)
    st.cache_data.clear()
    app = AppTest.from_file("app.py", default_timeout=DUREE_MAX)
    app.run()
    return app


def test_aucun_chiffre_ne_s_affiche_avant_le_mot_de_passe(monkeypatch):
    import config

    try:
        app = _ecran_protege(monkeypatch)
        assert not app.exception, [str(e) for e in app.exception]
        assert app.text_input, "l'écran de saisie ne s'affiche pas"
        assert not app.metric, "des chiffres sont visibles sans mot de passe"
    finally:
        monkeypatch.undo()
        importlib.reload(config)
        st.cache_data.clear()


def test_le_bon_mot_de_passe_ouvre_le_tableau_de_bord(monkeypatch):
    import config

    try:
        app = _ecran_protege(monkeypatch)
        app.text_input[0].set_value(SECRET).run()
        assert not app.exception, [str(e) for e in app.exception]
        assert app.metric, "le tableau de bord ne s'ouvre pas avec le bon mot de passe"
    finally:
        monkeypatch.undo()
        importlib.reload(config)
        st.cache_data.clear()


def test_un_mauvais_mot_de_passe_est_refuse_et_le_dit(monkeypatch):
    import config

    try:
        app = _ecran_protege(monkeypatch)
        app.text_input[0].set_value("au hasard").run()
        assert not app.metric
        assert any("incorrect" in e.value for e in app.error)
    finally:
        monkeypatch.undo()
        importlib.reload(config)
        st.cache_data.clear()
