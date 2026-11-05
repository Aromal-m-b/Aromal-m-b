"""Refresh the recent public GitHub activity block in the profile README."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


USERNAME = "Aromal-m-b"
README = "README.md"
START = "<!--START_SECTION:activity-->"
END = "<!--END_SECTION:activity-->"
EVENTS_URL = f"https://api.github.com/users/{USERNAME}/events/public?per_page=100"


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


def fetch_events() -> list[dict]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-readme",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(EVENTS_URL, headers=headers)
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def update_readme(lines: list[str]) -> None:
    with open(README, "r", encoding="utf-8") as file:
        content = file.read()
    pattern = re.compile(rf"{re.escape(START)}.*?{re.escape(END)}", re.DOTALL)
    if not pattern.search(content):
        raise ValueError("Activity markers are missing from README.md")
    replacement = "\n".join([START, *lines, END])
    with open(README, "w", encoding="utf-8", newline="\n") as file:
        file.write(pattern.sub(lambda _: replacement, content, count=1))


def main() -> int:
    try:
        events = fetch_events()
    except (HTTPError, URLError, TimeoutError) as error:
        print(f"Could not fetch public activity: {error}", file=sys.stderr)
        return 1

    lines: list[str] = []
    seen: set[str] = set()
    for event in events:
        line = format_event(event)
        event_id = str(event.get("id", ""))
        if line and event_id not in seen:
            lines.append(line)
            seen.add(event_id)
        if len(lines) == 6:
            break

    if not lines:
        lines = [f"- No recent public events. [View GitHub activity](https://github.com/{USERNAME}?tab=activity)."]

    update_readme(lines)
    print(f"Updated README activity with {len(lines)} entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
