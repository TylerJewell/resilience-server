#!/usr/bin/env bash
#
# Manage a 3-node Akka cluster on ports 9000, 9001, 9002.
# Uses Postgres (Docker) for shared persistence and real Akka cluster sharding.
#
# Usage:
#   ./scripts/node.sh start <1|2|3>   Start a node (auto-starts Postgres if needed)
#   ./scripts/node.sh stop  <1|2|3>   Stop a node
#   ./scripts/node.sh stop-all        Stop all nodes and Postgres
#   ./scripts/node.sh status          Show which nodes are running
#   ./scripts/node.sh db-start        Start Postgres only
#   ./scripts/node.sh db-stop         Stop Postgres only
#
# Nodes form a real Akka cluster with entity sharding across nodes.
# PID files: scripts/.node-<n>.pid
# Logs: scripts/node-<n>.log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_DIR="$SCRIPT_DIR"
BASE_PORT=9000

node_port() {
  echo $(( BASE_PORT + $1 - 1 ))
}

pid_file() {
  echo "$PID_DIR/.node-${1}.pid"
}

log_file() {
  echo "$PID_DIR/node-${1}.log"
}

is_running() {
  local pf
  pf="$(pid_file "$1")"
  if [[ -f "$pf" ]]; then
    local pid
    pid=$(cat "$pf")
    if kill -0 "$pid" 2>/dev/null; then
      return 0
    else
      rm -f "$pf"
    fi
  fi
  return 1
}

ensure_postgres() {
  local state
  state=$(docker inspect -f '{{.State.Running}}' akka-postgres 2>/dev/null || echo "false")
  if [[ "$state" == "true" ]]; then
    return 0
  fi

  echo "Starting Postgres..."
  docker rm -f akka-postgres 2>/dev/null || true
  docker run -d --name akka-postgres \
    -p 5432:5432 \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_PASSWORD=postgres \
    postgres:15 > /dev/null

  # Wait for Postgres to be ready
  for i in $(seq 1 30); do
    if docker exec akka-postgres pg_isready -q -U postgres 2>/dev/null; then
      echo "Postgres ready"
      return 0
    fi
    sleep 1
  done
  echo "WARNING: Postgres may not be ready"
}

start_node() {
  local n="$1"
  local port
  port=$(node_port "$n")

  if is_running "$n"; then
    echo "Node $n is already running on port $port (PID $(cat "$(pid_file "$n")"))"
    return 0
  fi

  ensure_postgres

  # Compile if needed
  if [[ ! -d "$PROJECT_DIR/target/classes" ]]; then
    echo "Compiling project..."
    (cd "$PROJECT_DIR" && mvn -q compile)
  fi

  # Clean stale registry entry
  rm -f "$HOME/.akka/local/resilience-${n}.conf" 2>/dev/null

  echo "Starting node $n on port $port..."

  local lf
  lf="$(log_file "$n")"

  (cd "$PROJECT_DIR" && mvn -q exec:java \
    -Dconfig.resource=local-node${n}.conf \
    -Dakka.javasdk.dev-mode.http-port=${BASE_PORT} \
    -Dakka.javasdk.dev-mode.service-name="resilience-${n}" \
    -Dakka.persistence.r2dbc.connection-factory.database=postgres \
    > "$lf" 2>&1) &

  local pid=$!
  echo "$pid" > "$(pid_file "$n")"
  echo "Node $n started (PID $pid, port $port, log: $lf)"
}

stop_node() {
  local n="$1"
  local pf
  pf="$(pid_file "$n")"

  if ! is_running "$n"; then
    echo "Node $n is not running"
    return 0
  fi

  local pid
  pid=$(cat "$pf")
  local port
  port=$(node_port "$n")
  echo "Stopping node $n (port $port)..."

  # Kill the mvn parent process
  if command -v taskkill &>/dev/null; then
    taskkill //F //T //PID "$pid" 2>/dev/null || true
    # Also kill any Java process listening on this node's port
    local java_pid
    java_pid=$(netstat -ano 2>/dev/null | grep "LISTEN" | grep ":${port} " | awk '{print $NF}' | head -1)
    if [[ -n "$java_pid" && "$java_pid" != "$pid" ]]; then
      taskkill //F //PID "$java_pid" 2>/dev/null || true
    fi
  else
    kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
  fi

  rm -f "$pf"
  rm -f "$HOME/.akka/local/resilience-${n}.conf" 2>/dev/null
  echo "Node $n stopped"
}

stop_all() {
  for n in 1 2 3; do
    if is_running "$n"; then
      stop_node "$n"
    fi
  done
  echo "Stopping Postgres..."
  docker rm -f akka-postgres 2>/dev/null || true
  echo "All nodes and Postgres stopped"
}

db_start() {
  ensure_postgres
}

db_stop() {
  echo "Stopping Postgres..."
  docker rm -f akka-postgres 2>/dev/null || true
  echo "Postgres stopped"
}

status() {
  # Postgres status
  local db_state
  db_state=$(docker inspect -f '{{.State.Running}}' akka-postgres 2>/dev/null || echo "false")
  if [[ "$db_state" == "true" ]]; then
    echo "Postgres: RUNNING"
  else
    echo "Postgres: STOPPED"
  fi
  echo ""
  echo "Node  Port   Status"
  echo "----  -----  ------"
  for n in 1 2 3; do
    local port
    port=$(node_port "$n")
    if is_running "$n"; then
      local pid
      pid=$(cat "$(pid_file "$n")")
      echo "  $n    $port   RUNNING (PID $pid)"
    else
      echo "  $n    $port   STOPPED"
    fi
  done
}

# --- Main ---

cmd="${1:-}"
arg="${2:-}"

case "$cmd" in
  start)
    if [[ -z "$arg" || "$arg" -lt 1 || "$arg" -gt 3 ]]; then
      echo "Usage: $0 start <1|2|3>"
      exit 1
    fi
    start_node "$arg"
    ;;
  stop)
    if [[ -z "$arg" || "$arg" -lt 1 || "$arg" -gt 3 ]]; then
      echo "Usage: $0 stop <1|2|3>"
      exit 1
    fi
    stop_node "$arg"
    ;;
  stop-all)
    stop_all
    ;;
  status)
    status
    ;;
  db-start)
    db_start
    ;;
  db-stop)
    db_stop
    ;;
  *)
    echo "Usage: $0 {start|stop|stop-all|status|db-start|db-stop} [node-number]"
    exit 1
    ;;
esac
