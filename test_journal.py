"""
test_journal.py — le journal des connexions
=============================================
Deux niveaux : le module lui-même, avec une fausse session Snowpark, et
l'écran, où l'on tape un mauvais mot de passe pour vérifier que l'échec
part bien au journal. Ce qui compte ici : un échec se voit, un mot de
passe ne s'écrit jamais, et un journal en panne n'empêche personne de
travailler.
"""
from __future__ import annotations

import pandas as pd

import journal
import permissions as perm

TABLE = "T_JOURNAL"


class FausseSession:
    def __init__(self, lignes: list[dict] | None = None, casse: bool = False):
        self.lignes = list(lignes or [])
        self.requetes: list[str] = []
        self.casse = casse
        self._derniere = ""

    def sql(self, requete: str):
        self.requetes.append(requete)
        self._derniere = requete
        return self

    def collect(self):
        if self.casse:
            raise RuntimeError("entrepôt indisponible")
        return []

    def to_pandas(self):
        return pd.DataFrame(self.lignes)


# ------------------------------------------------------------------
# Écrire
# ------------------------------------------------------------------
def test_une_connexion_reussie_est_enregistree():
    session = FausseSession()
    assert journal.enregistre("marie", journal.CONNEXION, "lecteur",
                              session=session, table=TABLE)
    insertion = session.requetes[-1]
    assert "INSERT INTO T_JOURNAL" in insertion
    assert "'marie'" in insertion and "'connexion'" in insertion
    assert "'lecteur'" in insertion


def test_un_echec_garde_l_identifiant_saisi_meme_inconnu():
    """C'est tout l'intérêt : voir quelqu'un essayer des comptes."""
    session = FausseSession()
    journal.enregistre("admin", journal.ECHEC, session=session, table=TABLE)
    assert "'admin'" in session.requetes[-1]
    assert "'échec'" in session.requetes[-1]


def test_une_apostrophe_dans_l_identifiant_ne_casse_pas_la_requete():
    session = FausseSession()
    journal.enregistre("o'brien", journal.ECHEC, session=session, table=TABLE)
    assert "'o''brien'" in session.requetes[-1]


def test_un_identifiant_demesure_est_tronque():
    """Trois cents caractères, c'est une tentative, pas une faute de frappe."""
    session = FausseSession()
    journal.enregistre("x" * 300, journal.ECHEC, session=session, table=TABLE)
    assert len(session.requetes[-1]) < 200


def test_un_journal_en_panne_ne_bloque_personne():
    """Si l'écriture échoue, la personne se connecte quand même."""
    assert journal.enregistre("marie", journal.CONNEXION,
                              session=FausseSession(casse=True),
                              table=TABLE) is False


def test_hors_snowflake_il_ne_se_passe_rien():
    assert journal.enregistre("marie", journal.CONNEXION) is False
    assert journal.lire().empty
    assert journal.resume().empty


# ------------------------------------------------------------------
# Lire
# ------------------------------------------------------------------
def test_la_lecture_demande_les_plus_recents_d_abord():
    session = FausseSession([{"horodatage": "2026-11-25 09:00:00",
                              "identifiant": "marie",
                              "evenement": "connexion", "role": "lecteur"}])
    lignes = journal.lire(50, session=session, table=TABLE)
    assert len(lignes) == 1
    assert "ORDER BY HORODATAGE DESC" in session.requetes[-1]
    assert "LIMIT 50" in session.requetes[-1]


def test_le_resume_est_calcule_par_l_entrepot():
    """Une ligne par personne traverse le réseau, pas le journal entier."""
    session = FausseSession([{"identifiant": "marie", "derniere_connexion": None,
                              "connexions": 3, "echecs": 1}])
    resume = journal.resume(session=session, table=TABLE)
    assert resume["connexions"].iloc[0] == 3
    assert "GROUP BY IDENTIFIANT" in session.requetes[-1]
    assert "COUNT_IF(EVENEMENT = 'échec')" in session.requetes[-1]


# ------------------------------------------------------------------
# À l'écran
# ------------------------------------------------------------------
def test_un_mot_de_passe_rate_part_au_journal(tmp_path, monkeypatch):
    """Le bout de chaîne complet : saisie fausse, ligne d'échec journalisée."""
    import importlib
    import json as json_module

    import streamlit as st
    from streamlit.testing.v1 import AppTest

    import config

    chemin = tmp_path / "profils.json"
    chemin.write_text(json_module.dumps({"profils": [
        {"identifiant": "chef", "nom": "Chef", "role": "admin",
         "empreinte": perm.empreinte("secret", iterations=1000)},
    ]}), encoding="utf-8")

    enregistres: list[tuple] = []
    monkeypatch.setattr(journal, "enregistre",
                        lambda *a, **k: enregistres.append(a) or True)
    monkeypatch.setenv("COCKPIT_PROFILS", str(chemin))
    importlib.reload(config)
    st.cache_data.clear()
    try:
        app = AppTest.from_file("app.py", default_timeout=180)
        app.run()
        app.text_input[0].set_value("chef")
        app.text_input[1].set_value("pas-le-bon")
        app.button[0].click().run()
        assert not app.exception, [str(e) for e in app.exception]
        assert ("chef", "échec", "") in enregistres

        app.text_input[0].set_value("chef")
        app.text_input[1].set_value("secret")
        app.button[0].click().run()
        assert ("chef", "connexion", "admin") in enregistres
    finally:
        monkeypatch.undo()
        importlib.reload(config)
        st.cache_data.clear()
