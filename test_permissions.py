"""
test_permissions.py — le périmètre de chacun tient-il vraiment ?
==================================================================
Ces tests sont les plus importants du projet : une erreur ici fait voir à
quelqu'un des chiffres qu'il n'a pas le droit de voir, et ça ne se rattrape
pas avec une excuse.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

import permissions as perm

VENTES = pd.DataFrame([
    {"date": "2026-10-01", "magasin": "Toulouse", "categorie": "Textile",
     "client": "C1", "ca_ttc": 100.0},
    {"date": "2026-10-02", "magasin": "Auch", "categorie": "Textile",
     "client": "C2", "ca_ttc": 200.0},
    {"date": "2026-10-03", "magasin": "Toulouse", "categorie": "Cuisine",
     "client": "C3", "ca_ttc": 300.0},
])


# ------------------------------------------------------------------
# Les mots de passe
# ------------------------------------------------------------------
def test_le_mot_de_passe_n_est_jamais_stocke_en_clair():
    stockee = perm.empreinte("Soleil-2026", iterations=1000)
    assert "Soleil-2026" not in stockee
    assert stockee.startswith("pbkdf2_sha256$")


def test_l_empreinte_change_a_chaque_fois_mais_verifie_toujours():
    a = perm.empreinte("même mot de passe", iterations=1000)
    b = perm.empreinte("même mot de passe", iterations=1000)
    assert a != b                                   # le sel diffère
    assert perm.verifie_mot_de_passe("même mot de passe", a)
    assert perm.verifie_mot_de_passe("même mot de passe", b)


def test_un_mauvais_mot_de_passe_est_refuse():
    stockee = perm.empreinte("bon", iterations=1000)
    assert perm.verifie_mot_de_passe("mauvais", stockee) is False
    assert perm.verifie_mot_de_passe("", stockee) is False


def test_une_empreinte_abimee_ne_laisse_pas_passer():
    for abimee in ("", "n'importe quoi", "pbkdf2_sha256$pas$des$nombres", "md5$1$a$b"):
        assert perm.verifie_mot_de_passe("bon", abimee) is False


# ------------------------------------------------------------------
# Les profils
# ------------------------------------------------------------------
def _fichier(tmp_path, profils) -> str:
    chemin = tmp_path / "profils.json"
    chemin.write_text(json.dumps({"profils": profils}, ensure_ascii=False),
                      encoding="utf-8")
    return chemin


def test_lecture_des_profils(tmp_path):
    chemin = _fichier(tmp_path, [
        {"identifiant": "direction", "nom": "Direction", "role": "admin",
         "empreinte": perm.empreinte("d", iterations=1000)},
        {"identifiant": "toulouse", "magasins": ["Toulouse"],
         "empreinte": perm.empreinte("t", iterations=1000)},
    ])
    profils = perm.charge_profils(chemin)
    assert set(profils) == {"direction", "toulouse"}
    assert profils["direction"].voit_tout is True
    assert profils["toulouse"].voit_tout is False


def test_fichier_absent_donc_pas_de_restriction(tmp_path):
    assert perm.charge_profils(tmp_path / "rien.json") == {}


def test_un_profil_mal_ecrit_est_refuse_a_la_lecture(tmp_path):
    chemin = _fichier(tmp_path, [{"identifiant": "x", "magasin": "Toulouse"}])
    with pytest.raises(ValueError, match="inconnue"):
        perm.charge_profils(chemin)


def test_authentification(tmp_path):
    chemin = _fichier(tmp_path, [
        {"identifiant": "toulouse", "magasins": ["Toulouse"],
         "empreinte": perm.empreinte("secret", iterations=1000)}])
    profils = perm.charge_profils(chemin)
    assert perm.authentifie("toulouse", "secret", profils).identifiant == "toulouse"
    assert perm.authentifie("toulouse", "faux", profils) is None
    assert perm.authentifie("inconnu", "secret", profils) is None


# ------------------------------------------------------------------
# Le périmètre appliqué aux données
# ------------------------------------------------------------------
def test_un_profil_magasin_ne_voit_que_son_magasin():
    profil = perm.Profil("toulouse", magasins=["Toulouse"])
    vu = perm.applique(VENTES, profil)
    assert set(vu["magasin"]) == {"Toulouse"}
    assert vu["ca_ttc"].sum() == 400.0          # 100 + 300, pas les 200 d'Auch


def test_la_direction_voit_tout():
    assert len(perm.applique(VENTES, perm.Profil("direction"))) == 3
    assert len(perm.applique(VENTES, None)) == 3


def test_deux_restrictions_se_cumulent():
    profil = perm.Profil("x", magasins=["Toulouse"], categories=["Cuisine"])
    vu = perm.applique(VENTES, profil)
    assert len(vu) == 1
    assert vu["ca_ttc"].iloc[0] == 300.0


def test_un_perimetre_vide_ne_laisse_rien_passer():
    """Un profil dont le magasin n'existe pas ne doit rien voir, pas tout voir."""
    vu = perm.applique(VENTES, perm.Profil("x", magasins=["Narbonne"]))
    assert len(vu) == 0


