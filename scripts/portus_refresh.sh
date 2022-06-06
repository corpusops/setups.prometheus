#!/usr/bin/env bash
set -ex
cd $(dirname $(readlink -f $0))
dc="docker-compose"
dcr="$dc exec -T prometheusscripts"
$dc up -d
while true;do
    if ( $dcr test 0 = 0 );then break;fi
    echo "waiting dc up"
    sleep 1
done
$dcr python src/prometheus_update_replications.py
