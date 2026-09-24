"""Assemble plans/solution.md from the plan sources and the GitHub issues.

solution.md is generated; edit the sources (spec.md, sample-analysis.md, design.md, actors.md,
use-cases.md, decisions.md, GitHub issues) and re-run:

    GH_TOKEN=... python3 plans/build_solution.py
"""
import datetime
import json
import re
import subprocess
from pathlib import Path

PLANS = Path(__file__).parent
REPO = "markfyoung0711/rp"
ISSUE_URL = f"https://github.com/{REPO}/issues/"


def read(name):
    return (PLANS / name).read_text()


def drop_title_and_banner(md):
    """Remove the leading '# Title' line and the '> ...' banner that follows it."""
    lines = md.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    while lines and (not lines[0].strip() or lines[0].startswith(">")):
        lines = lines[1:]
    return "\n".join(lines)


def transform(md, demote=0):
    """Demote headings and link bare #N issue refs, leaving code fences and inline code alone."""
    out, fenced = [], False
    for line in md.splitlines():
        if line.startswith("```"):
            fenced = not fenced
            out.append(line)
            continue
        if fenced:
            out.append(line)
            continue
        if demote and re.match(r"#{1,6} ", line):
            line = "#" * demote + line
        parts = re.split(r"(`[^`]*`)", line)
        parts = [
            p if p.startswith("`") else re.sub(r"(?<![\w/\[&#])#(\d{1,3})\b", rf"[#\1]({ISSUE_URL}\1)", p)
            for p in parts
        ]
        out.append("".join(parts))
    return "\n".join(out)


def section(md, start, stop=None):
    """Text from heading `start` up to (not including) heading `stop`."""
    i = md.index(start)
    j = md.index(stop, i) if stop else len(md)
    return md[i:j].rstrip()


def issues():
    try:
        raw = subprocess.run(
            ["gh", "issue", "list", "-R", REPO, "--state", "all", "--limit", "100",
             "--json", "number,title,labels,state,body"],
            check=True, capture_output=True, text=True,
        ).stdout
        return sorted(json.loads(raw), key=lambda i: i["number"])
    except Exception as e:  # keep the doc buildable offline
        print(f"warning: could not fetch issues ({e})")
        return []


