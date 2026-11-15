#!/usr/bin/env bash
# Kör samtliga moduler och bevara varje fel i slutstatus.
set -u
failed=0
count=0
for m in modules/*; do
    if [ -d "$m/tests" ]; then
        count=$((count + 1))
        printf '\n=== %s ===\n' "$m"
        if pytest -q "$m/tests"; then
            printf 'PASS: %s\n' "$m"
        else
            printf 'FAIL: %s\n' "$m"
            failed=1
        fi
    fi
done
if [ "$count" -eq 0 ]; then
    echo "FAIL: inga modultester hittades"
    exit 1
fi
exit "$failed"
