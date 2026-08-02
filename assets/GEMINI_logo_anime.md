# 🎬 Logo animé « Le Cockpit » — mode d'emploi Gemini

Objectif : générer un court clip (2–3 s) qui joue à l'ouverture du dashboard,
puis s'efface pour révéler le tableau de bord. Charte **navy (#0E1E3D) / or (#C6A15B)**.

---

## Étape 1 — Générer la vidéo sur Gemini

Va sur **Gemini** (gemini.google.com) et choisis la génération **vidéo** (Veo).
Colle ce prompt :

> **Prompt (copier-coller) :**
>
> A short 3-second premium logo animation for a data product called "Le Cockpit".
> Dark navy blue background (#0E1E3D) with a subtle radial glow in the center.
> A minimalist gold (#C6A15B) emblem — a circular aviation-style attitude
> indicator / viewfinder with a thin horizon curve and four tick marks —
> draws itself with elegant thin lines, then a soft gold light sweeps across.
> The words "LE COCKPIT" appear in an elegant serif font (Playfair Display style),
> white with a thin gold underline that draws from left to right.
> Cinematic, refined, luxury fintech aesthetic, smooth ease-in-out motion,
> no text glitch, no camera shake. Ends on a clean hold of the full logo.
> 16:9, high quality.

**Réglages conseillés :** durée 3 s, ratio 16:9, qualité max.

### Variante image animée (si tu n'as pas Veo)
Génère d'abord une **image** du logo (même prompt sans les mots « animation/motion »,
en demandant « a static logo, centered, navy background »), puis anime-la avec un
outil type **Runway / Pika / Canva**, ou garde simplement l'animation CSS de secours
déjà intégrée (voir plus bas).

---

## Étape 2 — Récupérer le fichier

- Format idéal : **MP4** (H.264). WebM accepté aussi.
- Durée : **2 à 3 secondes**.
- Renomme le fichier exactement : **`cockpit_logo.mp4`**
- Dépose-le dans ce dossier :
  `Démo Retail (projet clé)/assets/cockpit_logo.mp4`

C'est tout. Au prochain lancement, l'app détecte le fichier et le joue en plein
écran à l'ouverture, puis fond vers le dashboard.

---

## Étape 3 — Ajuster la durée (optionnel)

Le fondu est réglé dans `app.py` :

```python
splash("Le Cockpit",
       sous_titre="Maison Lauret · Pilotage",
       video="assets/cockpit_logo.mp4",
       duree=2.8)          # ← mets la durée de ta vidéo + ~0.3 s
```

## Pas de vidéo ? Aucun souci.
Si `cockpit_logo.mp4` est absent, l'app joue automatiquement une **animation de
secours en CSS/SVG** (emblème or qui tourne + « LE COCKPIT » qui apparaît avec un
trait doré). Le dashboard reste 100 % présentable sans la vidéo Gemini.
