"""An example registry: one real source, plus two shapes kept as comments.

Run it:

    PYTHONPATH=src python -m report_collector check --registry examples/registry_example.py
    PYTHONPATH=src python -m report_collector run   --registry examples/registry_example.py \
        --archive ./archive --year 2026
    PYTHONPATH=src python -m report_collector run   --registry examples/registry_example.py \
        --archive ./archive --year 2026          # second run: downloaded must be 0
    PYTHONPATH=src python -m report_collector audit --archive ./archive

Only real, reachable sources are active below, so a run takes seconds rather than minutes
spent timing out against a placeholder host. The commented block at the end shows the two
other tiers.
"""
from report_collector import Cadence, Source, Tier

SOURCES = [
    # The ECB Economic Bulletin appears eight times a year, so it gets no expected months:
    # WINDOW collects what is published and files each issue under the month its link names
    # ("6 August 2026 Economic Bulletin Issue 5, 2026").
    #
    # The listing links to the HTML issue page, not to the PDF - the commonest shape there
    # is. Two ways out, and this registry declares both:
    #   * url_rewrite derives the PDF address from the page address, costing no extra request;
    #   * detail_page opens the issue page and looks for the document, used only if the
    #     rewrite does not land on a real PDF.
    # Checked 2026-09-20: robots.txt allows both paths; issue PDFs live at
    # /pub/pdf/ecbu/eb<year><issue>.en.pdf.
    Source(
        key="ecb-eb",
        name="Economic Bulletin",
        publisher="European Central Bank",
        tier=Tier.SCRAPE,
        cadence=Cadence.WINDOW,
        landing_url="https://www.ecb.europa.eu/press/economic-bulletin/html/index.en.html",
        allowed_hosts=("ecb.europa.eu",),
        extensions=(".pdf",),
        link_patterns=(r"/press/economic-bulletin/html/eb\d{6}\.en\.html",),
        url_rewrite=(r"/press/economic-bulletin/html/(eb\d{6})\.en\.html",
                     r"/pub/pdf/ecbu/\1.en.pdf"),
        detail_page=True,
        edition_tokens=("{year}",),
        year_window=1,
        notes="Eight issues a year; the statistical annex is a separate PDF.",
    ),
]

# --- the other two tiers, as shapes to copy -------------------------------------------
#
# TEMPLATE - the address can be built from the period. One request per issue, no landing
# page to parse: the cheapest and least fragile tier, when the publisher keeps old issues at
# their original addresses.
#
#     Source(
#         key="example-monthly",
#         name="Monthly Market Report",
#         publisher="Example Institute",
#         tier=Tier.TEMPLATE,
#         cadence=Cadence.MONTHLY,
#         url_template="https://reports.example.org/{year}/market-report-{month:02d}.pdf",
#         allowed_hosts=("example.org",),
#     )
#
# MANUAL - behind a login, a form or a paywall. Declared, not omitted: the manifest then asks
# for it every quarter, and a file dropped into the month folder closes the row. The reason
# is part of the declaration; "it didn't work" is not a reason.
#
#     Source(
#         key="example-members",
#         name="Members' Survey",
#         publisher="Example Trade Body",
#         tier=Tier.MANUAL,
#         cadence=Cadence.QUARTERLY,
#         months=(1, 4, 7, 10),
#         manual_reason="member login required; credentials do not belong in a registry",
#     )
