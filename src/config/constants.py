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
