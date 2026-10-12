#!/bin/sh
# qa-mode.sh on|off|status — turn long-term memory OFF for both agents while running the QA evaluation.
#   on  : OpenClaw openviking autoRecall/autoCapture=false, Hermes memory provider/built-in memory off
#   off : restore (OpenClaw autoRecall=true, autoCapture=true; Hermes config.memory-on.yaml)
D="$(cd "$(dirname "$0")/.." && pwd)"
oc(){ docker exec openclaw-cli node dist/index.js "$@" 2>&1 | tail -1; }
case "$1" in
  on)  oc config set plugins.entries.openviking.config.autoRecall false --strict-json
       oc config set plugins.entries.openviking.config.autoCapture false --strict-json
       cp "$D/hermes-docker/config.memory-off.yaml" "$D/hermes-docker/profile/config.yaml" && echo "hermes: memory off";;
  off) oc config set plugins.entries.openviking.config.autoRecall true --strict-json
       oc config set plugins.entries.openviking.config.autoCapture true --strict-json
       cp "$D/hermes-docker/config.memory-on.yaml" "$D/hermes-docker/profile/config.yaml" && echo "hermes: memory on";;
  status) oc config get plugins.entries.openviking.config.autoRecall; oc config get plugins.entries.openviking.config.autoCapture
       grep -A4 '^memory:' "$D/hermes-docker/profile/config.yaml";;
  *) echo "usage: $0 on|off|status"; exit 1;;
esac