def test_une_dimension_absente_du_fichier_est_ignoree_sans_tout_ouvrir():
    """Pas de colonne client dans ce fichier : le filtre magasin s'applique quand même."""
    sans_client = VENTES.drop(columns=["client"])
    vu = perm.applique(sans_client, perm.Profil("x", magasins=["Auch"], clients=["C9"]))
    assert set(vu["magasin"]) == {"Auch"}


def test_le_resume_dit_ce_que_la_personne_voit():
    assert "ensemble" in perm.Profil("d").resume()
    texte = perm.Profil("x", magasins=["Toulouse", "Auch"]).resume()
    assert "magasins : Toulouse, Auch" in texte


# ------------------------------------------------------------------
# Le périmètre poussé dans la base
# ------------------------------------------------------------------
def test_la_clause_sql_est_parametree_et_pas_concatenee():
    clause, parametres = perm.filtre_sql(perm.Profil("x", magasins=["Toulouse"]))
    assert clause == "magasin IN (?)"
    assert parametres == ["Toulouse"]
    assert "Toulouse" not in clause       # jamais la valeur dans le texte SQL


def test_la_clause_sql_cumule_les_dimensions_et_renomme_les_colonnes():
    profil = perm.Profil("x", magasins=["Toulouse", "Auch"], clients=["C1"])
    clause, parametres = perm.filtre_sql(
        profil, colonnes={"magasin": "M.LIBELLE", "client": "CLI.CODE"})
    assert clause == "M.LIBELLE IN (?, ?) AND CLI.CODE IN (?)"
    assert parametres == ["Toulouse", "Auch", "C1"]


def test_sans_restriction_la_clause_est_vide():
    assert perm.filtre_sql(perm.Profil("direction")) == ("", [])
    assert perm.filtre_sql(None) == ("", [])


def test_la_clause_sql_et_le_filtre_python_donnent_le_meme_resultat():
    """Les deux niveaux doivent dire la même chose, sinon l'un des deux ment."""
    import sqlite3

    profil = perm.Profil("x", magasins=["Toulouse"], categories=["Cuisine"])
    with sqlite3.connect(":memory:") as cx:
        VENTES.to_sql("ventes", cx, index=False)
        clause, parametres = perm.filtre_sql(profil)
        par_sql = pd.read_sql(f"SELECT * FROM ventes WHERE {clause}", cx,
                              params=parametres)
    par_python = perm.applique(VENTES, profil)
    assert par_sql["ca_ttc"].sum() == par_python["ca_ttc"].sum()
    assert len(par_sql) == len(par_python)


# ------------------------------------------------------------------
# De bout en bout, dans l'écran
# ------------------------------------------------------------------
def test_a_l_ecran_un_profil_magasin_ne_voit_que_son_magasin(tmp_path, monkeypatch):
    """Le test qui garantit la promesse : les autres chiffres n'apparaissent pas."""
    import importlib

    import streamlit as st
    from streamlit.testing.v1 import AppTest

    import config

    chemin = _fichier(tmp_path, [
        {"identifiant": "auch", "nom": "Boutique Auch", "role": "lecteur",
         "magasins": ["Auch"], "empreinte": perm.empreinte("secret", iterations=1000)},
        {"identifiant": "direction", "nom": "Direction", "role": "admin",
         "empreinte": perm.empreinte("secret", iterations=1000)},
    ])
    monkeypatch.setenv("COCKPIT_PROFILS", str(chemin))
    importlib.reload(config)
    st.cache_data.clear()
    try:
        app = AppTest.from_file("app.py", default_timeout=180)
        app.run()
        assert not app.metric, "des chiffres sont visibles avant la connexion"

        app.text_input[0].set_value("auch")
        app.text_input[1].set_value("secret")
        app.button[0].click().run()
        assert not app.exception, [str(e) for e in app.exception]
        ca_auch = next(m for m in app.metric if m.label == "Chiffre d'affaires HT")
        assert any("Auch" in c.value for c in app.caption)

        # La direction, elle, voit forcément plus.
        app2 = AppTest.from_file("app.py", default_timeout=180)
        app2.run()
        app2.text_input[0].set_value("direction")
        app2.text_input[1].set_value("secret")
        app2.button[0].click().run()
        ca_tout = next(m for m in app2.metric if m.label == "Chiffre d'affaires HT")

        en_euros = lambda v: float(v.replace("€", "").replace(" ", "").replace(" ", ""))
        assert en_euros(ca_auch.value) < en_euros(ca_tout.value)
    finally:
        monkeypatch.undo()
        importlib.reload(config)
        st.cache_data.clear()


