"""
cockpit_calculs.py — tout ce que le Cockpit calcule
====================================================
Les chiffres sont ici, l'affichage est dans `app.py`. Deux raisons :

  - on peut les **tester** (voir `test_cockpit.py`), donc modifier l'écran sans
    casser un indicateur sans s'en apercevoir ;
  - on peut les **expliquer** : quand un dirigeant demande « ça veut dire quoi,
    exactement ? », la réponse tient dans ce fichier, pas éparpillée dans 340
    lignes de mise en page.

Convention de prix, valable partout : le fichier de caisse contient des prix
boutique, donc TTC. Tout ce qui sort d'ici est **hors taxes**, parce que c'est
la base dont parlent un dirigeant et son expert-comptable. Le coût d'achat est
déjà hors taxes : le commerçant récupère la TVA qu'il paie à ses fournisseurs.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin",
           "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
JOURS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

# Une alerte n'est utile que si elle pèse : en dessous, c'est du bruit qui fait
# perdre confiance. Un écart doit dépasser le seuil en pourcentage ET ce montant.
MONTANT_MINIMAL_ALERTE = 300.0


# ------------------------------------------------------------------
# Mise en forme
# ------------------------------------------------------------------
def euros(montant: float) -> str:
    """1234.5 devient '1 235 €'."""
    return f"{montant:,.0f} €".replace(",", " ")


def libelle_mois(ts) -> str:
    """Un horodatage devient 'octobre 2026'."""
    if ts is None or pd.isna(ts):
        return "—"
    ts = pd.Timestamp(ts)
    return f"{MOIS_FR[ts.month - 1]} {ts.year}"


def variation(actuel: float, precedent: float, suffixe: str = "%") -> str | None:
    """'+12.3%', ou None si la comparaison n'a pas de sens (référence nulle)."""
    if not precedent:
        return None
    return f"{(actuel - precedent) / precedent * 100:+.1f}{suffixe}"


# ------------------------------------------------------------------
# Du fichier de caisse aux montants hors taxes
# ------------------------------------------------------------------
def montants_hors_taxes(df: pd.DataFrame, taux_tva: float) -> pd.DataFrame:
    """Ajoute `ca` et `marge`, tous deux hors taxes, à partir des prix boutique.

    `taux_tva = 0` quand le fichier d'un client est déjà en hors taxes.
    """
    sortie = df.copy()
    sortie["ca"] = sortie["ca_ttc"] / (1.0 + taux_tva)
    cout = sortie["quantite"] * sortie["cout_unitaire"].fillna(0.0)
    sortie["marge"] = sortie["ca"] - cout
    return sortie


# ------------------------------------------------------------------
# Le mois regardé, et celui auquel on le compare
# ------------------------------------------------------------------
@dataclass
class Periode:
    """Le mois de référence, son mois de comparaison, et comment le dire."""

    mois: pd.Timestamp
    comparaison: pd.Timestamp | None
    type_comparaison: str      # "au même mois un an avant" | "au mois précédent disponible"
    en_cours: bool = False     # le mois analysé n'est pas terminé
    jour_arret: int | None = None   # dernier jour vendu, quand le mois est en cours

    @property
    def note(self) -> str:
        """La phrase à afficher quand la comparaison a été tronquée."""
        if not self.en_cours or self.jour_arret is None:
            return ""
        return (f" Mois en cours : la comparaison s'arrête au {self.jour_arret} "
                f"des deux côtés, à périmètre égal.")


def periode_de_reference(d: pd.DataFrame, aujourdhui=None) -> Periode:
    """Le dernier mois du fichier, comparé au même mois un an avant.

    Comparer au mois précédent dans un commerce saisonnier n'a pas de sens
    (décembre bat toujours novembre). On ne s'y rabat que si l'an dernier
    n'existe pas dans les données, et l'écran le dit alors au visiteur.

    Si le mois analysé est **en cours**, la comparaison doit être tronquée au
    même jour des deux côtés : opposer vingt jours à un mois entier fabrique
    une baisse qui n'existe pas. C'est le calendrier qui décide, pas la
    dernière vente du fichier : un mois clos dont la dernière vente tombe le 29
    est un mois complet.
    """
    mois_ref = d["mois"].max()
    jour = pd.Timestamp(aujourdhui).normalize() if aujourdhui is not None else pd.Timestamp.today().normalize()
    fin_du_mois = mois_ref + pd.offsets.MonthEnd(0)
    en_cours = bool(fin_du_mois.normalize() >= jour)
    arret = int(d.loc[d["mois"] == mois_ref, "date"].max().day) if en_cours else None

    an_dernier = mois_ref - pd.DateOffset(years=1)
    if not d[d["mois"] == an_dernier].empty:
        return Periode(mois_ref, an_dernier, "au même mois un an avant", en_cours, arret)
    precedent = d.loc[d["mois"] < mois_ref, "mois"].max()
    if pd.isna(precedent):
        return Periode(mois_ref, None, "à rien : c'est le premier mois du fichier",
                       en_cours, arret)
    return Periode(mois_ref, precedent, "au mois précédent disponible", en_cours, arret)


