#!/usr/bin/env bash
# Watchdog for deepseek-v4-flash.service (DeepSeek-V4-Flash-0731 on vLLM+DSpark, TP=2).
#
# Why this exists: the serving unit is Type=oneshot/RemainAfterExit and the containers run
# with restart policy "no", so systemd owns ordering but nothing notices a mid-run death.
# On 2026-09-19 rank 0's NCCL watchdog caught a 600s _ALLGATHER_BASE timeout and took the
# process down; the unit stayed "active (exited)" and the API was gone for hours.
#
# One tick (driven by deepseek-v4-flash-watchdog.timer, every 60s):
#   - liveness: GET /v1/models, 10s timeout
#   - depth:    every DEEP_INTERVAL, POST /v1/completions max_tokens=8 with a hard deadline,
#               which catches a wedged NCCL group that still answers HTTP but emits no tokens
#   - FAIL_THRESHOLD consecutive failures -> cold restart via `systemctl --user restart`
#     (that runs the unit's ExecStop -> stop-deepseek-v4-flash-dspark.sh, clearing the stale
#     rank on node 2, then ExecStart -> serve-dspark-ds4.sh with the drop_caches sidecar)
#
# Deliberate non-goals:
#   - If the unit is `inactive`, an operator stopped it on purpose. The watchdog stands down
#     and will NOT resurrect it. `systemctl --user start deepseek-v4-flash` re-arms it.
#   - After MAX_RESTARTS inside RESTART_WINDOW it gives up and only reports, so a genuinely
#     broken cluster is not restart-looped for days.
#
# State: ~/deepseek-v4-flash-watchdog-state.json   Logs: journalctl --user -u deepseek-v4-flash-watchdog
set -uo pipefail

API="${API:-http://127.0.0.1:8888}"
MODEL="${MODEL:-deepseek-v4-flash-0731}"
UNIT="${UNIT:-deepseek-v4-flash.service}"
STATE="${STATE:-$HOME/deepseek-v4-flash-watchdog-state.json}"
LOCK="${LOCK:-$HOME/.deepseek-v4-flash-watchdog.lock}"

LIVENESS_TIMEOUT="${LIVENESS_TIMEOUT:-10}"   # GET /v1/models budget
DEEP_INTERVAL="${DEEP_INTERVAL:-600}"        # how often the generation probe runs
DEEP_DEADLINE="${DEEP_DEADLINE:-90}"         # generation probe budget (cold KV cache is slow)
FAIL_THRESHOLD="${FAIL_THRESHOLD:-3}"        # consecutive bad ticks before acting
RESTART_DEADLINE="${RESTART_DEADLINE:-5400}" # matches the unit's TimeoutStartSec=90min
MAX_RESTARTS="${MAX_RESTARTS:-3}"            # inside RESTART_WINDOW, then give up
RESTART_WINDOW="${RESTART_WINDOW:-10800}"    # 3h
HEALTHY_RESET="${HEALTHY_RESET:-3600}"       # 1h healthy clears the restart history

now() { date +%s; }
log() { printf '%s %s\n' "$(date -Is)" "$*"; }

# --- state -------------------------------------------------------------------
state_get() { jq -r --arg k "$1" --arg d "$2" '.[$k] // $d' "$STATE" 2>/dev/null || printf '%s' "$2"; }

state_put() { # state_put key value [key value ...]  (values land as JSON where valid, else string)
  local tmp; tmp="$(mktemp "${STATE}.XXXXXX")"
  local -a args=(); local filter='.'
  local i=1
  while [ "$#" -ge 2 ]; do
    args+=(--arg "k$i" "$1" --arg "v$i" "$2")
    filter="$filter | .[\$k$i] = ((\$v$i | try fromjson catch \$v$i))"
    i=$((i + 1)); shift 2
  done
  jq "${args[@]}" "$filter" "$STATE" > "$tmp" 2>/dev/null && mv -f "$tmp" "$STATE" || rm -f "$tmp"
}

