#!/bin/bash
_AGENT_HOME="${AGENT_RUNTIME_HOME:-$HOME/Workspace/agent-runtime}"
exec "$_AGENT_HOME/scripts/cost_digest.sh" "$@"
