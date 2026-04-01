Start the 3-node Akka cluster with shared Postgres persistence.

1. Ensure Docker is running and start the `akka-postgres` container if not already up
2. Start all 3 nodes using `bash scripts/node.sh start 1`, `start 2`, `start 3`
3. Poll ports 9000, 9001, 9002 every 10 seconds until all respond with HTTP 200
4. Run `bash scripts/node.sh status` and report the result
