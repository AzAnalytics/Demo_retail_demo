-- =================================================================
-- Le Cockpit — qui voit quelles lignes, dans l'entrepôt lui-même
-- =================================================================
-- Deux niveaux de sécurité se superposent, et c'est voulu :
--
--   1. l'application : comptes, rôles et périmètres (profils.demo.json),
--      avec le périmètre poussé dans le WHERE de la requête ;
--   2. l'entrepôt : ce fichier. Même si quelqu'un se connecte à Snowflake
--      sans passer par le Cockpit, il ne voit que ses lignes.
--
-- Édition Snowflake : les ROW ACCESS POLICY demandent l'édition Enterprise.
-- En Standard, Snowflake répond « Unsupported feature ». La vue sécurisée
-- ci-dessous donne le même résultat et fonctionne dans toutes les éditions.

-- 1. La correspondance rôle -> magasin. Une ligne à ajouter par responsable,
--    sans toucher au code ni à la vue. '*' veut dire « tous les magasins ».
CREATE OR REPLACE TABLE MAISON_LAURET.VENTES.ACCES_MAGASIN (
    ROLE_SF VARCHAR,
    MAGASIN VARCHAR
);
INSERT INTO MAISON_LAURET.VENTES.ACCES_MAGASIN VALUES
    ('COCKPIT_DIRECTION','*'),
    ('COCKPIT_TOULOUSE','Toulouse'),
    ('COCKPIT_AUCH','Auch');

-- 2. La vue sécurisée. SECURE veut dire que Snowflake n'en laisse pas deviner
--    le contenu par le plan d'exécution : sans cela, un utilisateur curieux
--    pourrait déduire des lignes qu'il ne voit pas.
CREATE OR REPLACE SECURE VIEW MAISON_LAURET.VENTES.VENTES_PAR_ROLE AS
SELECT t.*
FROM MAISON_LAURET.VENTES.TICKETS t
WHERE CURRENT_ROLE() IN ('ACCOUNTADMIN','SYSADMIN')
   OR EXISTS (SELECT 1
              FROM MAISON_LAURET.VENTES.ACCES_MAGASIN a
              WHERE a.ROLE_SF = CURRENT_ROLE()
                AND (a.MAGASIN = '*' OR a.MAGASIN = t.MAGASIN));

-- 3. Les rôles. Ils reçoivent la vue, jamais la table : c'est ce qui empêche
--    de contourner le filtre en lisant la source.
CREATE ROLE IF NOT EXISTS COCKPIT_TOULOUSE;
CREATE ROLE IF NOT EXISTS COCKPIT_AUCH;

GRANT USAGE  ON DATABASE  MAISON_LAURET                      TO ROLE COCKPIT_TOULOUSE;
GRANT USAGE  ON SCHEMA    MAISON_LAURET.VENTES               TO ROLE COCKPIT_TOULOUSE;
GRANT SELECT ON VIEW      MAISON_LAURET.VENTES.VENTES_PAR_ROLE TO ROLE COCKPIT_TOULOUSE;
GRANT USAGE  ON WAREHOUSE WH_XS                              TO ROLE COCKPIT_TOULOUSE;

GRANT USAGE  ON DATABASE  MAISON_LAURET                      TO ROLE COCKPIT_AUCH;
GRANT USAGE  ON SCHEMA    MAISON_LAURET.VENTES               TO ROLE COCKPIT_AUCH;
GRANT SELECT ON VIEW      MAISON_LAURET.VENTES.VENTES_PAR_ROLE TO ROLE COCKPIT_AUCH;
GRANT USAGE  ON WAREHOUSE WH_XS                              TO ROLE COCKPIT_AUCH;

-- Un identifiant contenant des points doit être entre guillemets.
-- GRANT ROLE COCKPIT_TOULOUSE TO USER "prenom.nom";

-- 4. La vérification. Attention : Snowsight active les RÔLES SECONDAIRES,
--    donc une session garde en arrière-plan les droits des autres rôles de la
--    personne. Sans la ligne suivante, le test est faussé et tout semble
--    autorisé.
-- USE ROLE COCKPIT_TOULOUSE;
-- USE SECONDARY ROLES NONE;
-- SELECT COUNT(*) FROM MAISON_LAURET.VENTES.VENTES_PAR_ROLE;  --> 16 951 lignes
-- SELECT COUNT(*) FROM MAISON_LAURET.VENTES.TICKETS;          --> refusé
-- USE ROLE ACCOUNTADMIN; USE SECONDARY ROLES ALL;
