#!/bin/sh
# Stops whatever listens on this tool's port (only our own process binds it).
pid=$(lsof -tiTCP:8903 -sTCP:LISTEN); [ -n "$pid" ] && kill $pid && echo "stopped $pid" || echo "not running"
