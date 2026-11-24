"""Server-side constants: thresholds and limits that are not user settings."""

# Cards in the shortlist returned by the call that finishes a run.
SHORTLIST_SIZE = 10

# Posting text is cut here before it reaches the LLM (cost and prompt-injection surface).
JOB_TEXT_MAX_CHARS = 30_000

# Arbitrary app-wide number for the Postgres advisory lock that serializes container startup.
MIGRATION_LOCK_KEY = 727_001
