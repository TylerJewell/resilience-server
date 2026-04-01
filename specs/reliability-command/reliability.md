---
description: Attach a resilience testing dashboard to your Akka service — visualize clustering behavior, node failure/recovery, and HA/DR across regions.
handoffs:
  - label: Build & Run Locally
    agent: akka.build
    prompt: Build, test, and run the service locally
    send: true
  - label: Deploy to Platform
    agent: akka.deploy
    prompt: Deploy the service to the Akka platform
    send: true
  - label: Inspect Running Service
    agent: akka.inspect
    prompt: Inspect the running service's state and endpoints
    send: true
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). The user may specify which endpoints to use for read/write operations, or provide other preferences.

## Purpose

Attach a resilience testing dashboard and admin service to an existing Akka project. This enables developers to:

1. **Visualize local clustering** — launch agent teams, observe entity sharding across a 3-node local cluster, toggle nodes on/off, and watch automatic migration and recovery in real time.
2. **Visualize HA/DR** (Phase 2) — observe active-active replication across deployed regions, simulate region outages, and measure failover behavior.

The command generates:
- An **admin HTTP endpoint** in the user's project that serves the dashboard, manages local cluster topology, proxies read/write operations to the user's business endpoints, and discovers deployment regions.
- A **bundled resilience dashboard** (static HTML) served at `/admin/` that auto-detects available infrastructure and enables/disables features accordingly.
- A **reliability configuration file** (`.akka/reliability.yml`) that maps the user's endpoints to read/write test operations.

## Subcommands

This command supports two modes:

- `/akka:reliability` (or `/akka:reliability attach`) — attach the resilience testing dashboard to the project
- `/akka:reliability remove` — cleanly remove all reliability testing artifacts from the project

If `$ARGUMENTS` starts with `remove`, execute the **Remove** workflow (see below). Otherwise, execute the **Attach** workflow.

---

## Attach Workflow

### Step 0: Prerequisites

1. Verify the Akka MCP server is available by calling `akka_sdd_list_specs`. If unavailable, report:
   > The Akka MCP server is not running. Run `/akka:setup` to configure your environment.
   STOP.

2. Check for an existing Akka project:
   - Look for `pom.xml` with `akka-javasdk-parent` in the project root
   - Look for at least one Java source file under `src/main/java/` that extends an Akka component (`EventSourcedEntity`, `KeyValueEntity`, `Agent`, `Workflow`)
   - Look for at least one HTTP endpoint (class annotated with `@HttpEndpoint`)

3. If no Akka project exists, report:
   > ## Akka Reliability Testing
   >
   > This command attaches a resilience testing dashboard to an existing Akka service, letting you visualize how your entities, agents, and endpoints behave under node failures and region outages.
   >
   > **To get started:**
   > 1. `/akka:setup` — Set up your Akka development environment
   > 2. `/akka:specify` — Define your service's feature specification
   > 3. `/akka:plan` → `/akka:tasks` → `/akka:implement` — Build your service
   > 4. `/akka:reliability` — Come back here to attach resilience testing
   >
   > You need at least one entity and one HTTP endpoint before reliability testing can be attached.
   STOP.

4. If the project already has an `AdminEndpoint.java` in the api package, ask the user if they want to regenerate it (this would overwrite their existing admin endpoint).

### Step 0.5: User Consent

Before making any changes, present a clear explanation of what will be modified and obtain explicit consent:

```
## Reliability Testing — What Will Change

This command will temporarily add resilience testing instrumentation to your project.
The following files will be created:

  **New source files:**
  - `src/main/java/{package}/api/AdminEndpoint.java` — admin HTTP endpoint
  - `src/main/resources/static/admin/resilience.html` — testing dashboard

  **New config files:**
  - `.akka/reliability.yml` — endpoint mapping configuration
  - `.akka/reliability.manifest` — tracks all files added (used by `remove`)

⚠️  WARNING: The admin endpoint provides full cluster control and proxied
access to your business endpoints. It is intended for local development
and testing ONLY.

  - Do NOT include it in production builds or deployments
  - Do NOT commit it to branches destined for production
  - Run `/akka:reliability remove` to cleanly uninstall before packaging

The `/akka:deploy` command will check for the admin endpoint and warn
you if it is present. Enterprises can configure this as a hard failure.

Proceed with attaching reliability testing? (yes/no)
```

**STOP and wait for explicit user approval.** Do not proceed without a clear "yes" or equivalent.

### Step 1: Analyze the Project

Scan the project to build an inventory of components and endpoints. Read all Java source files to identify:

