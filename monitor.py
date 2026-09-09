#!/usr/bin/env python3
"""Monitor car listing searches and Telegram-alert on new ads.

Designed for GitHub Actions every 2 hours. First successful scrape of a
search only seeds seen.json (no flood of existing ads). Later runs notify
only IDs that were not seen before.
"""

from __future__ import annotations

import html as html_lib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
SEARCHES_PATH = ROOT / "searches.json"


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def seen_path() -> Path:
    raw = os.environ.get("SEEN_FILE", "").strip()
    return Path(raw) if raw else ROOT / "seen.json"


def selected_sites() -> set[str] | None:
    raw = ""
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--sites" and i + 1 < len(args):
            raw = args[i + 1]
            break
        if arg.startswith("--sites="):
            raw = arg.split("=", 1)[1]
            break
    if not raw:
        raw = os.environ.get("SITES", "")
    raw = raw.strip()
    if not raw or raw in {"*", "all"}:
        return None
    return {part.strip() for part in raw.split(",") if part.strip()}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

BROWSER_TIMEOUT_MS = 60_000
DELAY_BETWEEN_SEARCHES = 4.0
MAX_ALERTS_PER_RUN = 25

COOKIE_SELECTORS = [
    "#didomi-notice-agree-button",
    "#onetrust-accept-btn-handler",
    "button[data-testid='uc-accept-all-button']",
    "button:has-text('Prihvati sve')",
    "button:has-text('Prihvati')",
    "button:has-text('Slažem se')",
    "button:has-text('Alle akzeptieren')",
    "button:has-text('Akzeptieren und weiter')",
    "button:has-text('Akzeptieren')",
    "button:has-text('Accept all')",
    "button:has-text('Accept')",
]


def load_json(path: Path, fallback):
    if not path.exists():
        return fallback
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    tmp.replace(path)


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ")).strip()


def listing(
    *,
    ad_id: str,
    title: str,
    url: str,
    price: str = "",
    year: str = "",
    km: str = "",
    extra: str = "",
) -> dict[str, str]:
    return {
        "id": str(ad_id),
        "title": clean(title)[:180],
        "url": url,
        "price": clean(price),
        "year": clean(year),
        "km": clean(km),
        "extra": clean(extra),
    }


def looks_blocked(html: str, title: str = "") -> bool:
    blob = f"{title}\n{html[:8000]}".lower()
    needles = [
        "just a moment",
        "pričekajte trenutak",
        "pricekajte trenutak",
        "pričekajte",
        "please wait",
        "access to this page has been denied",
        "pardon our interruption",
        "g-recaptcha",
        "hcaptcha",
        "cf-chl-bypass",
        "checking your browser",
        "um trenutek",
    ]
    return any(n in blob for n in needles)


LISTING_SELECTORS = {
    "avto": ".GO-Results-Row",
    "willhaben": "script#__NEXT_DATA__",
    "njuskalo": "article",
    "index": None,
}


