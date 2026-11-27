"""Who is calling. Without auth every call is the single local user."""

LOCAL_SUBJECT = "local"


def current_subject() -> str:
    """The caller's identity as the auth provider names it (`users.external_id`).

    Local mode has no auth, so it is always "local". Production auth (phase 8) will read it
    from the validated token here; nothing else in the code knows how a caller is identified.
    """
    return LOCAL_SUBJECT
