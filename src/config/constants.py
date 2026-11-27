"""Server-side constants: thresholds and limits that are not user settings."""

# Cards in the shortlist returned by the call that finishes a run.
SHORTLIST_SIZE = 10

# Posting text is cut here before it reaches the LLM (cost and prompt-injection surface).
JOB_TEXT_MAX_CHARS = 30_000

# Arbitrary app-wide number for the Postgres advisory lock that serializes container startup.
MIGRATION_LOCK_KEY = 727_001

# One model call must leave room inside a ~30 s tool call (hosts cut at 60 s; see CLAUDE.md).
LLM_REQUEST_TIMEOUT_SECONDS = 45
LLM_MAX_RETRIES = 2  # the SDK retries 429 and 5xx by itself

# One shared HTTP client for every outbound call (sources, later others).
HTTP_TIMEOUT_SECONDS = 10
HTTP_CONNECT_TIMEOUT_SECONDS = 5

# How long a search run stays usable by `screen_batch`.
RUN_TTL_HOURS = 24
# Jobs asked from a source per search; a whole category is ~300, ranked before the cap applies.
SEARCH_FETCH_LIMIT = 500

# A job is claimed at most this many times: the first try plus one retry (see `screen_batch`).
MAX_SCREEN_ATTEMPTS = 2

# How each source is named to the user. Get on Board's terms require showing it as the source.
SOURCE_LABELS = {
    "getonbrd": "Get on Board",
    "google_jobs": "Google Jobs",
    "pasted": "Pasted by you",
}

# Why the search prefilter left a job out, in words for the host to pass on.
PREFILTER_REASON_TEXT = {
    "closed": "The posting is closed.",
    "too_old": "Older than the maximum job age of your profile.",
    "office_abroad": "Hybrid or on-site, and every office is in another country.",
    "residence_abroad": "Remote, but only for people who live in other countries.",
    "duplicate": "Another posting of the same opening was kept.",
}

# Pages of `list_jobs`: small enough for the host's context, large enough to browse.
LIST_JOBS_MAX_LIMIT = 50
