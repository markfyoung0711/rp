---
name: shutdown-system
description: Shut down the BidEdge API + UI (the uvicorn process that serves both) and optionally the local logging stack. Triggered by phrases like "shutdown system", "shut down the system", "stop the server", "stop api", "stop ui", "kill the server", "bring it down", "tear down system".
allowed-tools: Bash
---

# Shutdown System

Stop the running BidEdge API + UI. Do this immediately and terminately — no confirmation prompts, no "are you sure." Mark uses shutdown as an interrupt signal; honor it.

## Rule from memory

Per `feedback_shutdown_now.md`: when Mark says shut it down, kill it now. No other work first. Report tersely afterward.

## Steps — API + UI (default)

Kill the uvicorn process (the FastAPI that serves both the API and the UI):

```
pkill -f 'uvicorn src.api.main:app'
```

If `pkill` returns non-zero, it means no matching process — the system is already down.

Don't run a health probe afterward. Trust the kill. If the user wants verification, they'll ask.

## Steps — including logging stack

Only do this if the user explicitly asked to bring the logging stack down (Loki + Grafana via docker compose):

```
docker compose down
```

Use `docker compose down -v` only if they ask to drop the Loki data volume.

## Reporting

One line: "system down" (plus a note if logging was also stopped). That's it.

If `pkill` hit nothing and the user clearly expected a running system: one additional line noting the system was already down.

## Not covered by this skill

- Don't kill docker compose unless explicitly asked. Loki/Grafana are often left running across sessions and killing them discards useful state.
- Don't touch system Redis, MySQL, or other services running on this machine — not ours to stop.
- Don't restart. That's the `start-system` skill.
