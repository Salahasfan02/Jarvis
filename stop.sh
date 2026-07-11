#!/bin/bash
# Turn Jarvis off:  ./stop.sh
# Stops the web UI and the backend by their ports. Ollama is left running
# (other apps may use it) unless you pass --all:  ./stop.sh --all

stop_port() {
  local port=$1 name=$2
  local pids
  pids=$(lsof -ti tcp:"$port")
  if [ -n "$pids" ]; then
    kill $pids 2>/dev/null
    echo "▸ $name stopped (port $port)"
  else
    echo "▸ $name was not running"
  fi
}

stop_port 5173 "Web UI"
stop_port 8765 "Backend"

if [ "$1" = "--all" ]; then
  stop_port 11434 "Ollama"
fi

echo "✅ Done. Start again with ./start.sh"
