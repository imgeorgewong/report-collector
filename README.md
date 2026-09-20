# report-collector

**English** | [中文](README.zh-CN.md)

A small, registry-driven Python framework for collecting publicly available reports
(economic outlooks, market reports, surveys) into a month-by-month archive, with a manifest
that records the status of every expected issue.

It is built for sources that behave badly: PDFs hidden behind article pages, URLs that are
overwritten in place, redirects that land on unrelated pages, archives that roll off a list,
and publications that are only available by hand.

> Status: work in progress.

## What it does

- **Registry, not code, per source.** Each source is a declaration: landing page, link patterns, cadence, allowed hosts.
- **Files by publication month**, not download date.
- **Manifest** with one row per expected issue: `downloaded`, `unchanged`, `manual`, `manual-done`, `missed`, `no-issue`, `future`, `absent`.
- **Guards against false positives**: redirected-away pages, duplicate content within a run, off-host links, stale evergreen URLs, wrong editions.
- **Manual sources are first-class**: anything that cannot or should not be automated becomes a to-do row, and a hand-downloaded file dropped into the month folder is picked up automatically.
- **Health check**: run twice — the second run must report `downloaded = 0`.
- **Polite by default**: honours `robots.txt`, rate-limits requests, keeps TLS verification on.

## What it is not

Not a tool for getting around logins, paywalls, forms or other access controls. Sources that need
them are recorded as manual rows. Downloaded reports remain the publishers' copyright and are
never part of this repository.

## Install

```
git clone https://github.com/imgeorgewong/report-collector.git
cd report-collector
git config core.hooksPath .githooks
```

Python 3.10 or later. No dependencies to install.

## Use

```
python -m report_collector check --registry examples/registry_example.py
python -m report_collector run   --registry examples/registry_example.py --archive ./archive --year 2026
python -m report_collector run   --registry examples/registry_example.py --archive ./archive --year 2026
python -m report_collector audit --archive ./archive
```

The second `run` is the acceptance test, not a typo: it must report `downloaded=0`. Anything
else means the de-duplication key is matching something volatile, and the collector will
re-download the same issues every month.

The archive looks like this:

```
archive/
  _manifest.csv
  2026/
    01_Jan/ acme__2026-01__Monthly-Outlook.pdf
    02_Feb/ ...
```

## Declaring a source

```python
from report_collector import Cadence, Source, Tier

Source(
    key="acme",                       # short id; also the filename prefix
    name="Monthly Outlook",
    publisher="Acme Institute",
    tier=Tier.SCRAPE,                 # TEMPLATE | SCRAPE | MANUAL
    cadence=Cadence.MONTHLY,          # MONTHLY | QUARTERLY | ANNUAL | WINDOW
    landing_url="https://acme.example/reports",
    allowed_hosts=("acme.example",),  # default deny - required for SCRAPE
    extensions=(".pdf",),
    edition_tokens=("{year}",),       # guards against an evergreen URL serving last year
    year_window=1,                    # how far back a landing page's links may go
)
```

`check` validates a registry without making a single request, so a declaration that cannot
work says so before anyone waits for a run.

## Statuses

| Status | Meaning |
|---|---|
| `downloaded` | new file written this run |
| `unchanged` | already archived, content identical |
| `manual` | a person has to fetch it - the reason is in the row |
| `manual-done` | a hand-downloaded file was found in the month folder |
| `missed` | due, looked for, not obtainable any more |
| `no-issue` | the publisher did not publish for this period |
| `future` | not due yet |
| `absent` | due, nothing matched: not published, rolled off the list, or the pattern is wrong |

`manual` and `missed` are deliberately separate: one is work a person can still do, the other
is a hole in the archive.

## Tests

```
python -m unittest discover -s tests
```

47 tests, all offline: the engine takes a fetcher object, and the tests pass one that serves
canned responses. Network behaviour (robots, pacing, retries) is the only thing not covered
that way.

## Related

[public-data-powerquery](https://github.com/imgeorgewong/public-data-powerquery) — Excel Power Query connectors for free official economic data.

## Author

Jingbo Wang ([@imgeorgewong](https://github.com/imgeorgewong)) · [imgeorgewong.github.io](https://imgeorgewong.github.io)

## License

MIT — see `LICENSE`.
