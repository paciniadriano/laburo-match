"""Domain errors with a stable `error_code`.

Business code raises these and knows nothing about MCP. The router layer maps them to
`ToolError` in one place, so the host always sees the same shape: a stable code to react to
and a message that says what to do next. Messages are in English; the host translates them.
"""


class DomainError(Exception):
    """Base class. Subclasses set `error_code`; `message` is shown to the host."""

    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ProfileRequiredError(DomainError):
    error_code = "PROFILE_REQUIRED"

    def __init__(self) -> None:
        super().__init__(
            "The profile is not complete. Set up the profile before searching for jobs."
        )


class RunNotFoundError(DomainError):
    error_code = "RUN_NOT_FOUND"

    def __init__(self) -> None:
        super().__init__("Run not found. Use the run_id returned by search_jobs.")


class RunExpiredError(DomainError):
    error_code = "RUN_EXPIRED"

    def __init__(self) -> None:
        super().__init__("This run expired. Call search_jobs again to start a new one.")


class LLMOutputError(DomainError):
    error_code = "LLM_OUTPUT_INVALID"

    def __init__(self, task_name: str) -> None:
        super().__init__(
            f"The model could not produce a valid answer for task {task_name!r}. "
            "Try again; if it keeps failing, the item is reported as not processed."
        )
