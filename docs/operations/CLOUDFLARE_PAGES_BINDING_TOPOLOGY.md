# Cloudflare Pages Binding Topology — #1224-C

Status: **canonical deployment-evidence note / implementation HOLD**  
Checked: **2026-08-10**  
Scope: `cgbukku` Cloudflare Pages deployment and the server-side rate-limit/concurrency prerequisite from #1224-C.

Related contracts:

- [`exact-official-site-clone-invariant.md`](../product/exact-official-site-clone-invariant.md) — canonical site-fidelity invariant
- [`MVP_AI_RUNTIME_CONTRACT.md`](MVP_AI_RUNTIME_CONTRACT.md)
- [`PUBLIC_AI_API_SECURITY_AND_PRIVACY.md`](PUBLIC_AI_API_SECURITY_AND_PRIVACY.md)
- [`../cloudflare-pages-bukgu-mvp.md`](../cloudflare-pages-bukgu-mvp.md)

## 1. Decision

**Do not implement a production rate-limit/concurrency backend yet.**

The repository proves the application is deployed as a Cloudflare Pages project with Pages Functions, but it does **not** contain enough authoritative evidence to identify the bindings currently attached to the real production or preview project in the Cloudflare account.

Until the actual dashboard configuration is inspected or downloaded from Cloudflare, the following remain `UNKNOWN / HOLD`:

- existing production bindings;
- existing preview bindings;
- whether a service-bound limiter Worker already exists;
- whether a Durable Object Worker/namespace already exists;
- whether KV/D1/Analytics Engine resources are already bound;
- exact environment-specific binding variable names;
- compatibility date/build-system settings that would be captured by a downloaded Wrangler Pages config.

No rate-limit implementation may invent these values.

## 2. Repository evidence

At authoritative `main` `ea21a059a467e97693c444bbad9668aedebe7451`:

- repository search finds no `wrangler.toml`, `wrangler.json`, or `wrangler.jsonc` project configuration;
- repository search finds no declared `CF_PAGES` configuration;
- repository search finds no product use of a Durable Object namespace binding;
- repository search finds no product use of a KV binding for the public MVP request path;
- `package.json` contains Playwright only and does not define Wrangler/deployment configuration;
- `scripts/build_cloudflare_pages.py` builds `dist/cloudflare-pages` and copies the repository static tree into the Pages output;
- the existing deployment guide identifies project `cgbukku`, production branch `main`, framework preset `None`, build command `python3 scripts/build_cloudflare_pages.py`, and output directory `dist/cloudflare-pages`;
- that guide explicitly treats this project as dashboard-configured Pages + automatic Pages Functions deployment and says not to add a guessed Wrangler project configuration.

These facts establish the **repository-declared topology**, not the live Cloudflare-account binding set.

## 3. Current Cloudflare platform facts

Cloudflare documentation checked on 2026-08-10 establishes:

1. Pages Functions support only a documented subset of Cloudflare bindings.
2. The current Pages Functions binding documentation explicitly includes, among others:
   - KV namespaces;
   - Durable Objects;
   - Service bindings;
   - D1, R2, Analytics Engine, and other listed resources.
3. A Durable Object used by Pages must be created/deployed by a Worker and then bound to the Pages project; the Durable Object itself is not deployed inside the Pages project.
4. A Service binding can connect a Pages Function to a Worker without an Internet hop.
5. The Workers Rate Limiting API exists as a Worker binding and requires Wrangler configuration with a rate-limit namespace/configuration.
6. The current Pages Functions binding page does **not** list the Workers Rate Limiting binding among its supported Pages bindings.
7. Cloudflare recommends downloading an existing dashboard-configured Pages project with `wrangler pages download config` before adopting a Wrangler configuration file; a hand-written file must not be guessed from partial repository knowledge.
8. The Workers Rate Limiting API is intentionally permissive/eventually consistent and is not an authoritative accounting system. It is therefore unsuitable as the exact provider-spend ledger required by #1224-D even where it is usable for abuse control.

Official references:

- Cloudflare Pages — Functions / Bindings: `https://developers.cloudflare.com/pages/functions/bindings/`
- Cloudflare Pages — Functions / Configuration: `https://developers.cloudflare.com/pages/functions/wrangler-configuration/`
- Cloudflare Workers — Rate Limiting binding: `https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/`

## 4. Candidate designs — not yet selected

### Candidate A — direct Pages rate-limit binding

Status: **NOT SELECTED / currently unsupported by documented Pages binding list**.

Do not add `env.MVP_RATE_LIMITER.limit(...)` or a Wrangler `ratelimits` block to this Pages project on assumption alone.

