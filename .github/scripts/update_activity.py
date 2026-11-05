"""Refresh recent public activity and recently pushed repositories in README."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


USERNAME = "Aromal-m-b"
README = "README.md"
START = "<!--START_SECTION:activity-->"
END = "<!--END_SECTION:activity-->"
EVENTS_URL = f"https://api.github.com/users/{USERNAME}/events/public?per_page=100"
REPOS_URL = (
    f"https://api.github.com/users/{USERNAME}/repos"
    "?type=owner&sort=pushed&direction=desc&per_page=100"
)
REPOS_START = "<!--START_SECTION:repos-->"
REPOS_END = "<!--END_SECTION:repos-->"
REPO_LOOKBACK_DAYS = 120


def markdown_escape(value: str) -> str:
    return re.sub(r"([\\`*_{}\[\]()<>#+.!|])", r"\\\1", value)


def format_event(event: dict) -> str | None:
    event_type = event.get("type", "")
    payload = event.get("payload") or {}
    repository = (event.get("repo") or {}).get("name")
    if not repository:
        return None

    repo_link = f"[{markdown_escape(repository)}](https://github.com/{repository})"
    date = (event.get("created_at") or "")[:10]
    try:
        date = datetime.strptime(date, "%Y-%m-%d").strftime("%b %d, %Y")
    except ValueError:
        date = "recently"

    if event_type == "PushEvent":
        commits = payload.get("commits") or []
        count = int(payload.get("size") or len(commits) or 1)
        label = "commit" if count == 1 else "commits"
        return f"- `PUSH` · **{count} {label}** to {repo_link} · {date}"

    if event_type == "PullRequestEvent":
        action = markdown_escape(str(payload.get("action") or "updated"))
        number = (payload.get("pull_request") or {}).get("number")
        if number:
            link = f"https://github.com/{repository}/pull/{number}"
            return f"- `PULL REQUEST` · {action} [#{number}]({link}) in {repo_link} · {date}"
        return f"- `PULL REQUEST` · {action} in {repo_link} · {date}"

    if event_type == "IssuesEvent":
        action = markdown_escape(str(payload.get("action") or "updated"))
        number = (payload.get("issue") or {}).get("number")
        if number:
            link = f"https://github.com/{repository}/issues/{number}"
            return f"- `ISSUE` · {action} [#{number}]({link}) in {repo_link} · {date}"
        return f"- `ISSUE` · {action} in {repo_link} · {date}"

    if event_type == "ReleaseEvent":
        release = payload.get("release") or {}
        tag = markdown_escape(str(release.get("tag_name") or "release"))
        return f"- `RELEASE` · published **{tag}** in {repo_link} · {date}"

    if event_type == "IssueCommentEvent":
        issue = payload.get("issue") or {}
        number = issue.get("number")
        if number:
            link = f"https://github.com/{repository}/issues/{number}"
            return f"- `DISCUSSION` · commented on [#{number}]({link}) in {repo_link} · {date}"

    return None


def fetch_json(url: str) -> list[dict]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-readme",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def format_repository(repository: dict, now: datetime) -> str | None:
    full_name = str(repository.get("full_name") or "")
    if not full_name.lower().startswith(f"{USERNAME.lower()}/"):
        return None
    if full_name.lower() == f"{USERNAME.lower()}/{USERNAME.lower()}":
        return None
    if repository.get("fork") or repository.get("archived") or repository.get("disabled"):
        return None

    pushed_at = repository.get("pushed_at")
    if not pushed_at:
        return None
    try:
        pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if pushed < now - timedelta(days=REPO_LOOKBACK_DAYS):
        return None

    language = markdown_escape(str(repository.get("language") or "Mixed stack"))
    stars = int(repository.get("stargazers_count") or 0)
    description = " ".join(str(repository.get("description") or "No description yet.").split())
    if len(description) > 150:
        description = description[:147].rstrip() + "…"
    description = markdown_escape(description)
    pushed_date = pushed.strftime("%b %d, %Y")
    link = f"https://github.com/{full_name}"
    return (
        f"- [**{markdown_escape(full_name.split('/', 1)[1])}**]({link})"
        f" · `{language}` · ⭐ {stars} · pushed {pushed_date} — {description}"
    )


def event_signature(event: dict) -> tuple[str, ...]:
    payload = event.get("payload") or {}
    repository = (event.get("repo") or {}).get("name", "")
    event_type = str(event.get("type") or "")
    date = str(event.get("created_at") or "")[:10]

    if event_type == "PushEvent":
        return event_type, repository, date
    if event_type == "PullRequestEvent":
        pull_request = payload.get("pull_request") or {}
        return event_type, repository, str(payload.get("action") or ""), str(pull_request.get("number") or "")
    if event_type == "IssuesEvent":
        issue = payload.get("issue") or {}
        return event_type, repository, str(payload.get("action") or ""), str(issue.get("number") or "")
    if event_type == "IssueCommentEvent":
        issue = payload.get("issue") or {}
        return event_type, repository, date, str(issue.get("number") or "")
    if event_type == "ReleaseEvent":
        release = payload.get("release") or {}
        return event_type, repository, str(release.get("tag_name") or "")
    return event_type, repository, str(event.get("id") or "")


def replace_readme_block(start: str, end: str, lines: list[str]) -> None:
    with open(README, "r", encoding="utf-8") as file:
        content = file.read()
    pattern = re.compile(rf"{re.escape(start)}.*?{re.escape(end)}", re.DOTALL)
    if not pattern.search(content):
        raise ValueError(f"README markers are missing: {start} / {end}")
    replacement = "\n".join([start, *lines, end])
    with open(README, "w", encoding="utf-8", newline="\n") as file:
        file.write(pattern.sub(lambda _: replacement, content, count=1))


def main() -> int:
    try:
        events = fetch_json(EVENTS_URL)
        repositories = fetch_json(REPOS_URL)
    except (HTTPError, URLError, TimeoutError) as error:
        print(f"Could not fetch public activity: {error}", file=sys.stderr)
        return 1

    lines: list[str] = []
    seen: set[tuple[str, ...]] = set()
    for event in events:
        line = format_event(event)
        signature = event_signature(event)
        if line and signature not in seen:
            lines.append(line)
            seen.add(signature)
        if len(lines) == 6:
            break

    if not lines:
        lines = [f"- No recent public events. [View GitHub activity](https://github.com/{USERNAME}?tab=activity)."]

    repo_lines: list[str] = []
    now = datetime.now(timezone.utc)
    for repository in repositories:
        line = format_repository(repository, now)
        if line:
            repo_lines.append(line)
        if len(repo_lines) == 6:
            break

    if not repo_lines:
        repo_lines = [
            f"- No public repository pushes in the last {REPO_LOOKBACK_DAYS} days. "
            f"[Browse repositories](https://github.com/{USERNAME}?tab=repositories)."
        ]

    replace_readme_block(START, END, lines)
    replace_readme_block(REPOS_START, REPOS_END, repo_lines)
    print(
        f"Updated README activity with {len(lines)} entries and "
        f"{len(repo_lines)} recently pushed repositories."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
