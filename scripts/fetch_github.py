#!/usr/bin/env python3
"""Refresh data/github/*.json from the GitHub API (stdlib only).

Token: $GITHUB_TOKEN, else `gh auth token`. Any fetch that fails keeps the
previously committed JSON, so the site always builds.
"""
import json, os, re, subprocess, sys, urllib.request
from pathlib import Path

USER = "Vishrut2403"
CONTRIB_MD = f"repos/{USER}/{USER}/contents/docs/contributions.md"
OUT = Path(__file__).resolve().parent.parent / "data" / "github"


def token():
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    try:
        return subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    except Exception:
        return ""


def api(path, body=None, raw=False):
    req = urllib.request.Request(f"https://api.github.com/{path}", data=json.dumps(body).encode() if body else None)
    req.add_header("Accept", "application/vnd.github.raw" if raw else "application/vnd.github+json")
    if tok := token():
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read().decode()
    return data if raw else json.loads(data)


def repos():
    return {r["name"]: {
        "url": r["html_url"], "description": r["description"] or "", "language": r["language"] or "",
        "stars": r["stargazers_count"], "homepage": r["homepage"] or "", "fork": r["fork"], "topics": r["topics"],
    } for r in api(f"users/{USER}/repos?per_page=100&type=owner")}


def calendar():
    q = """query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{
      totalContributions weeks{contributionDays{date contributionCount contributionLevel weekday}}}}}}"""
    cal = api("graphql", {"query": q, "variables": {"u": USER}})["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    lvl = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
    return {"total": cal["totalContributions"], "weeks": [
        [{"date": d["date"], "count": d["contributionCount"], "level": lvl[d["contributionLevel"]], "weekday": d["weekday"]}
         for d in w["contributionDays"]] for w in cal["weeks"]]}


LINK = r"\[(.+?)\]\((.+?)\)"


def parse_contributions(md):
    out = {"updated": "", "repos": [], "shadow": []}
    if m := re.search(r"_Last updated: ([\d-]+)_", md):
        out["updated"] = m[1]
    shadow = False
    for line in md.splitlines():
        if line.startswith("## Shadow"):
            shadow = True
        elif m := re.match(rf"##+ {LINK}", line):
            repo = {"name": m[1], "url": m[2], "prs": []}
            if not shadow:
                out["repos"].append(repo)
        elif not shadow and (m := re.match(rf"- {LINK} _\(merged ([\d-]+)\)_", line)):
            repo["prs"].append({"title": m[1], "url": m[2], "number": m[2].rstrip("/").split("/")[-1], "date": m[3]})
        elif shadow and (m := re.match(rf"- {LINK} — \*\*(.+?)\*\*", line)):
            out["shadow"].append({"repo": repo["name"], "repo_url": repo["url"], "title": m[1], "url": m[2],
                                  "number": m[2].rstrip("/").split("/")[-1], "status": m[3]})
        elif shadow and (m := re.match(rf"\s+- Commit: {LINK}", line)):
            out["shadow"][-1].update(commit=m[1], commit_url=m[2])
    out["total"] = sum(len(r["prs"]) for r in out["repos"])
    return out


def save(name, fn):
    try:
        data = fn()
    except Exception as e:  # keep the committed copy
        print(f"warn: {name}: {e}", file=sys.stderr)
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(data, indent=1))
    print(f"wrote data/github/{name}.json")


def _check():
    sample = """_Last updated: 2026-10-31_
## [RPCS3/rpcs3](https://github.com/RPCS3/rpcs3)
- [overlay: Add trophy list sorting](https://github.com/RPCS3/rpcs3/pull/18965) _(merged 2026-07-31)_
## Shadow Contributions
### [fish-shell/fish-shell](https://github.com/fish-shell/fish-shell)
- [env: fix stale $PWD](https://github.com/fish-shell/fish-shell/pull/12714) — **✓ Applied upstream**
  - Commit: [411a432](https://github.com/fish-shell/fish-shell/commit/411a432)
"""
    p = parse_contributions(sample)
    assert p["updated"] == "2026-10-31" and p["total"] == 1
    assert p["repos"][0]["prs"][0]["number"] == "18965"
    assert p["shadow"][0]["repo"] == "fish-shell/fish-shell" and p["shadow"][0]["commit"] == "411a432"


if __name__ == "__main__":
    _check()
    if "--check" not in sys.argv:
        save("repos", repos)
        save("calendar", calendar)
        save("contributions", lambda: parse_contributions(api(CONTRIB_MD, raw=True)))