**Components:**
- Event Sourced Entities (class extends `EventSourcedEntity`)
- Key Value Entities (class extends `KeyValueEntity`)
- Agents (class extends `Agent`)
- Workflows (class extends `Workflow`)
- Views (class extends `View`)

**HTTP Endpoints:**
- For each class annotated with `@HttpEndpoint`, catalog every method with `@Get`, `@Post`, `@Put`, `@Delete`
- For each method, determine what component it calls via `componentClient` and what operation it performs
- Classify each method as:
  - **READ** — `@Get` methods, or methods that call entity `.get()` / `.invoke()` without state mutation, or view queries
  - **WRITE** — `@Post`/`@Put`/`@Delete` methods, or methods that call entity commands which persist events or update state
  - **AGENT** — methods that call `componentClient.forAgent()`

**Auto-select representative operations:**
- **Read operation**: Prefer a `@Get` endpoint that retrieves entity state. Pick the one with the simplest path (fewest path parameters). If multiple candidates, prefer one that returns a domain-meaningful response (not just `Done` or `HttpResponse`).
- **Write operation**: Prefer an agent invocation if one exists (most interesting under failure). Otherwise, pick a `@Post` or `@Put` that persists events or updates state. If multiple candidates, prefer one that exercises the most components.

Present the selection to the user:

```
## Project Analysis

### Components Found
- 1 Key Value Entity: GreetingEntity
- 1 HTTP Endpoint: GreetingEndpoint (2 methods)

### Selected Test Operations
- **Read**: `GET /hello/{id}` → GreetingEntity.get()
- **Write**: `PUT /hello/{id}` → GreetingEntity.setName()

These will be used by the resilience dashboard to generate test traffic.
Does this look right? (If you'd prefer different endpoints, tell me which ones.)
```

**STOP and wait for user approval.**

### Step 2: Generate the Reliability Configuration

Write `.akka/reliability.yml` with the selected mappings:

```yaml
# Akka Reliability Testing Configuration
# Generated by /akka:reliability

service:
  name: "{service-name from pom.xml artifactId}"
  package: "{base package from existing source}"

operations:
  read:
    method: GET
    path: "/hello/{id}"
    description: "Retrieve greeting by ID"
    component: GreetingEntity
    handler: get
    id-generator: uuid  # or: sequential, fixed:{value}
  write:
    method: PUT
    path: "/hello/{id}"
    description: "Set greeting name"
    component: GreetingEntity
    handler: setName
    id-generator: uuid
    body:
      template: '{"name": "Team-{teamId}-Agent-{agentId}"}'

admin:
  endpoint-path: "/admin"
  dashboard-path: "/admin/"
  port-offset: 100  # Admin on base port, nodes on base+1, base+2, base+3

cluster:
  node-count: 3
  base-port: 9000
```

Also write `.akka/reliability.manifest` — a plain text list of every file created by this command (one path per line, relative to project root). This manifest is used by `/akka:reliability remove` to cleanly uninstall and by `/akka:deploy` to detect the admin endpoint's presence. Example:

```
# Generated by /akka:reliability — do not edit
# Run '/akka:reliability remove' to uninstall
src/main/java/com/example/api/AdminEndpoint.java
src/main/resources/static/admin/resilience.html
.akka/reliability.yml
.akka/reliability.manifest
```

### Step 3: Generate the Admin Endpoint

Generate `src/main/java/{package}/api/AdminEndpoint.java` — an HTTP endpoint that:

**Dashboard serving:**
- `GET /admin/` — serves the bundled `resilience.html` from static resources
- The HTML file is placed at `src/main/resources/static/admin/resilience.html`

**Topology API:**
- `GET /admin/topology` — returns cluster/deployment topology as JSON:
  ```json
  {
    "mode": "local",
    "service": "greeting-service",
    "cluster": {
      "nodes": [
        {"id": 1, "port": 9000, "status": "RUNNING", "healthy": true},
        {"id": 2, "port": 9001, "status": "RUNNING", "healthy": true},
        {"id": 3, "port": 9002, "status": "STOPPED", "healthy": false}
      ]
    },
    "regions": [],
    "hadr_enabled": false,
    "hadr_message": "Deploy to multiple regions to enable HA/DR testing. Run /akka:deploy."
  }
  ```
  For local mode: use `akka_local_status` via MCP or direct health probes to determine node state.
  For deployed mode (Phase 2): use `akka_services_get` and `akka_projects_get` to discover regions.