def wait_out_challenge(page, site: str) -> None:
    """Give Cloudflare / Avto.net IUAM time to resolve, then wait for listings."""
    selector = LISTING_SELECTORS.get(site)
    deadline = time.time() + 22
    while time.time() < deadline:
        title = ""
        try:
            title = page.title()
        except Exception:
            pass
        count = 0
        if selector:
            try:
                count = page.locator(selector).count()
            except Exception:
                count = 0
        if count > 0:
            return
        if not looks_blocked("", title):
            break
        page.wait_for_timeout(1000)
    if selector:
        try:
            page.locator(selector).first.wait_for(state="attached", timeout=12_000)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_avto(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict[str, str]] = []
    seen: set[str] = set()

    rows = soup.select(".GO-Results-Row")
    if not rows:
        for link in soup.select("a[href*='details.asp?id=']"):
            href = link.get("href") or ""
            m = re.search(r"id=(\d+)", href, re.I)
            if not m or m.group(1) in seen:
                continue
            ad_id = m.group(1)
            seen.add(ad_id)
            title = clean(link.get("title") or link.get_text(" "))
            if len(title) < 8:
                continue
            out.append(
                listing(
                    ad_id=ad_id,
                    title=title,
                    url=f"https://www.avto.net/Ads/details.asp?id={ad_id}",
                )
            )
        return out

    for row in rows:
        link = row.select_one("a[href*='details.asp?id=']")
        if not link:
            continue
        href = link.get("href") or ""
        m = re.search(r"id=(\d+)", href, re.I)
        if not m or m.group(1) in seen:
            continue
        ad_id = m.group(1)
        seen.add(ad_id)

        title_el = row.select_one(".GO-Results-Naziv")
        title = clean(title_el.get_text(" ") if title_el else "") or clean(
            link.get("title") or link.get_text(" ")
        )
        price_el = row.select_one(".GO-Results-Price-TXT-Regular")
        price = clean(price_el.get_text(" ") if price_el else "")

        year = ""
        km = ""
        for tr in row.select("tr"):
            tds = [clean(td.get_text(" ")) for td in tr.find_all("td")]
            if len(tds) < 2:
                continue
            label = tds[0].lower()
            if "registracija" in label or label in {"letnik", "1.reg."}:
                year = tds[-1]
            elif "km" in label or "prevoženi" in label or "prevozeni" in label:
                km = tds[-1]

        if not km:
            km_m = re.search(r"(\d[\d.\s]*)\s*km", row.get_text(" "), re.I)
            if km_m:
                km = clean(km_m.group(0))

        out.append(
            listing(
                ad_id=ad_id,
                title=title or f"Avto.net oglas {ad_id}",
                url=f"https://www.avto.net/Ads/details.asp?id={ad_id}",
                price=price,
                year=year,
                km=km,
            )
        )
    return out


def _willhaben_attrs(ad: dict) -> dict[str, str]:
    attrs: dict[str, str] = {}
    raw = (ad.get("attributes") or {}).get("attribute") or []
    for item in raw:
        name = item.get("name")
        values = item.get("values") or []
        if name and values:
            attrs[name] = values[0]
    return attrs


