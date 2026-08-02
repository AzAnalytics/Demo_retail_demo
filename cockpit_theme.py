"""
cockpit_theme.py — Identité visuelle "Le Cockpit"
==================================================
Module réutilisable pour donner à n'importe quel dashboard Streamlit
l'allure premium du Cockpit (charte navy/or), un en-tête avec logo,
et un écran d'ouverture animé (splash) qui joue AVANT le tableau de bord.

Usage minimal dans une app Streamlit :

    import streamlit as st
    from cockpit_theme import apply_theme, splash, header

    st.set_page_config(page_title="…", layout="wide")
    apply_theme()                 # 1. charte navy/or
    splash("Le Cockpit",          # 2. écran d'ouverture animé (1re visite)
           sous_titre="Maison Lauret · Pilotage",
           video="assets/cockpit_logo.mp4")   # vidéo Gemini si dispo, sinon anim CSS
    header("Maison Lauret",       # 3. en-tête avec logo
           "Concept store déco-maison · 3 boutiques")
    # … le reste du dashboard …

Auteur : Alexis Zueras — produit "Le Cockpit".
"""
from __future__ import annotations
import base64
import os
import streamlit as st

# ==================================================================
# PALETTE — charte navy / or
# ==================================================================
COCKPIT = {
    "navy":        "#0E1E3D",   # bleu nuit profond (fond splash, titres)
    "navy_soft":   "#16294D",   # cartes / surfaces sombres
    "navy_line":   "#22345C",   # filets discrets
    "gold":        "#C6A15B",   # or mat (accents, filets)
    "gold_bright": "#E4C580",   # or clair (survol, halo)
    "paper":       "#F7F5EF",   # crème (fond de page)
    "surface":     "#FFFFFF",   # cartes claires
    "ink":         "#101828",   # texte principal
    "muted":       "#5A6478",   # texte secondaire
    "green":       "#2E8B6A",   # hausse / positif
    "red":         "#C0392B",   # alerte / baisse
}

# Palette catégorielle harmonisée navy/or (pour les graphes Plotly)
COCKPIT_SEQ = ["#0E1E3D", "#C6A15B", "#3E6D9C", "#8A6D3B",
               "#5C7A99", "#B08D57", "#2E8B6A", "#8892A6"]


def plotly_layout(fig, hauteur: int = 360):
    """Applique le look Cockpit à une figure Plotly (à appeler sur chaque graphe)."""
    fig.update_layout(
        height=hauteur,
        margin=dict(l=10, r=10, t=44, b=10),
        separators=", ",
        legend_title_text="",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, 'Segoe UI', sans-serif",
                  color=COCKPIT["ink"], size=13),
        title=dict(text=(fig.layout.title.text or ""),
                   font=dict(family="'Playfair Display', Georgia, serif",
                             color=COCKPIT["navy"], size=16)),
        colorway=COCKPIT_SEQ,
        hoverlabel=dict(bgcolor=COCKPIT["navy"], font_color="#FFFFFF",
                        font_family="Inter, sans-serif"),
    )
    fig.update_xaxes(showgrid=False, linecolor="#E4DFD3", zeroline=False)
    fig.update_yaxes(gridcolor="#ECE7DB", zeroline=False)
    return fig


def _md(html: str) -> None:
    """Injecte du HTML brut sans que Streamlit ne le prenne pour un bloc de code.

    On retire l'indentation de gauche de chaque ligne : sinon Markdown interprète
    les lignes indentées (>=4 espaces) comme du code et affiche le CSS en clair.
    """
    cleaned = "\n".join(line.lstrip() for line in html.splitlines())
    st.markdown(cleaned, unsafe_allow_html=True)


