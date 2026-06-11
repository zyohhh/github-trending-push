import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from html import unescape


DEFAULT_TRENDING_URL = "https://github.com/trending?since=daily"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def request_json(url, *, method="GET", payload=None, timeout=20):
    data = None
    headers = {
        "User-Agent": "github-hot-push/1.0",
        "Accept": "application/json",
    }

    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return json.loads(body)


def request_text(url, *, timeout=20):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "github-hot-push/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def clean_html(value):
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def parse_count(value):
    value = value.strip().replace(",", "")
    try:
        return int(value)
    except ValueError:
        return 0


def parse_github_trending(html, limit):
    articles = re.findall(
        r'<article[^>]*class="[^"]*\bBox-row\b[^"]*"[^>]*>(.*?)</article>',
        html,
        flags=re.DOTALL,
    )
    repos = []

    for article in articles[:limit]:
        link_match = re.search(r'<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', article, flags=re.DOTALL)
        if not link_match:
            continue

        href = unescape(link_match.group(1))
        full_name = clean_html(link_match.group(2)).replace(" / ", "/")
        description_match = re.search(r'<p[^>]*class="[^"]*\bmy-1\b[^"]*"[^>]*>(.*?)</p>', article, flags=re.DOTALL)
        language_match = re.search(r'<span[^>]*itemprop="programmingLanguage"[^>]*>(.*?)</span>', article, flags=re.DOTALL)
        stars_match = re.search(r'href="[^"]*/stargazers"[^>]*>.*?</svg>\s*([0-9,]+)\s*</a>', article, flags=re.DOTALL)
        today_match = re.search(r'([0-9,]+)\s+stars?\s+today', clean_html(article), flags=re.IGNORECASE)

        repos.append(
            {
                "full_name": full_name,
                "url": f"https://github.com{href}",
                "description": clean_html(description_match.group(1)) if description_match else "No description",
                "language": clean_html(language_match.group(1)) if language_match else "Unknown",
                "stars": parse_count(stars_match.group(1)) if stars_match else 0,
                "today_stars": parse_count(today_match.group(1)) if today_match else 0,
            }
        )

    return repos


def fetch_from_trending_api(url, limit):
    repos = request_json(url)
    if not isinstance(repos, list):
        raise RuntimeError("Trending API returned an unexpected response.")

    normalized = []
    for repo in repos[:limit]:
        author = repo.get("author") or ""
        name = repo.get("name") or ""
        normalized.append(
            {
                "full_name": f"{author}/{name}".strip("/"),
                "url": repo.get("url") or "",
                "description": repo.get("description") or "No description",
                "language": repo.get("language") or "Unknown",
                "stars": repo.get("stars") or 0,
                "today_stars": repo.get("currentPeriodStars") or 0,
            }
        )

    return normalized


def fetch_trending_repositories(limit):
    api_url = os.environ.get("TRENDING_API_URL")
    if api_url:
        repos = fetch_from_trending_api(api_url, limit)
        if repos:
            return repos

    trending_url = os.environ.get("GITHUB_TRENDING_URL", DEFAULT_TRENDING_URL)
    repos = parse_github_trending(request_text(trending_url), limit)
    if not repos:
        raise RuntimeError("No trending repositories found.")

    return repos


def format_number(value):
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def build_plain_text(repos):
    generated_at = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M UTC+8")
    lines = [
        "今日 GitHub 热门开源项目",
        f"生成时间：{generated_at}",
        "",
    ]

    for index, repo in enumerate(repos, start=1):
        lines.extend(
            [
                f"{index}. {repo['full_name']}",
                f"   {repo['description']}",
                f"   语言：{repo['language']} | Stars：{format_number(repo['stars'])} | 今日新增：{format_number(repo['today_stars'])}",
                f"   {repo['url']}",
                "",
            ]
        )

    return "\n".join(lines).strip()


def push_to_feishu(text):
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError("Missing FEISHU_WEBHOOK_URL environment variable.")

    payload = {
        "msg_type": "text",
        "content": {
            "text": text,
        },
    }
    request_json(webhook_url, method="POST", payload=payload)


def main():
    limit = int(os.environ.get("TRENDING_LIMIT", "10"))
    dry_run = os.environ.get("DRY_RUN", "").lower() in {"1", "true", "yes"}

    repos = fetch_trending_repositories(limit)
    message = build_plain_text(repos)

    if dry_run:
        print(message)
        return

    push_to_feishu(message)
    print(f"Pushed {len(repos)} repositories to Feishu.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        print(f"HTTP error: {error.code} {error.reason}", file=sys.stderr)
        print(error.read().decode("utf-8", errors="replace"), file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
