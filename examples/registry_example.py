"""An example registry: three sources, one real and two shapes to copy.

Run it:

    python -m report_collector check --registry examples/registry_example.py
    python -m report_collector run   --registry examples/registry_example.py \
        --archive ./archive --year 2026
    python -m report_collector run   --registry examples/registry_example.py \
        --archive ./archive --year 2026          # second run: downloaded must be 0
    python -m report_collector audit --archive ./archive

Only the first source below is a real publication whose landing page and link pattern were
checked (2026-09-20). The other two use example.org on purpose: they are here to show the
shape of a TEMPLATE source and of a MANUAL source, not to assert anything about a publisher.
Replace them with your own before running anything that matters.
"""
from report_collector import Cadence, Source, Tier

SOURCES = [
    # --- a real, irregular publication ------------------------------------------------
    # The ECB Economic Bulletin appears eight times a year, so it gets no expected months:
    # WINDOW collects what is published and files each issue under the month its link names.
    # Issue PDFs live at /pub/pdf/ecbu/eb<year><issue>.en.pdf, and the landing page's link
    # text carries the publication date ("6 August 2026 Economic Bulletin Issue 5, 2026").
    Source(
        key="ecb-eb",
        name="Economic Bulletin",
        publisher="European Central Bank",
        tier=Tier.SCRAPE,
        cadence=Cadence.WINDOW,
        landing_url="https://www.ecb.europa.eu/press/economic-bulletin/html/index.en.html",
        allowed_hosts=("ecb.europa.eu",),
        extensions=(".pdf",),
        link_patterns=(r"/pub/pdf/ecbu/eb\d{6}\.en\.pdf",),
        edition_tokens=("{year}",),
        year_window=1,
        notes="Eight issues a year; the statistical annex is a separate PDF.",
    ),

    # --- shape: a URL that can be built from the period --------------------------------
    # Use TEMPLATE when the address is predictable. It costs one request per issue and no
    # landing-page parsing, so it is the cheapest and the least fragile tier - but check that
    # the publisher really does keep old issues at their original addresses.
    Source(
        key="example-monthly",
        name="Monthly Market Report",
        publisher="Example Institute",
        tier=Tier.TEMPLATE,
        cadence=Cadence.MONTHLY,
        url_template="https://reports.example.org/{year}/market-report-{month:02d}.pdf",
        allowed_hosts=("example.org",),
        extensions=(".pdf",),
        notes="Illustrative only - example.org publishes nothing.",
    ),

    # --- shape: something a person has to fetch ----------------------------------------
    # A source behind a login, a form or a paywall is declared, not omitted. The manifest then
    # asks for it every quarter, and a file dropped into the month folder closes the row.
    # The reason is part of the declaration: "it didn't work" is not a reason.
    Source(
        key="example-members",
        name="Members' Survey",
        publisher="Example Trade Body",
        tier=Tier.MANUAL,
        cadence=Cadence.QUARTERLY,
        months=(1, 4, 7, 10),
        manual_reason="member login required; credentials do not belong in a registry",
        notes="Illustrative only.",
    ),
]
