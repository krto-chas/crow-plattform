#!/usr/bin/env sh
set -eu
PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src" python -m crow_workbench
