# Le Cockpit — image pour Google Cloud Run
# Cloud Run fournit la variable PORT (8080 par défaut) ; Streamlit doit l'écouter.
FROM python:3.12-slim

# Dépendances système minimales
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 1) Dépendances Python (couche cachée tant que requirements ne change pas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Code de l'application
COPY . .

# Cloud Run écoute sur $PORT (défaut 8080)
ENV PORT=8080
EXPOSE 8080

# Lancement de Streamlit, headless, sur le port fourni par Cloud Run.
#
# NOTE — ne pas réintroduire « --server.enableCORS=false » :
# cette option est incompatible avec --server.enableXsrfProtection=true.
# Streamlit l'ignore et la repasse à true en affichant un avertissement au
# démarrage. Elle n'est de toute façon pas nécessaire pour embarquer l'app en
# iframe : la page intégrée est servie par la même origine que le websocket.
# On garde donc la protection XSRF active (c'est le réglage sûr).
CMD streamlit run app.py \
    --server.port=${PORT} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableXsrfProtection=true \
    --browser.gatherUsageStats=false
