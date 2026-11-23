"""
acces.py — le verrou d'entrée du Cockpit
==========================================
Quand le Cockpit tourne sur un poste chez le client, il est joignable par tout
le réseau de l'entreprise : l'atelier, les commerciaux, l'intérimaire de
passage. Les marges et le chiffre d'affaires par client ne sont pas des
informations que le dirigeant veut voir circuler.

Ce verrou demande un mot de passe unique, défini dans `COCKPIT_ACCESS_PASSWORD`
(jamais dans le code). Sans mot de passe configuré, il n'y a pas de verrou :
c'est le cas de la démonstration publique, et c'est voulu.

Ce que ce verrou est, et ce qu'il n'est pas :

  - il empêche un collègue de passage d'ouvrir le tableau de bord ;
  - il ne remplace pas la protection du réseau. Le Cockpit ne doit pas être
    exposé sur internet, seulement sur le réseau local du client.
"""
from __future__ import annotations

import hmac
from datetime import datetime

import streamlit as st

CLEF_SESSION = "_cockpit_acces_ouvert"

# ------------------------------------------------------------------
# L'écran d'embarquement
# ------------------------------------------------------------------
# La métaphore du produit est tenue jusqu'au bout : on ne « se connecte » pas à
# un tableau de bord, on prend place dans un cockpit. La carte reprend la
# charte navy et or, et la forme d'une carte d'embarquement, talon compris.
# Les libellés des champs, eux, restent en français ordinaire : le décor peut
# être une métaphore, pas ce qu'on demande de taper.
_STYLE = """
<style>
/* Fond plein écran pendant l'embarquement : on quitte la salle d'attente. */
[data-testid="stAppViewContainer"] { background: #0E1E3D; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stMainBlockContainer"] { max-width: 820px; padding-top: 0; }
/* Carte centrée dans la hauteur de l'écran, comme une porte d'embarquement. */
[data-testid="stMainBlockContainer"] > div:first-child {
  min-height: 92vh; display: flex; flex-direction: column; justify-content: center; }

/* La carte elle-même */
.st-key-embarquement {
  background: #F7F5EF;
  border-radius: 14px;
  border-top: 4px solid #C6A15B;
  box-shadow: 0 30px 70px rgba(0,0,0,.45);
  padding: 30px 34px 26px;
  position: relative;
  overflow: hidden;
}
/* Le talon détachable, à droite, avec sa perforation */
.st-key-embarquement::before {
  content: ""; position: absolute; top: 0; bottom: 0; right: 132px;
  border-left: 2px dashed rgba(14,30,61,.22);
}
.st-key-embarquement::after {
  content: ""; position: absolute; right: 24px; top: 86px;
  width: 84px; height: 150px; opacity: .85;
  background: repeating-linear-gradient(90deg,
      #0E1E3D 0 2px, transparent 2px 5px, #0E1E3D 5px 6px, transparent 6px 11px);
}
.emb-tete { display: flex; align-items: center; gap: 14px; margin-bottom: 18px; }
.emb-tete .emb-titres { display: flex; flex-direction: column; line-height: 1.25; }
.emb-sur { font-size: 11px; letter-spacing: .22em; color: #8A6D3B;
           text-transform: uppercase; }
.emb-nom { font-family: Playfair Display, Georgia, serif; font-size: 27px;
           color: #0E1E3D; }
.emb-infos { display: flex; gap: 34px; margin: 0 0 20px; padding-bottom: 16px;
             border-bottom: 1px solid rgba(14,30,61,.12); max-width: 420px; }
.emb-infos div { display: flex; flex-direction: column; }
.emb-cle { font-size: 10px; letter-spacing: .16em; color: #5A6478;
           text-transform: uppercase; }
.emb-val { font-size: 14px; color: #0E1E3D; font-weight: 600; }
.emb-pied { margin-top: 14px; font-size: 12px; color: #5A6478; max-width: 420px; }

/* Les champs, dans l'esprit de la carte */
.st-key-embarquement [data-testid="stForm"] { border: 0; padding: 0;
  max-width: 420px; }
.st-key-embarquement label p { font-size: 11px !important; letter-spacing: .16em;
  text-transform: uppercase; color: #5A6478 !important; }
.st-key-embarquement input { background: #FFFFFF !important;
  border: 1px solid rgba(14,30,61,.18) !important; }
.st-key-embarquement [data-testid="stFormSubmitButton"] button {
  background: #0E1E3D; color: #F7F5EF; border: 1px solid #0E1E3D;
  padding: .55rem 1.6rem; letter-spacing: .08em; }
.st-key-embarquement [data-testid="stFormSubmitButton"] button:hover {
  background: #16294D; border-color: #C6A15B; color: #E4C580; }
</style>
"""