# ==================================================================
# CHARTE CSS
# ==================================================================
def apply_theme() -> None:
    """Injecte la charte navy/or (typographie, cartes, KPI, onglets, alertes)."""
    c = COCKPIT
    _md(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Inter:wght@400;500;600;700&display=swap');
    :root {{
        --navy:{c['navy']}; --navy-soft:{c['navy_soft']}; --gold:{c['gold']};
        --gold-bright:{c['gold_bright']}; --paper:{c['paper']}; --ink:{c['ink']};
        --muted:{c['muted']};
    }}

    /* --- Fond & typographie générale --- */
    .stApp {{ background: var(--paper); }}
    html, body, [class*="css"] {{
        font-family: 'Inter','Segoe UI',sans-serif; color: var(--ink);
    }}
    .block-container {{ padding-top: 2.2rem; max-width: 1250px; }}

    h1, h2, h3 {{ font-family:'Playfair Display',Georgia,serif; color: var(--navy);
                  letter-spacing:.2px; }}
    h1 {{ font-weight:700; }}
    .stApp h2, .stApp h3 {{ font-weight:600; }}

    /* --- En-tête Cockpit --- */
    .cockpit-header {{
        display:flex; align-items:center; gap:18px;
        background: linear-gradient(100deg, var(--navy) 0%, var(--navy-soft) 100%);
        border-radius:16px; padding:20px 26px; margin-bottom:8px;
        box-shadow:0 10px 30px rgba(14,30,61,.18);
        border:1px solid rgba(198,161,91,.35);
    }}
    .cockpit-mark {{ flex:0 0 auto; }}
    .cockpit-header .title {{ display:flex; flex-direction:column; line-height:1.15; }}
    .cockpit-header .eyebrow {{
        font-family:'Inter',sans-serif; font-size:.72rem; font-weight:600;
        letter-spacing:.22em; text-transform:uppercase; color:var(--gold-bright);
        margin-bottom:2px;
    }}
    .cockpit-header .maintitle {{
        font-family:'Playfair Display',serif; font-size:1.7rem; font-weight:700;
        color:#FFFFFF;
    }}
    .cockpit-header .subtitle {{
        font-family:'Inter',sans-serif; font-size:.9rem; color:#C7D0E0; margin-top:3px;
    }}

    /* --- Cartes KPI (st.metric) --- */
    [data-testid="stMetric"] {{
        background: var(--surface, #fff);
        border:1px solid #ECE7DB; border-top:3px solid var(--gold);
        border-radius:14px; padding:16px 18px 14px;
        box-shadow:0 4px 14px rgba(14,30,61,.06);
        transition:transform .15s ease, box-shadow .15s ease;
    }}
    [data-testid="stMetric"]:hover {{
        transform:translateY(-2px); box-shadow:0 8px 22px rgba(14,30,61,.12);
    }}
    [data-testid="stMetricLabel"] p {{
        font-size:.8rem; font-weight:600; letter-spacing:.02em;
        text-transform:uppercase; color:var(--muted);
    }}
    [data-testid="stMetricValue"] {{
        font-family:'Playfair Display',serif; font-weight:700;
        color:var(--navy); font-size:1.75rem;
    }}

    /* --- Onglets --- */
    .stTabs [data-baseweb="tab-list"] {{ gap:4px; border-bottom:1px solid #E4DFD3; }}
    .stTabs [data-baseweb="tab"] {{
        font-weight:600; color:var(--muted); border-radius:10px 10px 0 0;
        padding:8px 16px;
    }}
    .stTabs [aria-selected="true"] {{
        color:var(--navy) !important; background:rgba(198,161,91,.10);
        border-bottom:2px solid var(--gold) !important;
    }}

    /* --- Alertes --- */
    [data-testid="stAlert"] {{ border-radius:12px; border:none;
        box-shadow:0 3px 10px rgba(14,30,61,.06); }}

    /* --- Sidebar masquée (les filtres sont dans le panneau « Filtres ») --- */
    section[data-testid="stSidebar"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {{ display:none !important; }}

    /* --- Panneau « Filtres » (expander) façon bouton premium --- */
    [data-testid="stExpander"] {{
        border:1px solid #E4DFD3; border-radius:12px; overflow:hidden;
        box-shadow:0 3px 12px rgba(14,30,61,.06); background:#fff;
        margin-bottom:6px;
    }}
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] details > summary {{
        font-family:'Inter',sans-serif; font-weight:600; color:var(--navy);
        background:rgba(198,161,91,.10); padding:10px 16px;
    }}
    [data-testid="stExpander"] summary:hover {{ background:rgba(198,161,91,.18); }}
    /* Tags sélectionnés (multiselect) en or */
    [data-baseweb="tag"] {{ background:var(--gold) !important; }}
    [data-baseweb="tag"] * {{ color:var(--navy) !important; }}

    /* --- Calendrier (date_input) : texte foncé sur fond clair --- */
    [data-baseweb="calendar"] {{ background:#FFFFFF; }}
    [data-baseweb="calendar"] *,
    [data-baseweb="popover"] [data-baseweb="calendar"] * {{ color:var(--ink) !important; }}
    [data-baseweb="calendar"] [aria-selected="true"] {{
        background:var(--gold) !important; color:var(--navy) !important; }}

    /* --- Boutons --- */
    .stDownloadButton button, .stButton button {{
        background:var(--navy); color:#fff; border:1px solid var(--gold);
        border-radius:10px; font-weight:600;
    }}
    .stDownloadButton button:hover, .stButton button:hover {{
        background:var(--navy-soft); border-color:var(--gold-bright); color:#fff;
    }}

    /* --- Divers --- */
    hr {{ border-color:#E4DFD3; }}
    .cockpit-foot {{ color:var(--muted); font-size:.8rem; text-align:center;
                     padding:14px 0; }}
    #MainMenu, footer {{ visibility:hidden; }}
    </style>
    """)


# ==================================================================
# LOGO (SVG inline) — utilisé dans l'en-tête et le splash de secours
# ==================================================================
def _logo_svg(size: int = 46, color: str = "#C6A15B", ring: str = "#E4C580") -> str:
    """Petit emblème 'cockpit' : viseur / horizon artificiel stylisé."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 100 100" fill="none"
         xmlns="http://www.w3.org/2000/svg" class="cockpit-mark">
      <circle cx="50" cy="50" r="44" stroke="{color}" stroke-width="3"/>
      <circle cx="50" cy="50" r="33" stroke="{ring}" stroke-width="1.4" opacity=".6"/>
      <path d="M18 56 Q50 40 82 56" stroke="{ring}" stroke-width="2.4" fill="none"/>
      <line x1="50" y1="8"  x2="50" y2="24" stroke="{color}" stroke-width="3"/>
      <line x1="50" y1="76" x2="50" y2="92" stroke="{color}" stroke-width="3"/>
      <line x1="8"  y1="50" x2="24" y2="50" stroke="{color}" stroke-width="3"/>
      <line x1="76" y1="50" x2="92" y2="50" stroke="{color}" stroke-width="3"/>
      <circle cx="50" cy="50" r="5" fill="{color}"/>
    </svg>
    """


def header(titre: str, sous_titre: str = "", eyebrow: str = "LE COCKPIT") -> None:
    """En-tête premium avec logo, sur-titre 'LE COCKPIT', titre et sous-titre."""
    _md(f"""
    <div class="cockpit-header">
      {_logo_svg(50)}
      <div class="title">
        <span class="eyebrow">{eyebrow}</span>
        <span class="maintitle">{titre}</span>
        {f'<span class="subtitle">{sous_titre}</span>' if sous_titre else ''}
      </div>
    </div>
    """)


# ==================================================================
# SPLASH — écran d'ouverture animé (vidéo Gemini + secours CSS)
# ==================================================================
def _b64_video(path: str) -> str | None:
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


def splash(titre: str = "Le Cockpit",
           sous_titre: str = "",
           video: str | None = None,
           duree: float = 2.8,
           once: bool = True) -> None:
    """
    Affiche l'écran d'ouverture plein écran AVANT le dashboard.

    • Si `video` pointe vers un fichier existant (.mp4 conseillé, ou .webm),
      la vidéo Gemini est jouée en plein écran puis l'écran s'efface.
    • Sinon, une animation CSS/SVG de secours "Le Cockpit" est jouée.

    L'écran se retire tout seul (pur CSS, aucun JS requis) après `duree` s.
    `once=True` : ne rejoue pas le splash sur les reruns (filtres, etc.).
    """
    if once:
        if st.session_state.get("_cockpit_splash_done"):
            return
        st.session_state["_cockpit_splash_done"] = True

    c = COCKPIT
    fade_start = max(duree - 0.6, 0.2)
    hold = fade_start / duree            # part visible avant fondu
    b64 = _b64_video(video) if video else None

    # Média central : vidéo Gemini si dispo, sinon wordmark animé
    if b64:
        ext = (video or "").lower()
        mime = "video/webm" if ext.endswith(".webm") else "video/mp4"
        media = f"""
          <video autoplay muted playsinline class="ck-video">
            <source src="data:{mime};base64,{b64}" type="{mime}">
          </video>"""
    else:
        media = f"""
          <div class="ck-fallback">
            {_logo_svg(96, c['gold'], c['gold_bright'])}
            <div class="ck-word">
              <span class="ck-eyebrow">EMBARQUEMENT</span>
              <span class="ck-title">{titre}</span>
              <span class="ck-line"></span>
              {f'<span class="ck-sub">{sous_titre}</span>' if sous_titre else ''}
            </div>
          </div>"""

    _md(f"""
    <style>
    @keyframes ckHide {{
        0%, {hold*100:.0f}% {{ opacity:1; visibility:visible; }}
        100% {{ opacity:0; visibility:hidden; }}
    }}
    @keyframes ckRise {{
        0% {{ opacity:0; transform:translateY(14px); }}
        100% {{ opacity:1; transform:translateY(0); }}
    }}
    @keyframes ckDraw {{ 0% {{ width:0; }} 100% {{ width:150px; }} }}
    @keyframes ckSpin {{ to {{ transform:rotate(360deg); }} }}

    .cockpit-splash {{
        position:fixed; top:0; left:0; right:0; bottom:0;
        width:100vw; height:100vh; min-height:100dvh; margin:0;
        z-index:2147483647;                 /* au-dessus de tout (header, sidebar) */
        display:flex; align-items:center; justify-content:center;
        background:radial-gradient(circle at 50% 40%, {c['navy_soft']} 0%, {c['navy']} 70%);
        animation:ckHide {duree}s ease forwards;
    }}
    .cockpit-splash .cockpit-mark {{ animation:ckSpin 9s linear infinite; }}
    .ck-video {{ width:min(70vw,620px); height:auto; border-radius:14px;
                 box-shadow:0 20px 60px rgba(0,0,0,.45); }}
    .ck-fallback {{ display:flex; flex-direction:column; align-items:center;
                    gap:22px; animation:ckRise .9s ease both; }}
    .ck-word {{ display:flex; flex-direction:column; align-items:center; }}
    .ck-eyebrow {{ font-family:'Inter',sans-serif; font-size:.72rem; font-weight:600;
                   letter-spacing:.4em; color:{c['gold_bright']}; }}
    .ck-title {{ font-family:'Playfair Display',serif; font-weight:700;
                 font-size:2.8rem; color:#fff; margin-top:6px; }}
    .ck-line {{ height:2px; width:0; margin:12px 0 4px;
                background:linear-gradient(90deg,transparent,{c['gold']},transparent);
                animation:ckDraw 1.1s ease .3s forwards; }}
    .ck-sub {{ font-family:'Inter',sans-serif; font-size:.95rem; color:#C7D0E0;
               letter-spacing:.05em; }}
    </style>
    <div class="cockpit-splash">
      {media}
    </div>
    """)


def footer(texte: str) -> None:
    _md(f'<div class="cockpit-foot">{texte}</div>')
