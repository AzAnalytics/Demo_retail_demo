-- =================================================================
-- Le Cockpit — donner l'accès à un prospect, sans rien ouvrir d'autre
-- =================================================================
-- Snowsight propose « Share » sur l'application, mais partager ne suffit
-- pas : la personne doit exister dans ton compte Snowflake. Le chemin
-- complet tient en trois étapes, et une seule se fait à la main.
--
--   1. ce fichier : un rôle qui ne donne accès qu'à l'application ;
--   2. Governance & security > Users & roles > Invite (ou Create user) ;
--   3. Share sur l'application > « Copy link » > « For app viewers ».
--
-- Le lien « For app viewers » ouvre l'écran seul, sans la navigation
-- Snowflake autour : le prospect voit ton produit, pas l'outil.

-- 1. Le rôle. Il ne reçoit ni la table des ventes ni celle des comptes :
--    l'application tourne avec les droits de son propriétaire, donc elle
--    lit les données pour lui sans jamais les lui ouvrir.
CREATE ROLE IF NOT EXISTS COCKPIT_DEMO;

GRANT USAGE ON DATABASE  MAISON_LAURET                      TO ROLE COCKPIT_DEMO;
GRANT USAGE ON SCHEMA    MAISON_LAURET.VENTES               TO ROLE COCKPIT_DEMO;
GRANT USAGE ON STREAMLIT MAISON_LAURET.VENTES.COCKPIT       TO ROLE COCKPIT_DEMO;
GRANT USAGE ON WAREHOUSE WH_XS                              TO ROLE COCKPIT_DEMO;

-- 2. Après avoir invité la personne, lui donner ce rôle, et lui seul.
--    Les guillemets sont obligatoires si l'identifiant contient un point.
-- GRANT ROLE COCKPIT_DEMO TO USER "prenom.nom";
-- ALTER USER "prenom.nom" SET DEFAULT_ROLE = COCKPIT_DEMO;

-- 3. Contrôle : ce rôle ne doit pouvoir lire ni les ventes ni les comptes.
-- USE ROLE COCKPIT_DEMO;
-- USE SECONDARY ROLES NONE;
-- SELECT COUNT(*) FROM MAISON_LAURET.VENTES.TICKETS;   --> refusé
-- SELECT COUNT(*) FROM MAISON_LAURET.VENTES.COMPTES;   --> refusé
-- USE ROLE ACCOUNTADMIN; USE SECONDARY ROLES ALL;

-- Ce que ça coûte : la personne consomme TON entrepôt pendant sa visite.
-- Un WH_XS qui s'éteint au bout d'une minute, c'est quelques centimes par
-- démonstration. À surveiller dans Admin > Cost management.