**Cluster management API (local mode only):**
- `POST /admin/cluster/node/{n}/start` — start a cluster node (delegates to `akka_local_run_service`)
- `POST /admin/cluster/node/{n}/stop` — stop a cluster node (delegates to `akka_local_stop_service`)
- `POST /admin/cluster/start` — start all nodes (calls `akka_local_start` then runs service on each)
- `POST /admin/cluster/stop` — stop all nodes
- `GET /admin/cluster/status` — alias for topology

**Read/write proxy API:**

CRITICAL: The browser NEVER calls the user's business endpoints directly. All test traffic flows through the admin endpoint, which acts as an instrumented proxy. The admin endpoint invokes the user's service internally, measures server-side latency at the JVM level (not browser round-trip), counts response bytes, identifies which node handled the request, and returns an enriched response with all instrumentation data. This ensures consistent, accurate measurement regardless of browser network conditions.

- `POST /admin/test/read` — the admin endpoint internally invokes the configured read operation (e.g., `GET /hello/{id}`) via `ComponentClient`, measures wall-clock time around the invocation, captures the response body and byte count, and returns an instrumented result:
  ```json
  {
    "operation": "READ",
    "path": "/hello/abc-123",
    "status": 200,
    "latency_ms": 4,
    "response_bytes": 128,
    "node_port": 9000,
    "entity_id": "abc-123",
    "timestamp": "2026-04-01T16:30:00.000Z",
    "response": {"id": "abc-123", "message": "Hello, World!", "nodePort": 9000}
  }
  ```
  Accepts optional body `{"entity_id": "specific-id"}`. If omitted, generates a random UUID.

- `POST /admin/test/write` — the admin endpoint internally invokes the configured write operation (e.g., `PUT /hello/{id}` with a templated body), measures latency, counts bytes, and returns the same instrumented format:
  ```json
  {
    "operation": "WRITE",
    "path": "/hello/abc-123",
    "status": 200,
    "latency_ms": 12,
    "response_bytes": 42,
    "node_port": 9001,
    "entity_id": "abc-123",
    "timestamp": "2026-04-01T16:30:00.012Z",
    "response": {}
  }
  ```
  Accepts optional body `{"entity_id": "specific-id", "payload": {...}}`. If omitted, generates an ID and uses the body template from `.akka/reliability.yml`.

- `POST /admin/test/burst` — the admin endpoint spawns a server-side burst loop that executes multiple read/write operations at a configured interval. Each individual operation is proxied and instrumented as above. Returns a stream of results (or collects and returns batch). Accepts:
  ```json
  {
    "team_name": "Alpha",
    "agent_count": 3,
    "read_ratio": 0.4,
    "write_ratio": 0.6,
    "interval_ms": 400,
    "duration_seconds": 60
  }
  ```
  The burst runs server-side so that latency measurements reflect true service performance, not browser polling overhead. The dashboard polls `GET /admin/test/burst/{team_name}/results` to stream back the accumulated instrumented results.

- `GET /admin/test/burst/{team_name}/results` — returns the latest batch of instrumented results from a running burst, allowing the dashboard to poll and append to its transaction log. Returns:
  ```json
  {
    "team_name": "Alpha",
    "active": true,
    "results": [
      {"operation": "READ", "latency_ms": 4, "node_port": 9000, "entity_id": "...", "timestamp": "...", "response_bytes": 128},
      {"operation": "WRITE", "latency_ms": 12, "node_port": 9001, "entity_id": "...", "timestamp": "...", "response_bytes": 42}
    ]
  }
  ```

- `POST /admin/test/burst/{team_name}/stop` — stop a running burst for a team.

**Implementation notes for the admin endpoint:**
- Annotate with `@HttpEndpoint("/admin")`
- Annotate with `@Acl(allow = @Acl.Matcher(principal = Acl.Principal.ALL))`
- Inject `ComponentClient` for proxying to user's business endpoints — this is the mechanism for invoking the user's entity commands and agent methods. `ComponentClient` routes through the Akka cluster, so the request naturally hits whichever node owns the entity shard, giving us accurate `node_port` in the response.
- Inject `Config` for reading port/cluster configuration
- Use `AbstractHttpEndpoint` for access to request context
- Measure latency using `System.nanoTime()` around each `ComponentClient` invocation, convert to milliseconds
- Calculate `response_bytes` from the serialized response body size
- Determine `node_port` from the response metadata or from the entity's shard location
- For cluster management, delegate to MCP tools (`akka_local_run_service`, `akka_local_stop_service`) which handle process management
- Read `.akka/reliability.yml` at startup to know which endpoints to proxy and how to construct request bodies

