# Le Cockpit — image de production
# ============================================================
# Sert pour les deux usages, sans modification :
#   - chez un client, sur son serveur     -> voir docker-compose.yml
#   - sur Google Cloud Run                -> la variable PORT est fournie
#
# Deux principes tenus ici :
#   1. aucun secret ni compte client dans l'image (voir .dockerignore) ;
#      les comptes arrivent par un volume monté sur /config ;
#   2. l'application ne tourne pas en root, parce que c'est la première
#      question d'un informaticien qui relit une image.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 1) Dépendances Python, en couche séparée : tant que requirements.txt ne
#    change pas, une reconstruction ne les réinstalle pas.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Code de l'application
COPY . .

# 3) Un utilisateur sans privilèges, et le dossier où le client montera ses
#    comptes et ses données. /app doit rester inscriptible : la démonstration
#    régénère son fichier de ventes quand il est périmé.
RUN useradd --create-home --uid 10001 cockpit \
    && mkdir -p /config \
    && chown -R cockpit:cockpit /app /config
USER cockpit

ENV PORT=8080
EXPOSE 8080

# Docker sait ainsi si l'application répond vraiment, pas seulement si le
# conteneur est allumé. C'est ce qui déclenche un redémarrage automatique.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT','8080') + '/_stcore/health')" || exit 1

# Forme JSON avec `exec` : la variable PORT est bien remplacée, et Streamlit
# devient le processus principal, donc `docker stop` l'arrête proprement au
# lieu d'attendre dix secondes avant de le tuer.
CMD ["sh", "-c", "exec streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=true"]
