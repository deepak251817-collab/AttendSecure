#!/bin/bash
# Runs automatically on first initialization of the MySQL volume.
# Creates the dedicated pytest database and grants the application user
# full access to it, so `pytest` can reset it safely.
set -e

mysql -u root -p"$MYSQL_ROOT_PASSWORD" <<-EOSQL
    CREATE DATABASE IF NOT EXISTS `attendance_test`
        CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    GRANT ALL PRIVILEGES ON `attendance_test`.*
        TO '${MYSQL_USER:-attendance_user}'@'%';
    FLUSH PRIVILEGES;
EOSQL
