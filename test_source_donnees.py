"""
test_source_donnees.py — la même sortie, quelle que soit la source
====================================================================
Les tests tournent sur SQLite, qui est livré avec Python : la logique de
lecture d'une base est donc réellement exécutée, pas seulement écrite. Le
chemin Oracle, lui, n'est pas testable sans serveur Oracle ; seul le pilote
change, le reste du code est celui qui est testé ici.
"""
from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

import source_donnees as src

LIGNES = [
    ("2026-10-05", "Toulouse", "Textile", "Plaid laine", 1, 120.0, 40.0, 120.0),
    ("2026-10-06", "Auch", "Cuisine", "Mug grès", 2, 12.0, 5.0, 24.0),
]


def _base(tmp_path, colonnes: str = "date, magasin, categorie, produit, "
                                    "quantite, prix_unitaire, cout_unitaire, ca_ttc"):
    chemin = tmp_path / "ventes.db"
    with sqlite3.connect(chemin) as cx:
        cx.execute(f"CREATE TABLE ventes ({colonnes})")
        cx.executemany("INSERT INTO ventes VALUES (?,?,?,?,?,?,?,?)", LIGNES)
    return chemin


# ------------------------------------------------------------------
# Une base de données
# ------------------------------------------------------------------
def test_une_requete_sql_donne_le_meme_tableau_qu_un_csv(tmp_path):
    chemin = _base(tmp_path)
    cx = src.connexion_sqlite(chemin)
    try:
        ventes = src.depuis_base(cx, "SELECT * FROM ventes ORDER BY date")
    finally:
        cx.close()

    assert list(ventes.columns)[:8] == list(src.COLONNES)
    assert len(ventes) == 2
    assert ventes["ca_ttc"].sum() == pytest.approx(144.0)
    assert ventes["date"].iloc[0] == pd.Timestamp("2026-10-05")


def test_les_colonnes_se_renomment_dans_la_requete(tmp_path):
    """Chez un client, les colonnes s'appellent autrement : c'est le SQL qui traduit."""
    chemin = tmp_path / "erp.db"
    with sqlite3.connect(chemin) as cx:
        cx.execute("CREATE TABLE t (jour, boutique, famille, article, qte, pu, pra, ttc)")
        cx.executemany("INSERT INTO t VALUES (?,?,?,?,?,?,?,?)", LIGNES)

    cx = src.connexion_sqlite(chemin)
    try:
        ventes = src.depuis_base(cx, """
            SELECT jour AS date, boutique AS magasin, famille AS categorie,
                   article AS produit, qte AS quantite, pu AS prix_unitaire,
                   pra AS cout_unitaire, ttc AS ca_ttc
            FROM t
        """)
    finally:
        cx.close()
    assert len(ventes) == 2
    assert ventes["magasin"].tolist() == ["Toulouse", "Auch"]


def test_une_requete_parametree_filtre_la_periode(tmp_path):
    cx = src.connexion_sqlite(_base(tmp_path))
    try:
        ventes = src.depuis_base(cx, "SELECT * FROM ventes WHERE date >= ?",
                                 parametres=("2026-10-06",))
    finally:
        cx.close()
    assert len(ventes) == 1


def test_une_colonne_manquante_est_refusee_avant_tout_calcul(tmp_path):
    """Une vue modifiée côté client ne doit pas produire un chiffre faux."""
    chemin = tmp_path / "incomplet.db"
    with sqlite3.connect(chemin) as cx:
        cx.execute("CREATE TABLE v (date, magasin, categorie, produit, quantite)")
        cx.execute("INSERT INTO v VALUES ('2026-10-05','Toulouse','Textile','Plaid',1)")
    cx = src.connexion_sqlite(chemin)
    try:
        with pytest.raises(src.SourceInvalide, match="prix_unitaire"):
            src.depuis_base(cx, "SELECT * FROM v")
    finally:
        cx.close()


def test_une_base_vide_est_refusee(tmp_path):
    chemin = tmp_path / "vide.db"
    with sqlite3.connect(chemin) as cx:
        cx.execute("CREATE TABLE ventes (date, magasin, categorie, produit, "
                   "quantite, prix_unitaire, cout_unitaire, ca_ttc)")
    cx = src.connexion_sqlite(chemin)
    try:
        with pytest.raises(src.SourceInvalide, match="aucune ligne"):
            src.depuis_base(cx, "SELECT * FROM ventes")
    finally:
        cx.close()


# ------------------------------------------------------------------
# Un fichier
# ------------------------------------------------------------------
def test_le_csv_livre_passe_le_controle():
    ventes = src.depuis_csv("ventes_maison_lauret.csv")
    assert len(ventes) > 1000
    assert ventes["date"].notna().all()


def test_un_csv_sans_la_colonne_des_couts_est_refuse(tmp_path):
    chemin = tmp_path / "partiel.csv"
    chemin.write_text("date,magasin,categorie,produit,quantite,prix_unitaire,ca_ttc\n"
                      "2026-10-05,Toulouse,Textile,Plaid,1,120,120\n", encoding="utf-8")
    with pytest.raises(src.SourceInvalide, match="cout_unitaire"):
        src.depuis_csv(chemin)


def test_les_valeurs_illisibles_sont_ecartees_sans_tout_bloquer(tmp_path):
    chemin = tmp_path / "sale.csv"
    chemin.write_text(
        "date,magasin,categorie,produit,quantite,prix_unitaire,cout_unitaire,ca_ttc\n"
        "2026-10-05,Toulouse,Textile,Plaid,1,120,40,120\n"
        "pas une date,Auch,Cuisine,Mug,2,12,5,24\n"
        "2026-10-07,Auch,Cuisine,Mug,,12,5,\n",
        encoding="utf-8")
    ventes = src.depuis_csv(chemin)
    assert len(ventes) == 1


# ------------------------------------------------------------------
# Le choix de la source par la configuration
# ------------------------------------------------------------------
class _ConfigSqlite:
    SOURCE = "sqlite"
    SOURCE_REQUETE = "SELECT * FROM ventes"

    def __init__(self, chemin):
        self.SOURCE_PARAMETRES = {"chemin": chemin}


class _ConfigCsv:
    SOURCE = "csv"
    DATA_FILE = "ventes_maison_lauret.csv"


def test_la_configuration_choisit_la_base(tmp_path):
    ventes = src.charge(_ConfigSqlite(_base(tmp_path)))
    assert len(ventes) == 2


def test_la_configuration_choisit_le_fichier():
    assert len(src.charge(_ConfigCsv())) > 1000


def test_une_source_inconnue_est_dite_clairement():
    class Bidon:
        SOURCE = "mongodb"

    with pytest.raises(src.SourceInvalide, match="source inconnue"):
        src.charge(Bidon())


def test_sans_pilote_odbc_le_message_est_lisible(monkeypatch):
    """Pas de trace Python : on dit quoi installer."""
    import builtins

    vrai_import = builtins.__import__

    def sans_pyodbc(nom, *args, **kwargs):
        if nom == "pyodbc":
            raise ImportError("pas de pyodbc")
        return vrai_import(nom, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", sans_pyodbc)
    with pytest.raises(src.SourceInvalide, match="pip install pyodbc"):
        src.connexion_odbc("DRIVER={peu importe}")


def test_la_source_odbc_est_connue():
    assert "odbc" in src.FABRIQUES