def main():
    spec = read("spec.md")
    design = drop_title_and_banner(read("design.md"))
    actors = read("actors.md")
    use_cases = read("use-cases.md")
    decisions = drop_title_and_banner(read("decisions.md")).split("## How to add an entry")[0]
    analysis = read("sample-analysis.md")
    today = datetime.date.today().isoformat()
    readme = (PLANS.parent / "README.md").read_text()
    # Drop the README title, demote its sections, and re-point its repo-relative links from plans/.
    body = readme.split("\n", 1)[1].replace("](plans/", "](")
    body = re.sub(r"\]\((?!https?:|#|\.\./)([^)]+)\)", lambda m: f"](../{m.group(1)}" + ")" if "/" in m.group(1) or m.group(1).endswith(".md") and not (PLANS / m.group(1)).exists() else m.group(0), body)
    built = transform(body, demote=1)

    parts = [f"""# Solution: Context-Aware Messaging Bot for Rental Housing

**Author:** Mark F. Young · **Updated:** {today} · **Status:** v0.2 built and tested; the platform beyond the core is designed, not built

This one document combines what was built, the original assignment, our analysis of the sample data, the solution design, the actor walkthroughs, the use cases, the decision register, the work plan (GitHub issues), and the review, test, performance and PII results. It is generated from the repo by `plans/build_solution.py`.

## For the reviewer

**How to read the labels**

| Label | Meaning |
|---|---|
| **ORIGINAL** | Copied word for word from the assignment. This is the graded scope (use cases UC-01 to UC-03). |
| **ANALYSIS** | Our inference from the assignment's data (only 2 sample records). A hypothesis. |
| **ADD-ON (MFY)** | Mark F. Young's extension beyond the assignment. |

**Start with Part 0 (what was built and how to run it).** Everything after Part 1 was written before the build, then corrected by two independent reviews (Appendix A); the decision register (Part 5) records every change.

**Questions that shaped the design (answered by the reviews)**
1. Does the design respect "learns what to do only from input data"? It is mostly deterministic rules plus an LLM for the wording (D-014, Part 2 §7).
2. Which rules inferred from only 2 samples are overfit (D-002)?
3. Is the add-on scope (D-003 to D-020) at risk of crowding out the graded core?
4. Gaps and risks: security and PII (§9), demo auth (§10), database choice (§5), and legal and competitive exposure (§13).
5. Anything missing from the use cases, actors or data elements.

The independent reviews ([#9]({ISSUE_URL}9)) answered these; their findings are recorded in the decision register (Part 5).

**Contents**
0. What was built (v0.2)
1. The original assignment
2. Solution design
3. Actor walkthroughs
4. Use-case traceability
5. Decision register
6. Work plan (GitHub issues)
- Appendix A: critical reviews · B: code-review results · C: performance · D: PII categories · E: demo tests

---

# Part 0 — What was built (v0.2)

> From [`README.md`](../README.md). Run `uv run bot.py -i plans/sample.jsonl --compare` to see both samples match every field.

{{BUILT}}

---

# Part 1 — The original assignment
""",
        "> **ORIGINAL** — the assignment as given (`plans/spec.md`), unedited.\n",
        transform(spec, demote=1),
        "\n",
        transform(analysis, demote=1),
        "\n",
        transform(read("holdout-prep.md"), demote=1),
        "\n---\n\n# Part 2 — Solution design\n\n> **ADD-ON (MFY)** except where it says ORIGINAL.\n",
        transform(design, demote=0),
        "\n---\n\n# Part 3 — Actor walkthroughs\n\n> **ADD-ON (MFY).** How the system works from each actor's point of view. The data model and UX are covered in Part 2.\n",
        transform(section(actors, "The system has five actors", "## UX surfaces"), demote=0),
        "\n---\n\n# Part 4 — Use-case traceability\n\n> Who takes part in each use case, and which issue covers it. How each one works is in Part 2 §3.\n",
        transform(section(use_cases, "## Original scope", "## Demo scenario"), demote=0),
        "\n---\n\n# Part 5 — Decision register\n",
        transform(decisions, demote=0),
        "\n---\n\n# Part 6 — Work plan (GitHub issues)\n",
    ]

    parts[0] = parts[0].replace("{BUILT}", built)

    items = issues()
    if items:
        rows = ["| # | Title | Labels | State |", "|---|---|---|---|"]
        for i in items:
            labels = ", ".join(l["name"] for l in i["labels"])
            rows.append(f"| [#{i['number']}]({ISSUE_URL}{i['number']}) | {i['title']} | {labels} | {i['state'].lower()} |")
        parts.append("\n".join(rows) + "\n\n" + transform(
            "**Status:** planning and reviews done (#1, #2, #4, #9); the core bot shipped (#11); #5 and #6 in progress; #3, #7, #8, #10 deferred (designed, not built).") + "\n")
        for i in items:
            parts.append(f"\n## [#{i['number']}]({ISSUE_URL}{i['number']}) {i['title']}\n")
            parts.append(transform(i["body"].replace("\r\n", "\n"), demote=2))
    else:
        parts.append("_Issues could not be fetched; see the GitHub repo._\n")

    for letter, title, name in (("A", "Critical reviews", "review.md"), ("B", "Code-review results", "code-review-results.md"),
                                ("C", "Performance", "performance.md"), ("D", "PII categories and handling", "pii-categories.md"),
                                ("E", "Demo tests", "demo-tests.md")):
        body = drop_title_and_banner(read(name))
        parts.append(f"\n---\n\n# Appendix {letter} — {title}\n\n> From `plans/{name}`.\n")
        parts.append(transform(body, demote=1))

    (PLANS / "solution.md").write_text("\n".join(parts).rstrip() + "\n")
    print(f"wrote {PLANS / 'solution.md'}")


if __name__ == "__main__":
    main()