def parse_willhaben(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    out: list[dict[str, str]] = []
    seen: set[str] = set()

    if script and script.string:
        try:
            data = json.loads(script.string)
            ads = (
                data.get("props", {})
                .get("pageProps", {})
                .get("searchResult", {})
                .get("advertSummaryList", {})
                .get("advertSummary")
                or []
            )
            for ad in ads:
                ad_id = str(ad.get("id") or "")
                if not ad_id or ad_id in seen:
                    continue
                seen.add(ad_id)
                attrs = _willhaben_attrs(ad)
                seo = attrs.get("SEO_URL") or ""
                url = (
                    f"https://www.willhaben.at/iad/{seo.lstrip('/')}"
                    if seo
                    else f"https://www.willhaben.at/iad/object?adId={ad_id}"
                )
                km_raw = attrs.get("MILEAGE") or ""
                km = f"{int(km_raw):,}".replace(",", ".") + " km" if km_raw.isdigit() else km_raw
                out.append(
                    listing(
                        ad_id=ad_id,
                        title=attrs.get("HEADING") or ad.get("description") or f"willhaben {ad_id}",
                        url=url,
                        price=attrs.get("PRICE_FOR_DISPLAY") or attrs.get("PRICE") or "",
                        year=attrs.get("YEAR_MODEL") or "",
                        km=km,
                        extra=attrs.get("LOCATION") or "",
                    )
                )
            if out:
                return out
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    for link in soup.select("a[href*='/iad/gebrauchtwagen/d/auto/']"):
        href = link.get("href") or ""
        m = re.search(r"/iad/gebrauchtwagen/d/auto/[^\"']+-(\d+)/?", href)
        if not m or m.group(1) in seen:
            continue
        ad_id = m.group(1)
        seen.add(ad_id)
        title = clean(link.get_text(" "))
        if len(title) < 8:
            continue
        out.append(
            listing(
                ad_id=ad_id,
                title=title,
                url=urljoin("https://www.willhaben.at", href.split("?")[0]),
            )
        )
    return out


def parse_njuskalo(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict[str, str]] = []
    seen: set[str] = set()

    for article in soup.find_all("article"):
        parent = article.parent
        parent_classes = " ".join(parent.get("class", []) if parent else [])
        if "EntityList-item--FeaturedStore" in parent_classes:
            continue
        if "EntityList-item--Latest" in parent_classes:
            continue
        if "EntityList-item--banner" in parent_classes:
            continue

        link = article.find("a", href=re.compile(r"oglas-\d+"))
        if not link:
            continue
        href = link.get("href") or ""
        m = re.search(r"oglas-(\d+)", href)
        if not m or m.group(1) in seen:
            continue
        ad_id = m.group(1)
        seen.add(ad_id)

        url = href if href.startswith("http") else "https://www.njuskalo.hr" + href
        title = clean(link.get_text(" "))
        price_el = article.find(class_="price--hrk") or article.find(class_="price")
        price = clean(price_el.get_text(" ") if price_el else "")

        year = ""
        km = ""
        desc = article.find(class_="entity-description-main") or article.find(
            class_="entity-description"
        )
        desc_text = clean(desc.get_text(" ") if desc else article.get_text(" "))
        y_m = re.search(r"\b(20\d{2})\b", desc_text)
        if y_m:
            year = y_m.group(1)
        km_m = re.search(r"(\d[\d.\s]*)\s*km", desc_text, re.I)
        if km_m:
            km = clean(km_m.group(0))

        out.append(
            listing(
                ad_id=ad_id,
                title=title or f"Njuškalo oglas {ad_id}",
                url=url,
                price=price,
                year=year,
                km=km,
            )
        )
    return out


def parse_index_html(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("a[href*='/oglasi/auto-moto/'][href*='/oglas/']"):
        href = link.get("href") or ""
        m = re.search(r"/oglas/([^/]+)/(\d+)", href)
        if not m or m.group(2) in seen:
            continue
        ad_id = m.group(2)
        seen.add(ad_id)
        title = clean(link.get_text(" "))
        if len(title) < 6:
            title = m.group(1).replace("-", " ")
        url = href if href.startswith("http") else "https://www.index.hr" + href
        out.append(listing(ad_id=ad_id, title=title, url=url.split("?")[0]))
    return out


def parse_index_api(payload: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for ad in payload.get("data") or []:
        code = ad.get("code")
        if code is None:
            continue
        smart = ad.get("smartLink") or "oglas"
        summary = ad.get("summary") or {}
        year = ""
        make_year = summary.get("makeYear") or ""
        if isinstance(make_year, str) and len(make_year) >= 4:
            year = make_year[:4]
        km = ""
        mileage = summary.get("mileage")
        if isinstance(mileage, (int, float)):
            km = f"{int(mileage):,}".replace(",", ".") + " km"
        price = ad.get("price")
        price_s = f"{int(price):,}".replace(",", ".") + " €" if isinstance(price, (int, float)) else ""
        out.append(
            listing(
                ad_id=str(code),
                title=ad.get("title") or f"Index oglas {code}",
                url=f"https://www.index.hr/oglasi/auto-moto/osobni-automobili/oglas/{smart}/{code}",
                price=price_s,
                year=year,
                km=km,
            )
        )
    return out


# ---------------------------------------------------------------------------
# FlareSolverr (GitHub Actions Cloudflare bypass for Avto.net)
# ---------------------------------------------------------------------------

def flaresolverr_base() -> str:
    return os.environ.get("FLARESOLVERR_URL", "").strip().rstrip("/")


def flaresolverr_post(payload: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
    base = flaresolverr_base()
    if not base:
        raise RuntimeError("FLARESOLVERR_URL is not set")
    resp = requests.post(f"{base}/v1", json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "ok":
        raise RuntimeError(data.get("message") or str(data)[:300])
    return data


def flaresolverr_create_session() -> str | None:
    try:
        data = flaresolverr_post({"cmd": "sessions.create"}, timeout=60)
        session = data.get("session")
        print(f"  [i] FlareSolverr session {session}")
        return session
    except Exception as exc:
        print(f"  [!] FlareSolverr session.create failed: {exc}")
        return None


def flaresolverr_destroy_session(session: str | None) -> None:
    if not session:
        return
    try:
        flaresolverr_post({"cmd": "sessions.destroy", "session": session}, timeout=30)
    except Exception:
        pass


def flaresolverr_get_html(url: str, session: str | None = None) -> str:
    payload: dict[str, Any] = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": 90_000,
    }
    if session:
        payload["session"] = session
    data = flaresolverr_post(payload, timeout=120)
    html = (data.get("solution") or {}).get("response") or ""
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = clean(title_m.group(1)) if title_m else ""
    if looks_blocked(html, title):
        raise RuntimeError(f"FlareSolverr still blocked ({title!r}, {len(html)} bytes)")
    if len(html) < 2000:
        raise RuntimeError(f"FlareSolverr short response ({title!r}, {len(html)} bytes)")
    return html


def scrape_avto_via_flaresolverr(search: dict, session: str | None) -> list[dict[str, str]]:
    html = flaresolverr_get_html(search["url"], session)
    ads = parse_avto(html)
    if not ads:
        raise RuntimeError(f"0 listings parsed from FlareSolverr HTML ({len(html)} bytes)")
    return ads


# ---------------------------------------------------------------------------
# Browser
# ---------------------------------------------------------------------------

def accept_cookies(page) -> None:
    for sel in COOKIE_SELECTORS:
        try:
            loc = page.locator(sel)
            if loc.count() and loc.first.is_visible():
                loc.first.click(timeout=2500)
                page.wait_for_timeout(600)
                return
        except Exception:
            continue


def launch_browser(playwright):
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-infobars",
    ]
    try:
        return playwright.chromium.launch(headless=True, args=args)
    except Exception as exc:
        print(f"  [i] bundled Chromium missing ({exc}); trying system Chrome")
        return playwright.chromium.launch(channel="chrome", headless=True, args=args)


def new_page(browser, locale: str = "hr-HR"):
    context = browser.new_context(
        user_agent=USER_AGENT,
        locale=locale,
        viewport={"width": 1366, "height": 900},
    )
    page = context.new_page()
    try:
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
    except Exception:
        pass
    return context, page


def scrape_search(page, search: dict) -> list[dict[str, str]]:
    site = search["site"]
    url = search["url"]
    api_payload: dict[str, Any] | None = None

    def on_response(response) -> None:
        nonlocal api_payload
        if site != "index":
            return
        if "/oglasi/api/aditem?" not in response.url:
            return
        if response.status != 200:
            return
        try:
            api_payload = response.json()
        except Exception:
            pass

    page.on("response", on_response)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=BROWSER_TIMEOUT_MS)
        page.wait_for_timeout(1200)
        accept_cookies(page)

        title = ""
        try:
            title = page.title()
        except Exception:
            pass
        if looks_blocked("", title):
            print(f"    [i] challenge page ({title!r}), waiting")
            wait_out_challenge(page, site)

        try:
            page.evaluate("window.scrollTo(0, 700)")
            page.wait_for_timeout(700)
        except Exception:
            pass

        if site == "index":
            page.wait_for_timeout(3500)

        html = page.content()
        title = page.title()
        if looks_blocked(html, title):
            raise RuntimeError(f"blocked/captcha ({title!r}, {len(html)} bytes)")

        if site == "avto":
            ads = parse_avto(html)
        elif site == "willhaben":
            ads = parse_willhaben(html)
        elif site == "njuskalo":
            ads = parse_njuskalo(html)
        elif site == "index":
            ads = parse_index_api(api_payload) if api_payload else []
            if not ads:
                ads = parse_index_html(html)
        else:
            raise RuntimeError(f"unknown site {site}")

        if not ads:
            raise RuntimeError(f"0 listings parsed ({title!r}, {len(html)} bytes)")
        return ads
    finally:
        try:
            page.remove_listener("response", on_response)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def telegram_chats() -> list[str]:
    raw = os.environ.get("TELEGRAM_CHAT_ID", "")
    return [part.strip() for part in re.split(r"[,;\s]+", raw) if part.strip()]


def telegram_ready() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and telegram_chats())


def format_message(search_name: str, ad: dict[str, str]) -> str:
    bits = [html_lib.escape(ad["title"])]
    if ad.get("price"):
        bits.append(html_lib.escape(ad["price"]))
    meta = " · ".join(html_lib.escape(x) for x in (ad.get("year"), ad.get("km")) if x)
    if meta:
        bits.append(meta)
    if ad.get("extra"):
        bits.append(html_lib.escape(ad["extra"]))
    body = "\n".join(bits)
    return (
        f"🆕 <b>Novi oglas</b>\n"
        f"{html_lib.escape(search_name)}\n\n"
        f"{body}\n"
        f"{ad['url']}"
    )


def send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    for chat_id in telegram_chats():
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=30,
        )
        if not resp.ok:
            print(f"  [!] Telegram {chat_id}: {resp.status_code} {resp.text[:200]}")
            resp.raise_for_status()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    load_dotenv()
    dry_run = "--dry-run" in sys.argv
    send_existing = "--send-existing" in sys.argv
    sites = selected_sites()
    searches = load_json(SEARCHES_PATH, [])
    if sites:
        searches = [s for s in searches if s.get("site") in sites]
        print(f"[i] sites filter: {', '.join(sorted(sites))}")
    seen_file = seen_path()
    seen: dict[str, list[str]] = load_json(seen_file, {})
    found_new = 0
    sent = 0
    failures: list[str] = []

    if not searches:
        print("searches.json is empty (or SITES filter matched nothing)")
        return 1

    from playwright.sync_api import sync_playwright

    fs_session = flaresolverr_create_session() if flaresolverr_base() else None

    with sync_playwright() as p:
        browser = launch_browser(p)
        context, page = new_page(browser)

        try:
            for idx, search in enumerate(searches):
                sid = search["id"]
                name = search["name"]
                print(f"\n[{name}]")
                print(f"  URL: {search['url'][:110]}...")

                ads: list[dict[str, str]] = []
                try:
                    if search["site"] == "avto" and flaresolverr_base():
                        print("  [i] fetching Avto.net via FlareSolverr")
                        ads = scrape_avto_via_flaresolverr(search, fs_session)
                    else:
                        ads = scrape_search(page, search)
                except Exception as exc:
                    print(f"  [!] scrape failed: {exc}")
                    failures.append(name)
                    continue

                ids = [ad["id"] for ad in ads]
                print(f"  [i] {len(ads)} listings")
                for ad in ads[:5]:
                    print(f"      - {ad['id']} {ad['title'][:70]}")

                first_time = sid not in seen and not send_existing
                known = set(seen.get(sid, []))

                if first_time:
                    seen[sid] = ids
                    print(f"  [i] first run — seeded {len(ids)} ids, no Telegram")
                else:
                    new_ads = [ad for ad in ads if ad["id"] not in known]
                    print(f"  [i] {len(new_ads)} new")
                    for ad in new_ads:
                        found_new += 1
                        known.add(ad["id"])
                        print(f"  new: {ad['title'][:70]} {ad['url']}")
                        if dry_run:
                            continue
                        if not telegram_ready():
                            print("  [!] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — skip send")
                            continue
                        if sent >= MAX_ALERTS_PER_RUN:
                            print("  [!] hit MAX_ALERTS_PER_RUN, remaining ads stored as seen")
                            continue
                        try:
                            send_telegram(format_message(name, ad))
                            sent += 1
                            time.sleep(0.8)
                        except Exception as exc:
                            print(f"  [!] telegram failed: {exc}")
                    seen[sid] = sorted(known | set(ids))

                if idx < len(searches) - 1:
                    time.sleep(DELAY_BETWEEN_SEARCHES)
        finally:
            browser.close()
            flaresolverr_destroy_session(fs_session)

    save_json(seen_file, seen)
    print(f"\nDone. New: {found_new}, sent: {sent}, failures: {len(failures)}")
    if failures:
        print("Failed searches:", ", ".join(failures))
        # Partial failure is OK — seen file for successful searches is saved.
        # Exit 0 so GitHub still commits seen.json. Full-fail only if everything died.
        if len(failures) == len(searches):
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
