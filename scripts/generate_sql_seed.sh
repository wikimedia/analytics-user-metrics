#!/bin/sh

# This assumes that you have run mwdumper and imported an XML-based dump file into a Mediawiki db
# the mysql commands assume a working .my.cnf file
# You can run mwdumper using the following command
# java -jar mwdumper-1.16.jar test2wiki-20130430-pages-meta-history.xml.bz2 --format=mysql:1.5 | mysql
 
mysql -e "DROP TABLE IF EXISTS revision2;"
mysql -e "DROP TABLE IF EXISTS page2;"
mysql -e "DROP TABLE IF EXISTS user2;"
mysql -e "DROP TABLE IF EXISTS logging2;"
mysql -e "CREATE TABLE revision2 AS (SELECT * FROM revision ORDER BY rev_id LIMIT 2500);"
mysql -e "CREATE TABLE page2 AS (SELECT page.* FROM page INNER JOIN revision2 ON page.page_id=revision2.rev_id);"
mysql -e "CREATE TABLE user2 LIKE user;"
mysql -e "INSERT INTO user2 (user_name, user_editcount, user_registration) SELECT DISTINCT rev_user_text, COUNT(rev_user_text), MIN(rev_timestamp) FROM revision2 GROUP BY rev_user_text;"
mysql -e "CREATE TABLE logging2 AS (SELECT logging.* FROM logging INNER JOIN user2 ON user2.user_id=log_user)";
mysqldump --replace --skip-add-drop-table wiki revision2 page2 user2 logging2 > seed.sql

#Rename the table names back to their original name
sed -i 's/revision2/revision/g' seed.sql
sed -i 's/page2/page/g' seed.sql
sed -i 's/user2/user/g' seed.sql
sed -i 's/logging2/logging/g' seed.sql
sed -i 's/CREATE TABLE/CREATE TABLE IF NOT EXISTS/g' seed.sql
