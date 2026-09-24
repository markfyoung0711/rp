---
name: top-issues
description: Produce a leverage-ranked digest of the highest-priority open GitHub issues across the three project repos (estimator, parts, bleed) — or the single #1 issue. Triggered by phrases like "top issues", "top single issue", "top issue", "what's the #1 issue", "top github issues", "what are the top issues", "priority issues", "what should I work on from github", "issue digest".
allowed-tools: Bash, Skill
---

# top-issues — ranked GitHub issue digest across the three repos

Surface the issues that most deserve attention right now, **cross-repo across all three project
repos** (estimator + parts + bleed), ranked by priority and actionability — so Mark can pick the next
thing to work on without opening three issue lists by hand.

## Parse the request: "top N issues" (the general rule)

The skill is fundamentally **"top N"** — always pull + rank the same way (Steps 2–3), then output the
top **N** ranked issues. Read N and scope from the request:

- **N** = the count, if given. Match any phrasing: "top 5", "top 3 issues", "give me the top 7",
  "top ten". If no number is given ("top issues", "issue digest", "what should I work on"), default
  **N = ~10**.
- **N = 1** ("top issue", "top single issue", "the #1 issue", "single top issue", "what's the one
  thing") → output **exactly one** issue in the single-issue format (Step 4). It's just N=1, not a
  separate mode.
- **Scope** = cross-repo across all three repos **by default**. If a specific repo is named ("top
  estimator issues", "top 3 bleed issues"), restrict the pull to that repo, then take the top N.

So "top N issues" works in general for any N ≥ 1, with or without a repo scope.

## Step 1 — connect

Authenticate the gh CLI first by invoking the **`gh-connect`** skill (it loads `GH_TOKEN` from
`.env`). Without it, every `gh` call returns `HTTP 401`. Because shell state doesn't persist between
Bash calls, prefix the issue queries below with the same export line `gh-connect` uses.

## Step 2 — pull open issues from all three repos

```
export GH_TOKEN=$(grep -E '^export GH_TOKEN=' /home/markfyoung/estimator/.env | sed 's/^export GH_TOKEN=//')
for repo in jpy_estimator parts bleed; do
  echo "===== $repo ====="
  gh issue list --repo markfyoung0711/$repo --state open --limit 100 \
    --json number,title,labels,updatedAt \
    --jq '.[] | "#\(.number)\t[\(.labels|map(.name)|join(","))]\t\(.updatedAt[0:10])\t\(.title)"'
done
```

(If the user named a single repo — "top estimator issues" — restrict to that one. If they gave a
count — "top 5" — cap the digest at that many; default is **top ~10 overall**.)

## Step 3 — rank

Sort into priority tiers using the label conventions in each repo (highest first):

1. **Locked / committed** — estimator `priority-locked`; anything the issue body marks as a promise
   to Jeff/Patrick. These are commitments, not options.
2. **Active track-a (architecture/model)** — estimator `track-a`; parts `track:b` (the LINC2 baseline
   build chain B0–B11); bleed `module:1` + `needs:sme-interview` (the Jeff hand-labeling gates that
   unblock the classifiers).
3. **Cross-repo blockers** — anything labeled `status:blocked-on-estimator` (parts) or `cross-repo`
   (bleed/estimator). Call these out explicitly: they gate work in *another* repo, so they punch
   above their tier.
4. **Track-b data/acquisition** — estimator `track-b` (parsers/scrapers/registry), the acquisition
   buildout.
5. **Everything else** — `track-c`, `priority-parking-lot`, `non-curriculum`, `documentation`,
   `status:deferred`. Mention count, don't enumerate unless asked.

Within a tier, prefer issues that are **recently updated** (active threads) and ones that **unblock
the most downstream work** (a blocker that frees a whole chain outranks a leaf task).

Cross-reference the **current focus** before finalizing the order: read `project_priorities.md` and
the newest `project_acquisition_pillar_*` / `project_bleed_*` memory entries. The standing top focus
(Mark, 2026-06-27) is two concrete things — rank issues touching these **above** their label tier:

1. **Get ACQ (Pillar 1 acquisition) moving autonomously** — the reusable framework + scheduler that
   drives unattended recurring downloads of every source (snapshot store + per-source adapter +
   Cloud Run scheduling). Next concrete step = the Naperville import adapter (source #2).
2. **Fingerprint on docs** — the identity / format-recognizer layer that stamps each captured doc
   (provenance ≠ format, fingerprint → reader-ladder), starting with the IDOT 6/12 letting corpus.

Note where this live focus is **not yet a filed issue** (the acquisition framework + scheduler and
the autonomous-fingerprint push currently live only in memory, not github) so the digest doesn't read
as "github is the whole picture." Surface those as **un-filed focal points** at the top, then the
ranked github issues below.

## Step 4 — output

**N = 1:** output only `repo#number — title` and a 2–3 sentence why (tier, what it unblocks, next
concrete action). Stop there — no list, no tiers.

**N ≥ 2:** a compact ranked list of the top N. For each issue:

- `repo#number` — title
- one-line **why it's ranked here** (the label tier + any blocker/commitment/focus reason)

Group by tier, highest first. End with a one-line **"pick next"** recommendation tied to the current
focus, and a count of everything dropped below the cut.

Keep it scannable — this is a triage view, not a full report. Don't rewrite issue bodies; link by
number so Mark can open the ones he wants.