# ------------------------------------------------------------------
# Les rôles : ce qu'on a le droit de FAIRE
# ------------------------------------------------------------------
def test_chaque_role_porte_les_bons_droits():
    assert perm.Profil("a", role="lecteur").droits == {"voir"}
    contributeur = perm.Profil("b", role="contributeur")
    assert contributeur.peut("exporter") and contributeur.peut("reglages")
    assert not contributeur.peut("administrer")
    admin = perm.Profil("c", role="admin")
    assert all(admin.peut(d) for d in perm.DROITS)


def test_le_role_par_defaut_est_le_moins_permissif():
    assert perm.Profil("x").role == perm.ROLE_PAR_DEFAUT
    assert perm.Profil("x").droits == {"voir"}


def test_un_role_inconnu_n_autorise_rien_et_est_refuse_a_la_lecture(tmp_path):
    assert perm.Profil("x", role="super-chef").droits == set()
    chemin = _fichier(tmp_path, [{"identifiant": "x", "role": "super-chef"}])
    with pytest.raises(ValueError, match="rôle inconnu"):
        perm.charge_profils(chemin)


def test_role_et_perimetre_sont_independants():
    """Un contributeur restreint exporte son périmètre, pas celui des autres."""
    profil = perm.Profil("b", role="contributeur", magasins=["Auch"])
    assert profil.peut("exporter")
    assert set(perm.applique(VENTES, profil)["magasin"]) == {"Auch"}


def test_le_resume_du_role_est_lisible():
    assert "lecture seule" in perm.Profil("a", role="lecteur").resume_role()
    resume = perm.Profil("b", role="contributeur").resume_role().lower()
    assert "télécharger" in resume and "ajuster" in resume


def test_a_l_ecran_un_lecteur_n_a_pas_le_bouton_d_export(tmp_path, monkeypatch):
    import importlib

    import streamlit as st
    from streamlit.testing.v1 import AppTest

    import config

    chemin = _fichier(tmp_path, [
        {"identifiant": "lecteur", "role": "lecteur",
         "empreinte": perm.empreinte("secret", iterations=1000)},
        {"identifiant": "chef", "role": "admin",
         "empreinte": perm.empreinte("secret", iterations=1000)},
    ])
    monkeypatch.setenv("COCKPIT_PROFILS", str(chemin))
    monkeypatch.setenv("COCKPIT_EXPORT", "1")     # export ouvert, comme chez un client
    importlib.reload(config)
    st.cache_data.clear()
    try:
        app = AppTest.from_file("app.py", default_timeout=180)
        app.run()
        app.text_input[0].set_value("lecteur")
        app.text_input[1].set_value("secret")
        app.button[0].click().run()
        assert not app.exception, [str(e) for e in app.exception]
        assert app.metric, "le lecteur doit voir les indicateurs"
        assert not app.download_button, "un lecteur ne doit pas pouvoir exporter"
        assert not app.slider, "un lecteur ne doit pas pouvoir changer les seuils"

        chef = AppTest.from_file("app.py", default_timeout=180)
        chef.run()
        chef.text_input[0].set_value("chef")
        chef.text_input[1].set_value("secret")
        chef.button[0].click().run()
        assert chef.download_button, "l'administrateur doit pouvoir exporter"
        assert chef.slider, "l'administrateur doit pouvoir régler les seuils"
    finally:
        monkeypatch.undo()
        importlib.reload(config)
        st.cache_data.clear()


def test_le_bouton_de_deconnexion_ramene_a_l_ecran_de_connexion(tmp_path, monkeypatch):
    """Sur un poste partagé, pouvoir sortir compte autant que pouvoir entrer."""
    import importlib

    import streamlit as st
    from streamlit.testing.v1 import AppTest

    import config

    chemin = _fichier(tmp_path, [
        {"identifiant": "chef", "role": "admin",
         "empreinte": perm.empreinte("secret", iterations=1000)}])
    monkeypatch.setenv("COCKPIT_PROFILS", str(chemin))
    importlib.reload(config)
    st.cache_data.clear()
    try:
        app = AppTest.from_file("app.py", default_timeout=180)
        app.run()
        app.text_input[0].set_value("chef")
        app.text_input[1].set_value("secret")
        app.button[0].click().run()
        assert app.metric, "la connexion devrait ouvrir le tableau de bord"

        sortie = next(b for b in app.button if "déconnecter" in b.label)
        sortie.click().run()
        assert not app.exception, [str(e) for e in app.exception]
        assert not app.metric, "les chiffres restent visibles après la déconnexion"
        assert app.text_input, "l'écran de connexion ne revient pas"
        assert app.text_input[0].value in ("", None), "l'identifiant précédent reste affiché"
        # Réembarquer doit rejouer le générique d'ouverture.
        assert "_cockpit_splash_done" not in app.session_state
        # Et la sortie a son propre générique.
        assert any("DÉBARQUEMENT" in m.value for m in app.markdown),             "le générique de sortie ne se joue pas"
    finally:
        monkeypatch.undo()
        importlib.reload(config)
        st.cache_data.clear()