[ -s "$STATE" ] || echo '{"phase":"ok","consecutive_failures":0,"restart_history":[]}' > "$STATE"
jq -e . "$STATE" >/dev/null 2>&1 || echo '{"phase":"ok","consecutive_failures":0,"restart_history":[]}' > "$STATE"

# --- probes ------------------------------------------------------------------
# Sets PROBE_REASON on failure. Returns 0 only when the server is genuinely serving.
probe_liveness() {
  local body
  if ! body="$(curl -sS -m "$LIVENESS_TIMEOUT" "$API/v1/models" 2>&1)"; then
    PROBE_REASON="liveness: GET /v1/models failed within ${LIVENESS_TIMEOUT}s (${body//$'\n'/ })"
    return 1
  fi
  if ! jq -e --arg m "$MODEL" '.data[]? | select(.id == $m)' <<<"$body" >/dev/null 2>&1; then
    PROBE_REASON="liveness: /v1/models answered but does not list $MODEL"
    return 1
  fi
  return 0
}

probe_generation() {
  local body text
  if ! body="$(curl -sS -m "$DEEP_DEADLINE" -X POST "$API/v1/completions" \
        -H 'Content-Type: application/json' \
        -d "$(jq -nc --arg m "$MODEL" '{model:$m, prompt:"ping", max_tokens:8, temperature:0, stream:false}')" 2>&1)"; then
    PROBE_REASON="generation: no completion within ${DEEP_DEADLINE}s (${body//$'\n'/ }) - NCCL group likely wedged"
    return 1
  fi
  text="$(jq -r '.choices[0].text // empty' <<<"$body" 2>/dev/null)"
  if [ -z "$text" ]; then
    PROBE_REASON="generation: empty/!ok response (${body:0:200})"
    return 1
  fi
  return 0
}

# --- restart bookkeeping -----------------------------------------------------
recent_restarts() {
  jq --argjson cutoff "$(( $(now) - RESTART_WINDOW ))" \
     '[(.restart_history // [])[] | select(. > $cutoff)] | length' "$STATE" 2>/dev/null || echo 0
}

record_restart() {
  local tmp; tmp="$(mktemp "${STATE}.XXXXXX")"
  jq --argjson t "$(now)" --argjson cutoff "$(( $(now) - RESTART_WINDOW ))" \
     '.restart_history = ([((.restart_history // [])[] | select(. > $cutoff)), $t])' "$STATE" > "$tmp" \
     && mv -f "$tmp" "$STATE" || rm -f "$tmp"
}

# --- main tick ---------------------------------------------------------------
exec 9>"$LOCK"
flock -n 9 || { log "SKIP previous tick still running"; exit 0; }

T="$(now)"
PHASE="$(state_get phase ok)"
FAILS="$(state_get consecutive_failures 0)"
UNIT_STATE="$(systemctl --user is-active "$UNIT" 2>/dev/null || true)"
PROBE_REASON=""

mark_healthy() {
  local prev="$1"
  # healthy_since is the start of the CURRENT unbroken healthy stretch, reset on every
  # transition back into ok. Deriving it from last_ok instead would make a service that
  # flaps (healthy for one tick, dead again) look like a long healthy stretch and wipe the
  # crash-loop budget on every bounce.
  local healthy_since="$(state_get healthy_since 0)"
  if [ "$prev" != "ok" ] || [ "$healthy_since" = "0" ]; then
    healthy_since="$T"
    state_put healthy_since "$T"
  fi
  state_put phase ok consecutive_failures 0 last_ok "$T" last_check "$T" last_failure_reason ""
  if [ "$prev" != "ok" ]; then
    log "RECOVERED $UNIT is serving again (was phase=$prev)"
  fi
  # A long unbroken healthy stretch means whatever caused the last restarts is behind us.
  local uptime="$(( T - healthy_since ))"
  if [ "$(recent_restarts)" != "0" ] && [ "$uptime" -ge "$HEALTHY_RESET" ]; then
    state_put restart_history '[]'
    log "restart history cleared after ${uptime}s healthy"
  fi
}