def _carte(enseigne: str, ligne_pied: str, acces: str = "Personnel") -> None:
    """Le haut de la carte : emblème, enseigne, et les mentions d'embarquement."""
    from cockpit_theme import _logo_svg      # import tardif : évite un cycle

    aujourdhui = datetime.now().strftime("%d/%m/%Y")
    st.markdown(_STYLE, unsafe_allow_html=True)
    st.markdown(
        f"""<div class="emb-tete">{_logo_svg(46)}
<div class="emb-titres"><span class="emb-sur">Embarquement</span>
<span class="emb-nom">{enseigne}</span></div></div>
<div class="emb-infos">
<div><span class="emb-cle">Vol</span><span class="emb-val">Pilotage</span></div>
<div><span class="emb-cle">Date</span><span class="emb-val">{aujourdhui}</span></div>
<div><span class="emb-cle">Accès</span><span class="emb-val">{acces}</span></div>
</div>""",
        unsafe_allow_html=True,
    )
    st.session_state["_emb_pied"] = ligne_pied


def _pied(texte: str) -> None:
    st.markdown(f'<div class="emb-pied">{texte}</div>', unsafe_allow_html=True)


def est_correct(saisie: str, attendu: str) -> bool:
    """Comparaison à temps constant : on ne renseigne pas sur le bon mot de passe."""
    if not attendu:
        return True
    return hmac.compare_digest(saisie.encode("utf-8"), attendu.encode("utf-8"))


def ouvert(mot_de_passe_attendu: str, enseigne: str = "Le Cockpit") -> bool:
    """Affiche l'écran de saisie tant que le mot de passe n'est pas donné.

    Renvoie True quand l'accès est accordé. L'appelant fait `st.stop()` sinon.
    """
    if not mot_de_passe_attendu:
        return True
    if st.session_state.get(CLEF_SESSION):
        return True

    with st.container(key="embarquement"):
        _carte(enseigne, "Tableau de bord interne. Le mot de passe est donné par "
                         "la direction.")
        saisie = st.text_input("Mot de passe", type="password",
                               key="_cockpit_mot_de_passe")
        if not saisie:
            _pied("Tableau de bord interne. Le mot de passe est donné par la direction.")
            return False
        if est_correct(saisie, mot_de_passe_attendu):
            st.session_state[CLEF_SESSION] = True
            return True
        st.error("Mot de passe incorrect.", icon="🔒")
        return False


# ------------------------------------------------------------------
# Connexion nominative, quand des profils existent
# ------------------------------------------------------------------
CLEF_PROFIL = "_cockpit_profil"

# Les champs de saisie, à vider aussi : sinon le formulaire reviendrait
# pré-rempli avec l'identifiant de la personne précédente. Et le drapeau du
# générique d'ouverture : embarquer de nouveau, c'est revoir l'animation, sinon
# la deuxième personne qui prend le poste entre sans que rien ne le marque.
CLEFS_SESSION = (CLEF_SESSION, CLEF_PROFIL, "_cockpit_mot_de_passe",
                 "_cockpit_splash_done")


CLEF_DEBARQUEMENT = "_cockpit_debarquement"


def deconnecte() -> None:
    """Ferme la session et revient à l'écran de connexion.

    On pose un drapeau pour que l'écran suivant joue le générique de sortie :
    quitter le cockpit se voit, comme y entrer.
    """
    for clef in CLEFS_SESSION:
        st.session_state.pop(clef, None)
    st.session_state[CLEF_DEBARQUEMENT] = True
    st.rerun()


def bouton_deconnexion(conteneur=None, libelle: str = "Se déconnecter") -> None:
    """Le bouton, à placer là où la personne le cherchera."""
    cible = conteneur if conteneur is not None else st
    if cible.button(libelle, key="_bouton_deconnexion"):
        deconnecte()


def session(profils: dict, mot_de_passe_unique: str = "",
            enseigne: str = "Le Cockpit") -> tuple[bool, object | None]:
    """Ouvre la session et renvoie (autorisé, profil).

    Avec un fichier de profils, chacun se connecte avec son identifiant et ne
    verra que son périmètre (voir `permissions.py`). Sans fichier de profils,
    on retombe sur le mot de passe unique, et le profil vaut None.
    """
    import permissions as perm

    if not profils:
        return ouvert(mot_de_passe_unique, enseigne), None

    identifiant = st.session_state.get(CLEF_PROFIL)
    if identifiant and identifiant in profils:
        return True, profils[identifiant]

    with st.container(key="embarquement"):
        _carte(enseigne, "")
        with st.form("connexion", border=False):
            saisi = st.text_input("Identifiant")
            mot_de_passe = st.text_input("Mot de passe", type="password")
            envoye = st.form_submit_button("Embarquer")
        if not envoye:
            _pied("Chacun embarque avec son périmètre : vous ne verrez que ce "
                  "qui vous revient.")
            return False, None

        profil = perm.authentifie(saisi.strip(), mot_de_passe, profils)
        if profil is None:
            # Même message dans les deux cas : on ne dit pas si le compte existe.
            st.error("Identifiant ou mot de passe incorrect.", icon="🔒")
            return False, None
    st.session_state[CLEF_PROFIL] = profil.identifiant
    # Relance immédiate : sans cela le formulaire resterait affiché au-dessus
    # du tableau de bord jusqu'à la prochaine interaction.
    st.rerun()
    return True, profil
