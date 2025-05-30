#!/bin/sh
echo "[DataDog Agent Sim] Starting StatsD listener on UDP 8125..."
apk add --no-cache netcat-openbsd

while true; do 
  echo "[DataDog Agent Sim] $(date '+%Y-%m-%d %H:%M:%S'): Listening for StatsD metrics on UDP 8125"
  nc -u -l -p 8125 | while read line; do 
    if [ -n "$line" ]; then
      echo "[DataDog Agent Sim] $(date '+%Y-%m-%d %H:%M:%S'): METRIC RECEIVED: $line"
    fi
  done
  echo "[DataDog Agent Sim] $(date '+%Y-%m-%d %H:%M:%S'): Connection closed, restarting listener..."
  sleep 1
done