-- =================================================================
-- Le Cockpit — charger les ventes dans Snowflake
-- =================================================================
-- À jouer une fois, dans une feuille SQL Snowsight, en ACCOUNTADMIN
-- (ou un rôle qui peut créer dans la base).
--
-- Pourquoi pas COPY INTO depuis le dépôt Git ?
-- Snowflake refuse COPY INTO depuis un stage de type GIT REPOSITORY
-- (« Unsupported feature »). On passe donc par INSERT ... SELECT, qui lit
-- le même fichier sans difficulté.

CREATE DATABASE IF NOT EXISTS MAISON_LAURET;
CREATE SCHEMA   IF NOT EXISTS MAISON_LAURET.VENTES;

CREATE TABLE IF NOT EXISTS MAISON_LAURET.VENTES.TICKETS (
    DATE_VENTE    DATE,
    MAGASIN       VARCHAR,
    CATEGORIE     VARCHAR,
    PRODUIT       VARCHAR,
    QUANTITE      NUMBER(10,0),
    PRIX_UNITAIRE NUMBER(12,2),
    COUT_UNITAIRE NUMBER(12,2),
    PAIEMENT      VARCHAR,
    CA_TTC        NUMBER(12,2),
    MARGE_TTC     NUMBER(12,2)
);

-- Le format du fichier livré avec le dépôt : un en-tête, pas de guillemets.
CREATE OR REPLACE FILE FORMAT MAISON_LAURET.VENTES.CSV_COCKPIT
    TYPE = CSV SKIP_HEADER = 1;

TRUNCATE TABLE MAISON_LAURET.VENTES.TICKETS;

INSERT INTO MAISON_LAURET.VENTES.TICKETS
SELECT TO_DATE($1,'YYYY-MM-DD'), $2, $3, $4,
       TO_NUMBER($5), TO_NUMBER($6,12,2), TO_NUMBER($7,12,2), $8,
       TO_NUMBER($9,12,2), TO_NUMBER($10,12,2)
FROM @MAISON_LAURET.VENTES.DEMO_RETAIL/branches/main/ventes_maison_lauret.csv
     (FILE_FORMAT => 'MAISON_LAURET.VENTES.CSV_COCKPIT');

-- Contrôle : doit donner 33 841 lignes et 1 200 204 € TTC pour la démonstration.
SELECT COUNT(*)              AS LIGNES,
       MIN(DATE_VENTE)       AS DEBUT,
       MAX(DATE_VENTE)       AS FIN,
       ROUND(SUM(CA_TTC))    AS CA_TTC
FROM MAISON_LAURET.VENTES.TICKETS;
