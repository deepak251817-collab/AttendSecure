#!/bin/bash
# One-off helper: grant the app user access to attendance_test on the
# running compose MySQL container. (New volumes get this automatically
# via docker/mysql/init/01-test-database.sh.)
set -e
docker exec attendance-mysql mysql -uroot -p"${MYSQL_ROOT_PASSWORD:?export MYSQL_ROOT_PASSWORD}" <<'EOSQL'
CREATE DATABASE IF NOT EXISTS `attendance_test`
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON `attendance_test`.* TO 'attendance_user'@'%';
FLUSH PRIVILEGES;
EOSQL
echo "attendance_test granted to attendance_user."
