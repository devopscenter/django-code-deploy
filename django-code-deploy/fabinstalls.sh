#!/bin/bash
set -e

fab -R prod-web -P docker_web_install
fab -R prod-masterworker -P docker_worker_master_install
fab -R prod-standbyworker -P docker_worker_standby_install
fab -R prod-masterdb -P docker_masterdb_install
fab -R prod-standbydb -P docker_standbydb_install