### Step 4: Generate the Dashboard HTML

Place a customized version of `resilience.html` at `src/main/resources/static/admin/resilience.html`.

Modifications from the base resilience-ui:
1. **Replace all simulated data generation** with `fetch()` calls to the admin API:
   - Node/region status: poll `GET /admin/topology` every 2 seconds
   - Transaction log entries: driven by `POST /admin/test/read` and `POST /admin/test/write` responses
   - Team launch: calls `POST /admin/test/burst` with team config
   - Node toggle: calls `POST /admin/cluster/node/{n}/start` or `/stop`
2. **Auto-detect mode on load**: call `/admin/topology`, check `hadr_enabled`
   - If `false`: disable HA/DR tab, show message from `hadr_message`
   - If `true` (Phase 2): enable both tabs, populate region data
3. **Customize header/title** to include the service name from topology response
4. **Keep the same visual design** — dark theme, cyan/yellow accents, DNA helix animation, SVG border shapes

### Step 5: Compile and Verify

1. Run `akka_maven_compile` to verify the generated code compiles.
2. If compilation fails:
   - Read the errors
   - Fix import issues, type mismatches, or missing dependencies
   - Retry compilation (max 3 attempts)
3. Once compilation succeeds, report to the user.

### Step 6: Run and Test

1. Start the local environment: `akka_local_start`
2. Run the service: `akka_local_run_service`
3. Verify the admin endpoint responds:
   - `akka_local_request` to `GET /admin/topology` — should return local cluster info
   - `akka_local_request` to `GET /admin/` — should return HTML
4. Report the dashboard URL:

```
## Reliability Dashboard Ready

Dashboard: http://localhost:9000/admin/

### What you can do:
- **Launch agent teams** — generate read/write traffic against your service
- **Toggle nodes** — stop/start cluster nodes to observe failover behavior
- **Watch the transaction log** — see real latency and routing changes during failures

### Next steps:
- `/akka:deploy` — Deploy to the Akka platform to enable HA/DR testing
- `/akka:inspect` — Verify service state via backoffice tools
```

**STOP.**

## Phase 2: HA/DR (Future)

When Phase 2 is implemented, the following additions are needed:

1. **Topology endpoint enhancement**: When the service is deployed to multiple regions, `GET /admin/topology` returns region data:
   ```json
   {
     "mode": "deployed",
     "regions": [
       {"name": "us-east-1", "url": "https://svc-us-east.akka.app", "status": "available"},
       {"name": "eu-west-1", "url": "https://svc-eu-west.akka.app", "status": "available"}
     ],
     "hadr_enabled": true
   }
   ```
   Region discovery uses `akka_services_get` and `akka_routes_list` to find deployed instances.

2. **Dashboard HA/DR tab activation**: The resilience-ui enables the HA/DR tab and:
   - Calls each region's admin endpoint directly from the browser for latency measurement
   - Detects region outages by failed health checks (no server-side region management)
   - Visualizes replication by comparing write timestamps across regions
   - Calculates replication lag from cross-region read-after-write consistency checks

3. **Cross-region read/write**: The dashboard issues the same read/write proxy calls but targets specific region URLs, allowing it to measure per-region latency and observe failover when a region becomes unavailable.

## Error Handling

- If `akka_local_start` fails: check if Docker is running, if ports are in use, report clearly
- If compilation fails after 3 retries: present the errors and suggest `/akka:implement` to fix
- If the user has no entities: explain that at least one stateful component is needed for meaningful resilience testing
- If the user has only agents (no entities): the read operation can be an agent query and the write can be an agent invocation — adjust the mapping accordingly
- If port conflicts occur: suggest alternative ports or check `akka_local_status` for already-running services

## Key Rules