A future platform/documentation change could alter this conclusion; re-verify before implementation.

### Candidate B — service-bound limiter Worker

Status: **SUPPORTED PLATFORM MECHANISM / NOT YET SELECTED**.

Pages Functions officially support Service bindings. A separately deployed Worker could own rate-limit and/or coordination primitives and expose only a narrow internal service contract to `/api/mvp/ask`.

Before selecting this design, verify whether the account already contains an appropriate Worker/service binding and capture its exact binding name and environment scope.

### Candidate C — Durable Object Worker bound to Pages

Status: **SUPPORTED PLATFORM MECHANISM / NOT YET SELECTED**.

Pages Functions officially support Durable Object bindings, with the Durable Object implemented in a separate Worker. This can provide strongly coordinated state useful for concurrency controls that cannot safely rely on per-isolate memory.

Before selecting this design, verify the actual account resources and whether a new Worker/DO namespace is operationally acceptable.

### Candidate D — per-isolate JavaScript counters

Status: **REJECTED**.

Per-isolate process memory is not a production security boundary and is explicitly prohibited by #1224-C.

## 5. Required topology evidence before runtime implementation

An operator with Cloudflare account access must capture the real `cgbukku` project configuration without exposing secrets.

Preferred evidence path:

1. Open the `cgbukku` Pages project in Cloudflare.
2. Record production and preview bindings by **type + variable name only**; do not copy secret values.
3. Record whether any bound Worker or Durable Object namespace already exists.
4. Record the production/preview environment scope of each binding.
5. Record build-system generation and compatibility settings relevant to Pages Functions.
6. If using Wrangler to inspect configuration, use Cloudflare's download command for the existing dashboard project rather than writing a config by hand:
   - `npx wrangler pages download config cgbukku`
7. Sanitize the downloaded output before committing any evidence. Resource IDs that are not needed for design review should be redacted from the review note.
8. Do **not** migrate the project from dashboard configuration to Wrangler-as-source-of-truth merely to collect evidence.

Minimum review packet:

```text
project: cgbukku
environment: production | preview
configuration_source: dashboard | downloaded-for-inspection
bindings:
  - type: <KV | Service | Durable Object | D1 | ...>
    variable_name: <name>
    target/resource: <sanitized description only>
compatibility_date: <value or UNKNOWN>
build_system: <value or UNKNOWN>
existing_limiter_worker: yes | no | UNKNOWN
existing_durable_object: yes | no | UNKNOWN
secret_values_captured: false
```

## 6. Privacy/keying requirements after topology is verified

Whichever durable/server-side mechanism is selected must preserve these #1224 constraints:

- do not use the full citizen question as a rate-limit key;
- use a server-side salted/pseudonymous derivation of the anonymous session identifier;
- a network signal such as Cloudflare client IP may be used only where justified as a bounded abuse signal, not as a durable identity;
- do not persist raw IP indefinitely;
- do not expose limiter keys or raw IP/session identifiers in public responses;
- keep session/request rate limiting distinct from global/provider concurrency;
- do not use abuse counters as exact billing/cost accounting;
- keep `snapshot_only` and kill-switch behavior compatible with #1227;
- introduce stable failure codes and retry semantics before deployment.

## 7. Proposed post-verification implementation decision

Do not choose a concrete backend until Section 5 evidence is available.

Decision procedure:

1. If the account already exposes a reviewed server-side limiter service/binding suitable for Pages, prefer reuse over a second control plane.
2. If a Service-bound Worker exists or is the approved deployment model, implement limiter/concurrency there with a narrow Pages binding contract.
3. If coordinated concurrency requires strongly consistent per-key state and a Durable Object Worker is approved, use a DO-backed design.
4. Do not adopt KV alone for strict concurrency locking without a reviewed consistency argument.
5. Do not create or migrate Wrangler configuration as a side effect of implementing #1224-C without an explicit deployment-configuration decision.

## 8. Current gate status

| Gate | State |
| --- | --- |
| Repository topology captured | PASS |
| Current official Pages binding capabilities reviewed | PASS |
| Actual production binding set verified | **HOLD / UNKNOWN** |
| Actual preview binding set verified | **HOLD / UNKNOWN** |
| Production limiter backend selected | **HOLD** |
| Concurrency backend selected | **HOLD** |
| Runtime rate-limit code authorized | **NO** |
| In-memory counter fallback allowed | **NO** |
| Live load testing authorized | **NO** |

The next #1224-C runtime change must begin only after the actual Cloudflare binding topology is supplied and reviewed.
