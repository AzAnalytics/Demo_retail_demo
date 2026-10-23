"""Ouvre l'application Streamlit dans un vrai navigateur et la réveille si elle dort."""
from playwright.sync_api import sync_playwright

URL = "https://maison-lauret-demo.streamlit.app/"
BOUTON_REVEIL = "Yes, get this app back up!"

with sync_playwright() as p:
    navigateur = p.chromium.launch()
    page = navigateur.new_page()
    page.goto(URL, timeout=90_000)
    page.wait_for_timeout(10_000)

    bouton = page.get_by_role("button", name=BOUTON_REVEIL)
    if bouton.count() > 0:
        bouton.first.click()
        print("L'application dormait : réveil demandé.")
        page.wait_for_timeout(60_000)
    else:
        print("L'application est déjà active.")

    navigateur.close()
