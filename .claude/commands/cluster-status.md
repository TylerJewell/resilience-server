Check the status of the Akka cluster.

1. Run `bash scripts/node.sh status`
2. For each running node, curl its hello endpoint to verify it's responsive: `curl -s http://localhost:{port}/hello/health-check`
3. Report which nodes are up, down, or unresponsive
