"""
test_comptes.py — créer et retirer des personnes depuis l'écran
=================================================================
Ces tests tournent sans Snowflake : une fausse session Snowpark garde les
lignes en mémoire et enregistre le SQL produit. Ce qui est vérifié ici, ce
sont les garde-fous : pas de mot de passe en clair dans l'entrepôt, pas
d'apostrophe qui casse une requête, et jamais le dernier administrateur
supprimé par mégarde.
"""
from __future__ import annotations

import pandas as pd
import pytest

import comptes
import permissions as perm

TABLE = "T_COMPTES"


class FausseSession:
    """Imite Snowpark : .sql(requete).collect() et .to_pandas()."""

    def __init__(self, lignes: list[dict] | None = None):
        self.lignes = list(lignes or [])
        self.requetes: list[str] = []
        self._derniere = ""

    def sql(self, requete: str):
        self.requetes.append(requete)
        self._derniere = requete
        return self

    def collect(self):
        return []

    def to_pandas(self):
        if "SELECT" in self._derniere.upper():
            colonnes = ["identifiant", "nom", "role", "magasins",
                        "categories", "empreinte", "actif"]
            return pd.DataFrame(self.lignes, columns=colonnes)
        return pd.DataFrame()


def _ligne(identifiant="direction", role="admin", actif=True, magasins=""):
    return {"identifiant": identifiant, "nom": identifiant.title(), "role": role,
            "magasins": magasins, "categories": "", "empreinte": "x", "actif": actif}


# ------------------------------------------------------------------
# De la table aux profils de l'écran
# ------------------------------------------------------------------
def test_les_lignes_de_la_table_deviennent_des_profils():
    profils = comptes.profils_depuis_lignes([
        _ligne("direction", "admin"),
        _ligne("toulouse", "contributeur", magasins="Toulouse, Auch"),
    ])
    assert set(profils) == {"direction", "toulouse"}
    assert profils["toulouse"].magasins == ["Toulouse", "Auch"]
    assert profils["direction"].voit_tout


def test_un_compte_desactive_ne_peut_plus_se_connecter():
    profils = comptes.profils_depuis_lignes([_ligne("parti", "lecteur", actif=False)])
    assert profils == {}


def test_un_perimetre_vide_veut_dire_tout_voir():
    profils = comptes.profils_depuis_lignes([_ligne("chef", "admin", magasins=None)])
    assert profils["chef"].magasins == []


# ------------------------------------------------------------------
# Créer une personne
# ------------------------------------------------------------------
def test_creer_une_personne_ecrit_l_empreinte_et_jamais_le_mot_de_passe():
    session = FausseSession([_ligne("direction")])
    comptes.ajoute("marie", "Marie Dupont", "contributeur", "motdepasse-long",
                   magasins=["Montauban"], session=session, table=TABLE)
    insertion = session.requetes[-1]
    assert "INSERT INTO T_COMPTES" in insertion
    assert "'marie'" in insertion and "'Montauban'" in insertion
    assert "pbkdf2_sha256$" in insertion
    assert "motdepasse-long" not in insertion


def test_un_mot_de_passe_trop_court_est_refuse():
    with pytest.raises(comptes.CompteInvalide, match="huit caractères"):
        comptes.ajoute("marie", "Marie", "lecteur", "court",
                       session=FausseSession(), table=TABLE)


def test_un_role_inconnu_est_refuse():
    with pytest.raises(comptes.CompteInvalide, match="rôle inconnu"):
        comptes.ajoute("marie", "Marie", "patron", "motdepasse-long",
                       session=FausseSession(), table=TABLE)


def test_un_identifiant_deja_pris_est_refuse():
    session = FausseSession([_ligne("marie", "lecteur")])
    with pytest.raises(comptes.CompteInvalide, match="existe déjà"):
        comptes.ajoute("Marie", "Marie", "lecteur", "motdepasse-long",
                       session=session, table=TABLE)


def test_une_apostrophe_dans_un_nom_ne_casse_pas_la_requete():
    session = FausseSession([_ligne("direction")])
    comptes.ajoute("jean", "Jean d'Arc", "lecteur", "motdepasse-long",
                   session=session, table=TABLE)
    assert "'Jean d''Arc'" in session.requetes[-1]


def test_l_empreinte_ecrite_verifie_bien_le_mot_de_passe():
    """Le compte créé depuis l'écran doit réellement pouvoir se connecter."""
    session = FausseSession([_ligne("direction")])
    comptes.ajoute("marie", "Marie", "lecteur", "motdepasse-long",
                   session=session, table=TABLE)
    import re

    empreinte = re.search(r"'(pbkdf2_sha256[^']+)'", session.requetes[-1]).group(1)
    assert perm.verifie_mot_de_passe("motdepasse-long", empreinte)
    assert not perm.verifie_mot_de_passe("autre-chose", empreinte)


# ------------------------------------------------------------------
# Les garde-fous
# ------------------------------------------------------------------
def test_on_ne_supprime_pas_le_dernier_administrateur():
    session = FausseSession([_ligne("direction", "admin"),
                             _ligne("marie", "lecteur")])
    with pytest.raises(comptes.CompteInvalide, match="dernier administrateur"):
        comptes.supprime("direction", session=session, table=TABLE)


def test_on_ne_desactive_pas_le_dernier_administrateur():
    session = FausseSession([_ligne("direction", "admin")])
    with pytest.raises(comptes.CompteInvalide, match="dernier administrateur"):
        comptes.active("direction", False, session=session, table=TABLE)


def test_on_ne_retrograde_pas_le_dernier_administrateur():
    session = FausseSession([_ligne("direction", "admin")])
    with pytest.raises(comptes.CompteInvalide, match="dernier administrateur"):
        comptes.modifie("direction", role="lecteur", session=session, table=TABLE)


def test_avec_deux_administrateurs_on_peut_en_retirer_un():
    session = FausseSession([_ligne("direction", "admin"), _ligne("bis", "admin")])
    comptes.supprime("bis", session=session, table=TABLE)
    assert "DELETE FROM T_COMPTES" in session.requetes[-1]


# ------------------------------------------------------------------
# Le premier démarrage
# ------------------------------------------------------------------
def test_les_comptes_du_fichier_sont_semes_dans_une_table_vide():
    session = FausseSession([])
    profils = comptes.profils_depuis_lignes([_ligne("direction"), _ligne("toulouse")])
    assert comptes.sème_les_comptes_de_demonstration(profils, session, TABLE) == 2
    assert sum("INSERT INTO" in r for r in session.requetes) == 2


def test_on_ne_sème_pas_par_dessus_des_comptes_existants():
    session = FausseSession([_ligne("marie", "lecteur")])
    profils = comptes.profils_depuis_lignes([_ligne("direction")])
    assert comptes.sème_les_comptes_de_demonstration(profils, session, TABLE) == 0
    assert not any("INSERT INTO" in r for r in session.requetes)