def a_perimetre_egal(cmp: pd.DataFrame, periode: Periode) -> pd.DataFrame:
    """Tronque le mois de comparaison au même jour que le mois en cours."""
    if not periode.en_cours or periode.jour_arret is None or cmp.empty:
        return cmp
    return cmp[cmp["date"].dt.day <= periode.jour_arret]


# ------------------------------------------------------------------
# Les quatre indicateurs
# ------------------------------------------------------------------
@dataclass
class Indicateurs:
    """Les quatre chiffres du haut de l'écran, tous hors taxes."""

    ca: float
    marge: float
    taux_marge: float      # en pourcentage
    panier: float          # chiffre d'affaires par ticket
    tickets: int


def indicateurs(x: pd.DataFrame) -> Indicateurs:
    """Chiffre d'affaires, marge, taux de marge et panier moyen d'une sélection.

    Le panier moyen est le chiffre d'affaires divisé par le nombre de tickets.
    Ici une ligne du fichier est un ticket ; chez un client dont les tickets ont
    plusieurs lignes, il faudra d'abord regrouper par numéro de ticket.
    """
    ca = float(x["ca"].sum())
    marge = float(x["marge"].sum())
    return Indicateurs(
        ca=ca,
        marge=marge,
        taux_marge=(marge / ca * 100) if ca else 0.0,
        panier=(ca / len(x)) if len(x) else 0.0,
        tickets=len(x),
    )


# ------------------------------------------------------------------
# Les alertes
# ------------------------------------------------------------------
@dataclass
class AlerteCategorie:
    """Une catégorie qui décroche ou qui décolle, en pourcentage ET en euros."""

    categorie: str
    variation_pct: float
    ecart_eur: float       # négatif en cas de baisse
    ca_mois: float
    ca_reference: float

    @property
    def en_baisse(self) -> bool:
        return self.ecart_eur < 0

    def phrase(self, type_comparaison: str) -> str:
        repere = type_comparaison.replace("au ", "vs ").replace("à ", "vs ")
        if self.en_baisse:
            return (f"**{self.categorie}** recule de {abs(self.variation_pct):.1f} % "
                    f"{repere}, soit {euros(abs(self.ecart_eur))} de chiffre d'affaires "
                    f"en moins sur le mois.")
        return (f"**{self.categorie}** progresse de +{self.variation_pct:.1f} %, "
                f"soit {euros(self.ecart_eur)} de plus sur le mois.")


def alertes_categories(
    cur: pd.DataFrame,
    cmp: pd.DataFrame,
    seuil_pct: float,
    montant_minimal: float = MONTANT_MINIMAL_ALERTE,
) -> tuple[list[AlerteCategorie], list[AlerteCategorie]]:
    """Les catégories qui bougent de plus de `seuil_pct`, triées par euros.

    Le montant minimal évite l'alerte ridicule : une famille à 400 € qui perd
    15 % ne mérite pas la même ligne rouge qu'une famille à 40 000 €.
    """
    if cur.empty or cmp.empty:
        return [], []
    ca_mois = cur.groupby("categorie")["ca"].sum()
    ca_ref = cmp.groupby("categorie")["ca"].sum()

    baisses: list[AlerteCategorie] = []
    hausses: list[AlerteCategorie] = []
    for categorie in ca_mois.index:
        reference = float(ca_ref.get(categorie, 0.0))
        if reference <= 0:
            continue
        valeur = float(ca_mois[categorie])
        ecart = valeur - reference
        pourcentage = ecart / reference * 100
        if abs(ecart) < montant_minimal or abs(pourcentage) < seuil_pct:
            continue
        alerte = AlerteCategorie(categorie, pourcentage, ecart, valeur, reference)
        (baisses if ecart < 0 else hausses).append(alerte)

    baisses.sort(key=lambda a: a.ecart_eur)            # la plus grosse perte d'abord
    hausses.sort(key=lambda a: -a.ecart_eur)
    return baisses, hausses


# ------------------------------------------------------------------
# L'objectif
# ------------------------------------------------------------------
def objectif_du_mois(ca_reference: float, croissance: float) -> float | None:
    """L'objectif, soit le même mois l'an dernier augmenté de `croissance`."""
    return ca_reference * croissance if ca_reference else None
