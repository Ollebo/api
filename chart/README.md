# ollebo-api Helm chart

Deploys the `ollebo-api` Flask service (image `ollebo/api`). This file is the
contract for what the service needs to run correctly in a Kubernetes cluster
— another reviewer (human or AI) should be able to validate a running
deployment from this checklist alone.

## What this service is

A Python/Flask HTTP API for `ollebo.com` that manages drone-style "maps"
(orthophotos/geotiffs), "missions", and time-series "events". The app is
served by `gunicorn` on port `8080` inside the container.

Source: `code/start.py`. Entry script: `code/start.sh`
(`gunicorn -w 1 --threads 16 -k gthread -b 0.0.0.0:8080 --timeout 0 --graceful-timeout 30 start:app`).

## Architecture in this chart

Each install renders these resources (all named `api` in the install namespace):

| Kind                    | Purpose                                                              |
| ----------------------- | -------------------------------------------------------------------- |
| Deployment              | The Flask app, 2+ replicas, gunicorn on port 8080                    |
| Service (ClusterIP)     | Stable in-cluster DNS for the app, port 8080                         |
| Ingress                 | Public entry on `api.ollebo.com`, TLS via cert-manager               |
| HorizontalPodAutoscaler | Scales 2→10 replicas at 70% CPU utilization                          |
| PodDisruptionBudget     | `minAvailable: 1` so node drains never take the API fully down       |

## External dependencies (must exist before install)

The chart **does not** create these — they are expected to already be in the
cluster. An AI validator should confirm each one exists.

### Cluster-level prerequisites

| Dependency                    | Why                                                                                  |
| ----------------------------- | ------------------------------------------------------------------------------------ |
| Traefik ingress controller    | The Ingress uses `ingressClassName: traefik`                                         |
| cert-manager + ClusterIssuer  | The Ingress uses annotation `cert-manager.io/cluster-issuer: http` (HTTP-01 issuer) |
| metrics-server                | The HPA reads CPU utilization from the metrics API                                   |
| Prometheus (kube-prometheus or similar) | The pod is annotated `prometheus.io/scrape=true` — scrape config must use the standard pod role discovery |

### Namespaced prerequisites (same namespace as install)

| Resource                  | Kind   | Used for                                                          |
| ------------------------- | ------ | ----------------------------------------------------------------- |
| Secret `ollebo-app`       | Secret | Provides key `password` → env `POSTGRES_PASSWORD`                 |
| Service `ollebo-rw`       | Service | Primary Postgres/PostGIS endpoint (host for env `POSTGRES_HOST`) |
| Service `nats` (port 4222) | Service | NATS JetStream endpoint (env `NATS=nats://nats:4222`)            |

### Backing data stores

| Store              | Required? | Used by                                                                 |
| ------------------ | --------- | ----------------------------------------------------------------------- |
| PostgreSQL + PostGIS | **Yes**  | Primary store for `maps`, `missions`, `mission_data` tables. The Flask app opens a single long-lived connection at import time and `sys.exit()`s if it can't connect — so a failed Postgres dependency means the pod will CrashLoopBackoff |
| NATS JetStream     | No, but degraded without | Event bus for the SSE `/event/<id>/stream` endpoint. Connection is async with infinite retry in a background thread — the rest of the API works without it |

## Environment variables set by the chart

| Env                  | Source                                          |
| -------------------- | ----------------------------------------------- |
| `POSTGRES_PASSWORD`  | `secretKeyRef: ollebo-app/password`             |
| `POSTGRES_HOST`      | hardcoded `ollebo-rw`                           |
| `POSTGRES_DB`        | hardcoded `ollebo`                              |
| `POSTGRES_USER`      | hardcoded `ollebo`                              |
| `NATS`               | hardcoded `nats://nats:4222`                    |
| `PROJECT`            | hardcoded `ollebo`                              |

## Configurable values (`values.yaml`)

| Key                          | Default                | Purpose                                  |
| ---------------------------- | ---------------------- | ---------------------------------------- |
| `replicaCount`               | `2`                    | Starting replicas (HPA may scale higher) |
| `image.repository`           | `ollebo/api`           | Image name                               |
| `image.tag`                  | `latest`               | Image tag (CI overrides with git SHA)    |
| `image.pullPolicy`           | `Always`               |                                          |
| `resources.requests.cpu`     | `100m`                 | Required for HPA CPU calc                |
| `resources.requests.memory`  | `128Mi`                |                                          |
| `resources.limits.cpu`       | `500m`                 |                                          |
| `resources.limits.memory`    | `512Mi`                |                                          |
| `ingress.className`          | `traefik`              |                                          |
| `ingress.host`               | `api.ollebo.com`       | Public hostname                          |
| `ingress.clusterIssuer`      | `http`                 | cert-manager ClusterIssuer name (HTTP-01) |
| `hpa.minReplicas`            | `2`                    |                                          |
| `hpa.maxReplicas`            | `10`                   |                                          |
| `hpa.targetCPU`              | `70`                   | Average utilization % to scale at        |