# 1. An operator-stopped unit is intent, not an outage.
if [ "$UNIT_STATE" = "inactive" ]; then
  [ "$PHASE" = "standby" ] || log "STANDBY $UNIT is inactive (stopped by an operator); not restarting. \`systemctl --user start ${UNIT%.service}\` re-arms the watchdog."
  state_put phase standby consecutive_failures 0 last_check "$T"
  exit 0
fi

# 2. A restart we launched is still in flight (weight load can take many minutes).
if [ "$PHASE" = "restarting" ]; then
  START="$(state_get restart_started "$T")"
  ELAPSED="$(( T - START ))"
  if probe_liveness; then
    mark_healthy restarting
    exit 0
  fi
  if [ "$UNIT_STATE" = "activating" ] && [ "$ELAPSED" -lt "$RESTART_DEADLINE" ]; then
    log "restart in progress (${ELAPSED}s, unit=$UNIT_STATE)"
    state_put last_check "$T"
    exit 0
  fi
  if [ "$ELAPSED" -lt "$RESTART_DEADLINE" ]; then
    log "restart settling (${ELAPSED}s, unit=$UNIT_STATE): $PROBE_REASON"
    state_put last_check "$T"
    exit 0
  fi
  log "RESTART FAILED after ${ELAPSED}s (unit=$UNIT_STATE): $PROBE_REASON"
  state_put phase degraded consecutive_failures "$FAIL_THRESHOLD" last_check "$T" last_failure_reason "$PROBE_REASON"
  PHASE=degraded
  FAILS="$FAIL_THRESHOLD"
fi

# 3. Probe. Liveness every tick; generation on its own slower cadence.
HEALTHY=1
probe_liveness || HEALTHY=0
DEEP_LAST="$(state_get last_deep_probe 0)"
if [ "$HEALTHY" = "1" ] && [ "$(( T - DEEP_LAST ))" -ge "$DEEP_INTERVAL" ]; then
  if probe_generation; then
    state_put last_deep_probe "$T"
  else
    state_put last_deep_probe "$T"
    HEALTHY=0
  fi
fi

if [ "$HEALTHY" = "1" ]; then
  mark_healthy "$PHASE"
  exit 0
fi

# 4. Unhealthy.
FAILS="$(( FAILS + 1 ))"
log "UNHEALTHY ($FAILS/$FAIL_THRESHOLD, unit=$UNIT_STATE): $PROBE_REASON"
state_put consecutive_failures "$FAILS" last_check "$T" last_failure_reason "$PROBE_REASON" healthy_since 0

if [ "$FAILS" -lt "$FAIL_THRESHOLD" ]; then
  state_put phase degraded
  exit 0
fi

if [ "$PHASE" = "givenup" ]; then
  log "STILL DOWN and past the restart budget; not restarting. Fix, then \`systemctl --user restart ${UNIT%.service}\`."
  exit 0
fi

if [ "$(recent_restarts)" -ge "$MAX_RESTARTS" ]; then
  log "GIVING UP: $(recent_restarts) restarts in the last $(( RESTART_WINDOW / 60 ))min did not hold. No further restarts."
  log "  last failure: $PROBE_REASON"
  log "  inspect: docker logs --tail 100 deepseek-v4-flash-vllm-dspark-1 ; ssh 192.168.100.11 docker logs --tail 100 deepseek-v4-flash-vllm-dspark-1"
  state_put phase givenup
  exit 0
fi

log "RESTARTING $UNIT (cold: ExecStop stops both ranks, ExecStart re-runs serve-dspark-ds4.sh)"
record_restart
state_put phase restarting restart_started "$T"
if systemctl --user restart --no-block "$UNIT"; then
  log "restart dispatched; next ticks will watch for the API to come back (deadline $(( RESTART_DEADLINE / 60 ))min)"
else
  log "ERROR could not dispatch restart of $UNIT"
  state_put phase degraded
fi
