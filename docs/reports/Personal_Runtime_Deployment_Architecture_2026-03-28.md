# Personal Runtime Deployment Architecture (2026-03-28)

Status: Active deployment note
Date: 2026-03-28
Owner: Lattice runtime maintainers
Purpose: define a repo-grounded deployment shape that matches Lattice's current local-first, single-operator-first product direction without drifting into an accidental multi-tenant workspace platform.

Canonical parents:
- `README.md`
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/reports/Installability_Audit_2026-03-27.md`
- `docs/reports/Alpha_Share_QA_Audit_2026-03-27.md`

## 1. Executive verdict

The recommended deployment shape for the current product is:

1. `personal runtime per user` as the product unit
2. local install first
3. managed single-tenant hosting second
4. shared multi-user app server not recommended for the current product stage

This follows the current product truth:
- Lattice is `local-first`
- the first-product story is `paper-first`
- the runtime is `single-operator-first`
- the product is not currently a first-class project/workspace platform

So distribution should preserve operator-local ownership and per-user runtime isolation rather than centralize all users into one shared stateful service.

## 2. Why this matters

The current runtime is not just a stateless chat surface.
It persists operator-specific state across:

- config
- local DB
- storage roots and derived artifacts
- logs and cache
- external filesystem adapters such as Obsidian and Zotero
- API keys, model/provider settings, and local-vs-cloud execution choices

That means "personalization" is not a thin presentation layer.
It is part of the runtime boundary itself.

If many users share one backend, one DB, and one artifact root, the product starts drifting toward:

- multi-tenant account modeling
- workspace/project ownership rules
- per-user authorization and tenancy isolation
- shared-vs-private artifact semantics
- cross-user provenance and audit policy
- support and recovery complexity far beyond the current product claim

That is a different product shape from the current repo direction.

## 3. Decision rule

Use this rule for deployment decisions:

- If the runtime state should feel like "my papers, my artifacts, my notes, my models, my vault, my review history," deploy one runtime per operator.
- If the runtime state should be pooled, concurrently shared, permissioned, and collaboration-aware, that is a future product decision and should not be smuggled in through deployment shortcuts.

For the current stage, the first rule wins.

## 4. Deployment options

### Option A. Local install runtime per user

Shape:
- each operator installs Lattice locally
- `lattice start` remains the main entry
- each operator has their own config, DB, storage, logs, cache, and external-root wiring

Why it fits:
- strongest match to `local-first`
- strongest match to `single-operator-first`
- preserves local inspectability, recovery, offline survivability, and data ownership
- keeps Obsidian/Zotero and local file paths conceptually honest

Pros:
- best alignment with product positioning
- easiest personalization story
- lowest risk of accidental multi-tenant platform drift
- easier provenance reasoning because runtime truth stays operator-scoped

Cons:
- install/support burden is higher
- updates are harder than on a central server
- non-technical users may need packaging and onboarding help

Recommendation:
- this is the preferred alpha and early-beta shape

### Option B. Managed personal instance per user

Shape:
- each operator gets a dedicated hosted runtime
- one VM/container/volume set per user
- each instance has isolated config, DB, storage, logs, cache, and secrets
- access may still be through a browser, but the runtime boundary remains personal

Why it fits:
- keeps the product unit as `one operator = one runtime`
- gives hosted convenience without forcing shared state
- avoids premature workspace/platform semantics

Pros:
- good compromise between operability and product integrity
- easier remote support than pure local install
- makes backups, updates, and onboarding more manageable
- can still preserve user-owned export/import and local artifact semantics

Cons:
- higher infra cost than a shared app server
- requires provisioning, lifecycle management, and instance health monitoring
- can create pressure toward centralization if isolation is not kept strict

Recommendation:
- this is the preferred hosted shape if local install proves too heavy

### Option C. Shared multi-user app server

Shape:
- one backend service
- one or a few shared state stores
- many users log into the same runtime plane

Why it does not fit now:
- conflicts with the current `single-operator-first` story
- pushes the product toward workspace/account/platform semantics
- makes personalization a tenancy problem instead of a runtime-shape feature
- increases risk around provenance, path exposure, external-root modeling, and artifact ownership

Pros:
- cheapest infra per user
- easiest centralized updates
- easiest way to hand out a URL quickly

Cons:
- weakest product alignment
- highest architecture drift risk
- forces authz/tenancy decisions the repo has not adopted
- makes per-user external filesystem integration awkward or artificial

Recommendation:
- do not use this as the primary product deployment model
- acceptable only for tightly controlled internal demos where no one mistakes it for the intended product shape

## 5. Required isolation boundary per operator

If a deployment option claims to preserve personal runtime behavior, each operator should have isolated:

- `config.yaml` or equivalent config root
- `state.db`
- storage/artifact roots
- logs root
- cache root
- API/provider keys
- model/provider selection
- Obsidian vault path or adapter config
- Zotero base path or adapter config
- any user-visible exports and watch folders

In current runtime terms, that maps directly onto the runtime-path layer and related env overrides such as:

- `PAPERPIPE_HOME`
- `PAPERPIPE_CONFIG_PATH`
- `PAPERPIPE_CONFIG_DIR`
- `PAPERPIPE_STORAGE_DIR`
- `PAPERPIPE_DB_PATH`
- `PAPERPIPE_LOGS_DIR`
- `PAPERPIPE_CACHE_DIR`
- install-layout app roots behind `PAPERPIPE_INSTALL_LAYOUT=1`

If these are shared across users, the deployment is not truly personal-runtime-aligned.

## 6. Recommended rollout path

### Stage 1. Close-person alpha

Recommended shape:
- local install per user

Target tester profile:
- technically comfortable researcher or close collaborator

Why:
- it matches the current alpha-share decision better than a shared hosted server
- it exposes real local-first friction honestly instead of hiding it behind central ops

Target scale:
- keep this to a very small number of testers until install/update/support polish improves

### Stage 2. Managed beta

Recommended shape:
- managed personal instance per user

Why:
- preserves the product boundary while reducing support burden
- lets the team learn what should stay local, what can be centrally managed, and what truly needs remote hosting

Suggested use:
- external beta users who need less setup burden
- institutions or labs that want a supported deployment without shared runtime state

### Stage 3. Future product fork only if explicitly chosen

Possible shape:
- shared multi-user platform

Constraint:
- treat this as a separate product-shape decision, not as a deployment convenience

Before taking this path, the product would need explicit adoption of:
- tenancy/account model
- collaboration and ownership semantics
- per-user and shared artifact policy
- permission model
- support, billing, and recovery model

## 7. Near-term implementation recommendation

For the current repo, the best near-term path is:

1. keep `lattice start` as the canonical entry
2. continue installability hardening around personal runtime roots
3. package local install first for macOS-first close-person alpha
4. if hosting is needed, build a single-tenant deployment template rather than a shared app server

Concrete implication:
- package and operate `a runtime template`
- not `a shared app`

That template should be able to run:
- locally on a user's machine
- or remotely as one isolated instance for one operator

without changing the runtime truth model.

## 8. What should not happen next

Avoid these shortcuts:

- using one shared server as the default distribution path because it is operationally easier
- introducing account/workspace semantics indirectly through deployment glue
- treating per-user filesystem adapters as if they were naturally multi-tenant
- collapsing operator-owned artifacts into one shared store before ownership semantics exist
- narrating a shared hosted setup as if it were equivalent to the intended local-first product

## 9. One-sentence recommendation

Ship Lattice as a `personal runtime product` first: local install by default, managed single-tenant hosting when needed, and no shared multi-user server as the default product shape.
