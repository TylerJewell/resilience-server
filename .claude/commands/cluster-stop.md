Stop the 3-node Akka cluster and clean up.

1. Run `bash scripts/node.sh stop-all` to stop all nodes and Postgres
2. Kill any remaining java.exe processes: `taskkill //F //IM java.exe 2>/dev/null`
3. Clean stale registry files: `rm -f ~/.akka/local/resilience*.conf`
4. Run `bash scripts/node.sh status` to confirm everything is stopped
