#!/usr/bin/env bash
# Thin entry point — the real runner is Python (see run_scenarios.py) since
# it needs to parse JSON, run subprocesses, and grade filesystem state.
set -eu
exec python3 "$(dirname "$0")/run_scenarios.py" "$@"
