---
name: gh-connect
description: Authenticate the gh CLI for the three project repos (estimator, parts, bleed) using the PAT stored in the estimator .env. Use this before any GitHub operation. Triggered by phrases like "connect to GH", "connect github", "gh connect", "authenticate github", "log in to github".
allowed-tools: Bash
---

# gh-connect — authenticate the gh CLI

The default `gh` login in this environment fails with `HTTP 401: Bad credentials`. The working
credential is a Personal Access Token (project scope) stored in `/home/markfyoung/estimator/.env`
as `export GITHUB_PAT=...`. The file's `export GH_TOKEN=$GITHUB_PAT` line only works when `.env` is
sourced; grepping it yields the literal text `$GITHUB_PAT`, so always read the `GITHUB_PAT` line. `gh` reads `GH_TOKEN` from the
environment, so the job of this skill is simply to load that token into the shell's environment
before any `gh` call.

## The three repos

| Repo (local)        | GitHub slug                     |
|---------------------|---------------------------------|
| `~/estimator`       | `markfyoung0711/jpy_estimator`  |
| `~/parts`           | `markfyoung0711/parts`          |
| `~/bleed`           | `markfyoung0711/bleed`          |

Note the estimator local dir is `jpy_estimator` on GitHub — always pass `--repo` explicitly when
you want a specific repo, don't rely on the cwd remote.

## Connect

Export the token from `.env`, then every `gh` call in the **same Bash invocation** is authenticated.
Shell state does not persist across separate Bash tool calls, so either prefix each `gh` command
with the export, or run a multi-command block:

```
export GH_TOKEN=$(grep -E '^export GITHUB_PAT=' /home/markfyoung/estimator/.env | sed 's/^export GITHUB_PAT=//')
gh auth status 2>&1 | head -3
```

A healthy connection prints `✓ Logged in to github.com account markfyoung0711 (GH_TOKEN)`.

## Rules

- Never print the token value. The export line above keeps it inside `$GH_TOKEN`; don't echo it.
- If `.env` has no `GITHUB_PAT` line, stop and tell the user the token is missing — do **not** fall
  back to `gh auth login` (interactive, won't work here).
- This skill only establishes auth. Callers (e.g. the `top-issues` skill) run their own `gh` queries
  after invoking it.
