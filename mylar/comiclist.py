#  This file is part of Mylar.
#
#  Mylar is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Mylar is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Mylar.  If not, see <http://www.gnu.org/licenses/>.

"""
ComicList fallback source for the weekly pull-list.

locg.locg() uses this when the primary backend (walksoftly.itsaninja.party) is
unreachable or returns a non-200, so the weekly pull-list keeps working. It
scrapes ComicList (Charles LePage, https://comiclist.info), which is actively
published and aggregates the post-Diamond distributors (Lunar Distribution,
Penguin Random House, Manage Comics).

response(weeknumber, year) returns a small requests.Response-like object
(.status_code / .json()) carrying records in the exact shape locg.py already
consumes, so the calling code needs no other changes.

CURRENT WEEK vs UPCOMING WEEK
-----------------------------
ComicList publishes TWO lists around each New-Comic-Book-Day (Wednesday):

  * a FINAL list for the CURRENT week's Wednesday, posted ~2 days before it
      e.g. post 2026-06-08, title ".../for Wednesday, June 10, 2026"  (final)
  * a PRELIMINARY list for NEXT week's Wednesday, posted on the current Wednesday
      e.g. post 2026-06-10, title ".../for Wednesday, June 17, 2026"
      body: "This is the *preliminary* list and is not definitive."

We differentiate by (1) the post TITLE ship-date -> the Wednesday that list
covers, and (2) the word "preliminary" in the post body -> draft vs final.
Given mylar's (weeknumber, year), we compute the Wednesday of that %U week, pick
the post whose title ship-date == that Wednesday, and PREFER the final over the
preliminary. If no post matches the requested week we fall back to the newest
available list so the pull-list is never empty.
"""
import re
import html
import datetime
import urllib.request

try:
    import mylar
    from mylar import logger
except Exception:  # allows standalone testing outside the mylar package
    mylar = None
    logger = None

BASE = "https://comiclist.info"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


class _Resp:
    """Minimal stand-in for a requests.Response as locg.py uses it."""
    def __init__(self, data, status="200"):
        self.status_code = status
        self._data = data
        self.headers = {}

    def json(self):
        return self._data


def response(weeknumber, year):
    """Drop-in for the primary requests.get(). Never raises."""
    try:
        data = _fetch(int(weeknumber), int(year))
        return _Resp(data, "200") if data else _Resp([], "522")
    except Exception as e:
        if logger:
            logger.warn('[PULL-LIST][ComicList] fallback failed: %s' % (e,))
        return _Resp([], "522")


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def _wednesday_of_week(weeknumber, year):
    """The Wednesday whose strftime('%U') == weeknumber in `year` (mylar's scheme)."""
    d = datetime.date(year, 1, 1)
    d += datetime.timedelta(days=(2 - d.weekday()) % 7)  # first Wednesday (Mon=0..Wed=2)
    for _ in range(54):
        wk = int(d.strftime("%U"))
        if wk == weeknumber:
            return d
        if wk > weeknumber:
            break
        d += datetime.timedelta(days=7)
    return d  # best effort for odd boundaries


def _recent_post_urls():
    home = _get(BASE + "/")
    urls = []
    for m in re.finditer(r"/20\d{2}/\d{2}/\d{2}/[a-z0-9-]*new-comic[a-z0-9-]*\.html", home, re.I):
        u = BASE + m.group(0)
        if u not in urls:
            urls.append(u)
    return urls


def _is_publisher(line):
    # ComicList publisher headers are ALL-CAPS, priceless, short.
    if "$" in line or not line or any(c.islower() for c in line):
        return False
    return len(re.sub(r"[^A-Za-z]", "", line)) >= 2 and len(line) <= 60


def _parse_post(page):
    """Return (ship_date: date|None, is_preliminary: bool, records: list[(pub, series, issue)])."""
    page = re.sub(r"(?i)<\s*br\s*/?>", "\n", page)
    page = re.sub(r"(?i)</\s*(p|div|li|h[1-6])\s*>", "\n", page)
    page = html.unescape(re.sub(r"<[^>]+>", "", page))
    lines = [l.strip() for l in page.splitlines()]

    ship = None
    for l in lines:
        m = re.search(r"for\s+\w+,\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})", l)
        if m:
            ship = datetime.datetime.strptime(m.group(1), "%B %d, %Y").date()
            break
    is_preliminary = any("preliminary" in l.lower() for l in lines[:10])

    records, publisher = [], "UNKNOWN"
    for l in lines:
        if not l:
            continue
        if _is_publisher(l):
            publisher = l
            continue
        if "$" not in l:
            continue
        entry = re.sub(r"\(find on eBay\)\s*$", "", l).strip()
        mprice = re.search(r",\s*\$[0-9.]+\s*$", entry)
        if mprice:
            entry = entry[:mprice.start()].strip()
        if not entry:
            continue
        mi = re.search(r"#([0-9]+(?:\.[0-9]+)?)", entry)
        if mi:
            issue = mi.group(1)
            series = entry[:mi.start()].strip(" ,")
        else:
            issue = ""
            series = entry.strip(" ,")
        if series:
            records.append((publisher, series, issue))
    return ship, is_preliminary, records


def _fetch(weeknumber, year):
    target_wed = _wednesday_of_week(weeknumber, year)
    matches, newest = [], None  # matches: (is_preliminary, ship, records)
    for url in _recent_post_urls():
        ship, is_prelim, records = _parse_post(_get(url))
        if not records:
            continue
        if newest is None:
            newest = (ship, records)
        if ship == target_wed:
            matches.append((is_prelim, ship, records))

    if matches:
        matches.sort(key=lambda m: m[0])  # final (False) before preliminary (True)
        _, ship, records = matches[0]
    elif newest:
        ship, records = newest  # best-effort: newest available list
    else:
        return []

    if logger:
        logger.info('[PULL-LIST][ComicList] week %s -> %s (%s issues)'
                    % (weeknumber, ship, len(records)))

    shipdate = (ship or datetime.date.today()).strftime("%Y-%m-%d")
    out = []
    for publisher, series, issue in records:
        out.append({
            "series": series, "alias": None, "issue": issue,
            "publisher": publisher, "shipdate": shipdate, "coverdate": shipdate,
            "comicid": None, "issueid": None, "weeknumber": str(weeknumber),
            "link": "", "year": str(year), "volume": None, "seriesyear": None,
            "type": "comic",
        })
    return out
