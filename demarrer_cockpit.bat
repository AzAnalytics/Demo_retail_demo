@echo off
REM ====================================================================
REM  Le Cockpit - demarrage sur un poste Windows (chez le client)
REM --------------------------------------------------------------------
REM  A lancer par la tache planifiee creee dans DEPLOIEMENT-CHEZ-LE-CLIENT.md,
REM  ou a la main pour verifier que tout demarre.
REM
REM  Les reglages (source de donnees, identifiants, mot de passe d'acces)
REM  sont lus dans le fichier .env place a cote de ce script. Rien de
REM  sensible n'est ecrit ici.
REM ====================================================================

cd /d "%~dp0"

REM --- L'interpreteur : venv local s'il existe, sinon le Python du poste ---
set "PYTHON=%~dp0venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

REM --- Les journaux, un fichier par jour, pour pouvoir diagnostiquer ---
if not exist "logs" mkdir "logs"
for /f "tokens=1-3 delims=/-. " %%a in ("%date%") do set "JOUR=%%c-%%b-%%a"

echo [%date% %time%] demarrage du Cockpit >> "logs\cockpit-%JOUR%.log"

REM  --server.address 0.0.0.0 : joignable depuis les autres postes du reseau
REM  --server.headless true   : pas de navigateur ouvert sur le poste
REM  --fileWatcherType none   : pas de rechargement auto, c'est de la production
"%PYTHON%" -m streamlit run app.py ^
    --server.port 8501 ^
    --server.address 0.0.0.0 ^
    --server.headless true ^
    --server.fileWatcherType none ^
    --browser.gatherUsageStats false ^
    >> "logs\cockpit-%JOUR%.log" 2>&1

echo [%date% %time%] le Cockpit s'est arrete (code %errorlevel%) >> "logs\cockpit-%JOUR%.log"
