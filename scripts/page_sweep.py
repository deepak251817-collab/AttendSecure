"""Crawl every nav link for each role and report any page that fails.

Run inside the web container:
    docker exec attendance-web python scripts/page_sweep.py
Or locally against a running dev server:
    python scripts/page_sweep.py
"""
from __future__ import annotations

import http.cookiejar
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:5000"
# Credentials match scripts/seed_demo.py demo accounts (dev/demo only).
ROLES = {
    "admin": "adminpass",
    "teacher1": "teach@123",
    "student_cseA01": "study@123",
}


def _open(opener: urllib.request.OpenerDirector, url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "page-sweep/1.0"})
    return opener.open(req, timeout=15)


def crawl(opener: urllib.request.OpenerDirector, start: str, label: str) -> list[str]:
    failures: list[str] = []
    queue = [start]
    seen: set[str] = set()
    while queue:
        url = queue.pop()
        if url in seen:
            continue
        seen.add(url)
        try:
            resp = _open(opener, url)
            body = resp.read().decode("utf-8", "replace")
            status = resp.status
        except urllib.error.HTTPError as exc:
            failures.append(f"{label}: HTTP {exc.code} {url}")
            continue
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{label}: ERROR {url} ({exc})")
            continue
        if status != 200:
            failures.append(f"{label}: HTTP {status} {url}")
            continue
        # Follow same-site links found in the page.
        for href in re.findall(r'href="([^"#?]+)"', body):
            if "/static/" in href:
                continue
            full = urllib.parse.urljoin(url, href)
            parsed = urllib.parse.urlparse(full)
            if parsed.netloc == urllib.parse.urlparse(BASE).netloc:
                queue.append(urllib.parse.urlunparse(parsed))
    return failures


def main() -> int:
    all_failures: list[str] = []
    for username, password in ROLES.items():
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

        # Login (WSGI server sets the CSRF cookie; re-parse it from the page).
        try:
            page = _open(opener, f"{BASE}/login").read().decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            all_failures.append(f"{username}: cannot load /login ({exc})")
            continue
        match = re.search(r'name="csrf_token" value="([^"]+)"', page)
        if not match:
            all_failures.append(f"{username}: no csrf_token on /login")
            continue
        data = urllib.parse.urlencode({
            "username": username,
            "password": password,
            "csrf_token": match.group(1),
        }).encode()
        try:
            resp = opener.open(f"{BASE}/login", data=data, timeout=15)
            if "/login" in resp.geturl():
                all_failures.append(f"{username}: login failed (redirected back)")
                continue
            dashboard = resp.geturl()
        except Exception as exc:  # noqa: BLE001
            all_failures.append(f"{username}: login request failed ({exc})")
            continue

        failures = crawl(opener, dashboard, username)
        print(f"[{username}] dashboard OK -> {dashboard}, "
              f"{len(failures)} failing page(s)")
        all_failures.extend(failures)

    print("\n=== FAILURES ===" if all_failures else "\nAll pages OK.")
    for failure in all_failures:
        print(" ", failure)
    return 1 if all_failures else 0


if __name__ == "__main__":
    sys.exit(main())