- **READ THE PROJECT FIRST** — never generate code without scanning all existing source files. The admin endpoint must integrate with the actual components in the project, not assumed ones.
- **PRESERVE EXISTING CODE** — the admin endpoint is additive. Never modify the user's existing entities, endpoints, or domain classes. Only add new files and static resources.
- **SINGLE ENTRY POINT** — the dashboard is served by the admin endpoint at `/admin/`. Users open one URL. No separate processes, no companion scripts.
- **MCP FOR CLUSTER MANAGEMENT** — use `akka_local_start`, `akka_local_run_service`, `akka_local_stop_service`, `akka_local_status` for all cluster operations. No `ProcessBuilder`, no shell scripts.
- **CONFIGURATION DRIVEN** — all endpoint mappings live in `.akka/reliability.yml`. The admin endpoint reads this at startup. Users can edit this file to change which operations are tested.
- **GRACEFUL DEGRADATION** — if deployed regions aren't available, the HA/DR tab is disabled with a helpful message, not hidden. If a node is down, the dashboard shows it clearly.
- **USER APPROVAL** — present the auto-detected endpoint mapping and wait for confirmation before generating code. The user knows their service better than static analysis can determine.
- **PHASE 1 FOCUS** — generate local clustering support. Include the HA/DR topology detection (so the tab shows the "not deployed" message), but do not implement region management or cross-region proxying yet.
- **MANIFEST EVERYTHING** — every file created must be listed in `.akka/reliability.manifest`. This is the contract that makes clean removal possible.
- **NOT FOR PRODUCTION** — the admin endpoint must never ship to production. The consent step, the remove command, and the deploy guard all reinforce this. Treat violations seriously.

---

## Remove Workflow

Executed when the user runs `/akka:reliability remove`.

### Step R1: Check for Manifest

1. Look for `.akka/reliability.manifest`.
2. If it does not exist, check for `AdminEndpoint.java` in the api package as a fallback indicator.
3. If neither exists, report:
   > No reliability testing artifacts found in this project. Nothing to remove.
   STOP.

### Step R2: Confirm Removal

Present the list of files that will be deleted:

```
## Remove Reliability Testing

The following files will be deleted:
  - src/main/java/com/example/api/AdminEndpoint.java
  - src/main/resources/static/admin/resilience.html
  - .akka/reliability.yml
  - .akka/reliability.manifest

Your existing service code will not be affected.

Proceed with removal? (yes/no)
```

**STOP and wait for explicit user approval.**

### Step R3: Delete Files

1. Read `.akka/reliability.manifest` line by line (skip comment lines starting with `#`).
2. For each file path listed:
   - Verify the file exists before deleting
   - Delete the file
   - If the file's parent directory is now empty (e.g., `src/main/resources/static/admin/`), remove the empty directory
3. Delete `.akka/reliability.manifest` itself (it's the last file removed).

### Step R4: Verify and Report

1. Run `akka_maven_compile` to confirm the project still compiles cleanly without the admin endpoint.
2. Report:

```
## Reliability Testing Removed

All testing artifacts have been removed. Your service is clean for production packaging.

Removed:
  - AdminEndpoint.java
  - resilience.html (dashboard)
  - reliability.yml (configuration)
  - reliability.manifest

Compilation: ✓ Passed
```

If compilation fails after removal (unlikely, but possible if the user's code referenced the admin endpoint), report the errors and suggest fixes.

---

## Deploy Guard — Changes to `/akka:deploy`

The `/akka:deploy` command MUST be updated to check for reliability testing artifacts before deploying. This protects users from accidentally shipping the admin endpoint to production.

### Detection

Before building the container image or pushing, `/akka:deploy` should:

1. Check for `.akka/reliability.manifest` — the authoritative indicator
2. As a fallback, scan for `AdminEndpoint.java` that contains the `@HttpEndpoint("/admin")` annotation

### Behavior

If reliability testing artifacts are detected:

**Default (warning):**
```
⚠️  WARNING: Reliability testing artifacts detected

The admin endpoint (AdminEndpoint.java) provides cluster control and
proxied access to your business endpoints. It should not be deployed
to production.

Files found:
  - src/main/java/com/example/api/AdminEndpoint.java
  - src/main/resources/static/admin/resilience.html
  - .akka/reliability.yml

Options:
  1. Run `/akka:reliability remove` to uninstall, then re-run `/akka:deploy`
  2. Continue anyway (not recommended for production)

Continue with deployment? (yes/no)
```

**Enterprise strict mode:**

If the project's `.akka/config.yml` (or equivalent project config) contains:

```yaml
reliability:
  deploy-guard: strict  # or: warn (default), skip
```

Then the presence of reliability artifacts is a **hard failure** — the deploy command refuses to proceed and does not offer a "continue anyway" option:

```
✖  BLOCKED: Reliability testing artifacts detected

Enterprise policy (deploy-guard: strict) prevents deployment while the
admin endpoint is present. This protects production environments from
unintended cluster control interfaces.

Run `/akka:reliability remove` to uninstall testing artifacts.
```

The three modes:
- `strict` — hard failure, blocks deployment, no override
- `warn` (default) — warning with option to continue
- `skip` — no check (for teams that intentionally deploy the admin endpoint to staging environments)
