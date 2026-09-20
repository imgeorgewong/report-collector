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

## Development

Enable the sensitive-content check once per clone:

```
git config core.hooksPath .githooks
```

Every commit then runs `tools/check_sensitive.py`, which blocks office/data files,
employer-internal URLs and paths, GUIDs and credential-looking strings.
Before making the repository public, also run the full scan:

```
python3 tools/check_sensitive.py --all
```

## Related

[public-data-powerquery](https://github.com/imgeorgewong/public-data-powerquery) — Excel Power Query connectors for free official economic data.

## Author

Jingbo Wang ([@imgeorgewong](https://github.com/imgeorgewong)) · [imgeorgewong.github.io](https://imgeorgewong.github.io)

## License

MIT — see `LICENSE`.
