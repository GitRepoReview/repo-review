"""Every threshold the signals use. Tune here, nowhere else.

Windows are in days (6 months = 183, 12 months = 365, 18 months = 548).
Boundaries are inclusive on the better side: exactly at a green limit is green.
"""

# Liveness: age of the latest default-branch commit.
LIVENESS_GREEN_DAYS = 183
LIVENESS_AMBER_DAYS = 365

# Bus factor: top human author's share of commits in the sample, in percent.
BUS_FACTOR_MIN_COMMITS = 10
BUS_FACTOR_GREEN_BELOW_PCT = 50
BUS_FACTOR_AMBER_UP_TO_PCT = 80

# Responsiveness: median days to close, over issues closed in the window.
RESPONSIVENESS_WINDOW_DAYS = 90
RESPONSIVENESS_MIN_CLOSED = 3
RESPONSIVENESS_GREEN_DAYS = 30
RESPONSIVENESS_AMBER_DAYS = 90

# Releases: age of the latest non-draft release.
RELEASES_GREEN_DAYS = 183
RELEASES_AMBER_DAYS = 548

# License: SPDX ids that need no legal review. Everything else is amber
# (copyleft, NOASSERTION, unlisted); a missing license is red.
PERMISSIVE_LICENSES = frozenset(
    {
        "MIT",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "0BSD",
        "Unlicense",
        "Zlib",
    }
)
COPYLEFT_PREFIXES = ("GPL", "LGPL", "AGPL", "MPL", "EPL")
UNCLEAR_LICENSE = "NOASSERTION"

# Verdict: red / amber counts that move the traffic light.
VERDICT_HIGH_RED_COUNT = 2
VERDICT_MEDIUM_AMBER_COUNT = 2
