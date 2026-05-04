#!/bin/sh
# Test harness for autoclaw.sh
cd /storage/emulated/0/Download/picoclaw/workspace/autoclaw-project

# Start autoclaw in background
sh autoclaw.sh --budget 20 > /tmp/autoclaw_test.log 2>&1 &
PID=$!
sleep 1

# Send commands
echo "start" > /proc/$PID/fd/0 2>/dev/null || printf "start\n" >> /tmp/autoclaw_input
kill -PIPE $PID 2>/dev/null

sleep 15

echo "status" > /proc/$PID/fd/0 2>/dev/null || true
sleep 1
echo "quit" > /proc/$PID/fd/0 2>/dev/null || true
wait $PID 2>/dev/null
cat /tmp/autoclaw_test.log 2>/dev/null
