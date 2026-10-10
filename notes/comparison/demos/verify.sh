#!/bin/sh
# verify.sh <tool> <port> <path> [wait_s]: start the tool, wait until <path> answers, record status, stop it.
t=$1; p=$2; path=$3; w=${4:-90}
cd "$(dirname "$0")/$t"; ./start.sh > verify.log 2>&1 &
i=0; code=000
while [ $i -lt $w ]; do code=$(curl -s -o /tmp/verify_$t.body -w '%{http_code}' "http://127.0.0.1:$p$path"); [ "$code" = 200 ] && break; sleep 2; i=$((i+2)); done
echo "$t port $p $path -> HTTP $code after ${i}s; $(head -c 200 /tmp/verify_$t.body | tr '\n' ' ')"
./stop.sh; sleep 1; lsof -tiTCP:$p -sTCP:LISTEN >/dev/null && echo "WARNING still listening on $p"
