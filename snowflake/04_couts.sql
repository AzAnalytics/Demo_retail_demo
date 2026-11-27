-- =================================================================
-- Le Cockpit — plafonner la dépense, et la rendre lisible
-- =================================================================
-- Ce que ce script met en place, dans l'ordre :
--
--   1. un moniteur de ressources : un quota mensuel en crédits, des
--      alertes par courriel en chemin, et la suspension de l'entrepôt
--      au-delà. C'est le seul garde-fou qui agisse tout seul, la nuit,
--      quand personne ne regarde la facture ;
--   2. un entrepôt qui s'éteint vite et qui ne peut pas s'emballer ;
--   3. le droit de LIRE la facturation, donné au rôle de direction, pour
--      que le panneau « Ce que l'entrepôt a coûté » du Cockpit affiche
--      des chiffres au lieu d'un refus.
--
-- À exécuter en ACCOUNTADMIN : créer un moniteur et le rattacher à un
-- entrepôt n'est permis à personne d'autre, et c'est heureux.
--
-- Le script est rejouable : chaque objet est créé « OR REPLACE » ou
-- « IF NOT EXISTS », donc le relancer ne casse rien.

USE ROLE ACCOUNTADMIN;

-- -----------------------------------------------------------------
-- 1. Le plafond
-- -----------------------------------------------------------------
-- Dix crédits par mois, soit environ 25 € : largement de quoi faire
-- tourner des démonstrations et des essais, et bien trop peu pour qu'un
-- oubli devienne une mauvaise surprise. À monter chez un client, après
-- avoir mesuré un mois réel.
--
-- Les paliers servent à deux choses différentes :
--   NOTIFY  prévient (courriel aux administrateurs du compte) ;
--   SUSPEND laisse finir les requêtes en cours puis arrête l'entrepôt ;
--   SUSPEND_IMMEDIATE coupe net, y compris une requête en cours.
--
-- Important : les courriels ne partent qu'aux administrateurs qui ont
-- activé les notifications dans Snowsight (menu du compte >
-- Notifications). Sans cela, le quota agit mais prévient personne.
CREATE OR REPLACE RESOURCE MONITOR MONITEUR_COCKPIT
    WITH CREDIT_QUOTA = 10
         FREQUENCY = MONTHLY
         START_TIMESTAMP = IMMEDIATELY
         TRIGGERS
             ON 50  PERCENT DO NOTIFY
             ON 80  PERCENT DO NOTIFY
             ON 100 PERCENT DO SUSPEND
             ON 110 PERCENT DO SUSPEND_IMMEDIATE;

ALTER WAREHOUSE WH_XS SET RESOURCE_MONITOR = MONITEUR_COCKPIT;

-- -----------------------------------------------------------------
-- 2. L'entrepôt : petit, vite endormi, incapable de s'emballer
-- -----------------------------------------------------------------
-- AUTO_SUSPEND = 60 : l'entrepôt s'éteint après une minute sans requête.
-- Snowflake facture au moins une minute à chaque réveil, donc descendre
-- en dessous ferait payer des réveils à répétition sans rien gagner.
--
-- STATEMENT_TIMEOUT_IN_SECONDS = 300 : une requête qui dépasse cinq
-- minutes sur cette base est une erreur, pas un travail long. Mieux vaut
-- qu'elle s'arrête que de la découvrir sur la facture du mois.
-- (INITIALLY_SUSPENDED n'existe qu'à la création d'un entrepôt : dans un
-- ALTER, Snowflake refuse le paramètre.)
ALTER WAREHOUSE WH_XS SET
    WAREHOUSE_SIZE = XSMALL
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    STATEMENT_TIMEOUT_IN_SECONDS = 300;

-- -----------------------------------------------------------------
-- 3. Le droit de lire la facturation
-- -----------------------------------------------------------------
-- MONITOR sur l'entrepôt ouvre WAREHOUSE_METERING_HISTORY au rôle : il
-- voit ce que l'entrepôt a consommé, jamais les données des autres
-- magasins. C'est ce qui alimente le panneau du Cockpit.
--
-- On ne le donne qu'au rôle de direction : un vendeur n'a pas à lire la
-- facture, et le panneau technique lui est de toute façon fermé.
GRANT MONITOR ON WAREHOUSE WH_XS TO ROLE COCKPIT_DIRECTION;

-- -----------------------------------------------------------------
-- 4. Vérifier, tout de suite
-- -----------------------------------------------------------------
-- Le moniteur existe, il est bien rattaché, et le quota est celui voulu.
SHOW RESOURCE MONITORS LIKE 'MONITEUR_COCKPIT';
SHOW WAREHOUSES LIKE 'WH_XS';

-- Ce que l'entrepôt a coûté ces trente derniers jours, par jour. C'est la
-- requête exacte que le Cockpit affiche dans son panneau technique.
SELECT TO_DATE(START_TIME) AS "jour",
       SUM(CREDITS_USED)   AS "credits"
FROM TABLE(MAISON_LAURET.INFORMATION_SCHEMA.WAREHOUSE_METERING_HISTORY(
         DATE_RANGE_START => DATEADD(day, -30, CURRENT_DATE()),
         WAREHOUSE_NAME   => 'WH_XS'))
GROUP BY 1
ORDER BY 1;

-- Et le total du mois en cours, en crédits puis en euros (prix indicatif,
-- à remplacer par celui du contrat).
SELECT ROUND(SUM(CREDITS_USED), 2)        AS "credits_du_mois",
       ROUND(SUM(CREDITS_USED) * 2.50, 2) AS "euros_estimes"
FROM TABLE(MAISON_LAURET.INFORMATION_SCHEMA.WAREHOUSE_METERING_HISTORY(
         DATE_RANGE_START => DATE_TRUNC('month', CURRENT_DATE()),
         WAREHOUSE_NAME   => 'WH_XS'));

-- -----------------------------------------------------------------
-- Pour retirer le plafond (par exemple avant une grosse reprise)
-- -----------------------------------------------------------------
-- ALTER WAREHOUSE WH_XS UNSET RESOURCE_MONITOR;
-- DROP RESOURCE MONITOR MONITEUR_COCKPIT;
