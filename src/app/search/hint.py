"""The sentence that tells the host what to do after `search_jobs`."""


def search_next_step(to_screen: int, over_cap: int, carried_over: int = 0) -> str:
    if not to_screen:
        return "No new jobs since the last search."
    hint = "Call screen_batch with this run_id until nothing remains."
    if carried_over:
        hint += f" {carried_over} of them were left unscreened by an earlier search."
    if over_cap:
        # They were not discarded: a later search picks them up, which the user cannot guess.
        hint += (
            f" {over_cap} more new jobs did not fit in this batch; after the shortlist, "
            "offer to call search_jobs again to screen them."
        )
    return hint