## Network surface

| Surface         | Where                                          | Notes                          |
| --------------- | ---------------------------------------------- | ------------------------------ |
| Container port  | `8080`                                         | named `http`                   |
| Service port    | `8080` → targetPort `8080`                     | ClusterIP `api`                |
| Ingress         | `https://api.ollebo.com/` → `api:8080`         | TLS secret `api-tls` (issued by cert-manager) |

## Endpoints exposed by the app

| Path                                | Purpose                                               | Used by                  |
| ----------------------------------- | ----------------------------------------------------- | ------------------------ |
| `/healthz`                          | Liveness — 200 if process responds                    | `livenessProbe`          |
| `/readyz`                           | Readiness — 200 if Postgres `SELECT 1` succeeds, else 503 | `readinessProbe`     |
| `/metrics`                          | Prometheus text format (`prometheus_flask_exporter`)  | Prometheus scrape        |
| `/doc` + `/doc/openapi.json`        | Swagger UI + OpenAPI spec                             | humans                   |
| `/maps/`, `/search/`, `/missions/`, `/mission/<id>`, `/event/<mission_id>`, `/event/<mission_id>/recent`, `/event/<mission_id>/stream` | Business endpoints | clients          |

## Probe configuration (in the Deployment)

| Probe       | Path       | initialDelay | period | timeout | failureThreshold |
| ----------- | ---------- | ------------ | ------ | ------- | ---------------- |
| liveness    | `/healthz` | 10s          | 10s    | 2s      | 3                |
| readiness   | `/readyz`  | 5s           | 5s     | 2s      | 3                |

`terminationGracePeriodSeconds: 35` (gunicorn `--graceful-timeout 30` + buffer).

## Validation checklist for an AI/human reviewer

Run after `helm install` (or after the GitOps controller has reconciled):

```bash
NS=<namespace>

# 1. All five resources exist
kubectl -n $NS get deployment,svc,ingress,hpa,pdb -l app=ollebo-api -o wide

# 2. Pods are Ready (expect >= 2)
kubectl -n $NS get pods -l app=ollebo-api -o wide
kubectl -n $NS describe pod -l app=ollebo-api | grep -A3 -E 'Liveness|Readiness'

# 3. Probes are firing successfully (no recent Unhealthy events)
kubectl -n $NS get events --field-selector reason=Unhealthy

# 4. HPA has current metrics (TARGETS column shows %/70%, not <unknown>)
kubectl -n $NS get hpa api

# 5. Ingress has an address and the TLS secret was issued
kubectl -n $NS get ingress api
kubectl -n $NS get secret api-tls -o jsonpath='{.metadata.annotations.cert-manager\.io/certificate-name}{"\n"}'

# 6. Required dependencies are reachable
kubectl -n $NS get secret ollebo-app
kubectl -n $NS get svc ollebo-rw nats

# 7. External reachability + endpoints
curl -fsS https://api.ollebo.com/healthz                # expect "ok"
curl -fsS https://api.ollebo.com/readyz                 # expect "ok"
curl -fsS https://api.ollebo.com/metrics | head -5      # expect Prometheus text

# 8. Prometheus is scraping the pod
#    In Prometheus, expect `up{app="ollebo-api"} == 1` for each pod.
```

A green run of steps 1–8 means the service has everything it needs.

## Known production caveats

- Postgres connection is a single long-lived connection opened at import time
  in `code/db/postgis.py` — if Postgres is unreachable at startup, the pod
  crashes and gets restarted. `/readyz` will fail (and drain traffic) if the
  connection later dies; it does **not** reconnect automatically. Restart the
  pod to recover.
- gunicorn is configured with `--timeout 0` — long-running requests will
  never be killed by gunicorn. Edge timeouts apply at the Ingress only.
- The chart assumes the `Ollebo/manifests` GitOps repo is what actually
  applies these resources to the cluster (CI in this repo templates the chart
  and pushes the rendered manifests there).
