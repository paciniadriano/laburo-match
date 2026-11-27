from src.app.jobs.verify import verify_facts
from tests.factories import make_facts, make_restriction

POSTING = """We are hiring a frontend engineer.
Remote within Latin America. Candidates must be
US citizens. Send your CV to jobs@acme.io"""


def test_a_quote_that_appears_in_the_posting_is_kept():
    facts = make_facts(restrictions=[make_restriction(quotes=["Remote within Latin America"])])

    result = verify_facts(facts, POSTING)

    assert result.facts.restrictions[0].quotes == ["Remote within Latin America"]
    assert result.quotes_dropped == 0


def test_a_quote_spanning_a_line_break_still_matches():
    facts = make_facts(restrictions=[make_restriction(quotes=["Candidates must be US citizens"])])

    assert verify_facts(facts, POSTING).facts.restrictions[0].quotes != []


def test_an_invented_quote_is_dropped_and_the_restriction_loses_its_hard_verdict():
    facts = make_facts(restrictions=[make_restriction(quotes=["Only residents of Chile"])])

    result = verify_facts(facts, POSTING)

    restriction = result.facts.restrictions[0]
    assert restriction.quotes == []
    assert restriction.evidence_kind == "inferred"  # can only make the job doubtful now
    assert (result.quotes_dropped, result.restrictions_downgraded) == (1, 1)


def test_a_slightly_altered_quote_is_not_accepted():
    facts = make_facts(restrictions=[make_restriction(quotes=["Remote in Latin America"])])

    assert verify_facts(facts, POSTING).facts.restrictions[0].evidence_kind == "inferred"


def test_an_inferred_restriction_without_quotes_stays_inferred_and_is_not_counted():
    facts = make_facts(restrictions=[make_restriction(evidence_kind="inferred", quotes=[])])

    result = verify_facts(facts, POSTING)

    assert result.facts.restrictions[0].evidence_kind == "inferred"
    assert result.restrictions_downgraded == 0


def test_a_contradiction_needs_two_real_quotes():
    both = make_restriction(
        kind="modality",
        evidence_kind="contradictory",
        quotes=["Remote within Latin America", "Candidates must be US citizens"],
    )
    one_fake = both.model_copy(update={"quotes": ["Remote within Latin America", "Office in Lima"]})

    assert (
        verify_facts(make_facts(restrictions=[both]), POSTING).facts.restrictions[0].evidence_kind
        == "contradictory"
    )
    downgraded = verify_facts(make_facts(restrictions=[one_fake]), POSTING)
    assert downgraded.facts.restrictions[0].evidence_kind == "inferred"
    assert downgraded.facts.restrictions[0].quotes == ["Remote within Latin America"]


def test_an_email_in_the_posting_is_kept():
    result = verify_facts(make_facts(apply_email="jobs@acme.io"), POSTING)

    assert result.facts.apply_email == "jobs@acme.io"
    assert result.email_rejected is False


def test_an_email_not_in_the_posting_is_rejected():
    result = verify_facts(make_facts(apply_email="hr@other.com"), POSTING)

    assert result.facts.apply_email == ""
    assert result.email_rejected is True


def test_a_malformed_email_is_rejected_even_if_the_text_contains_it():
    result = verify_facts(make_facts(apply_email="not-an-email"), "write to not-an-email please")

    assert result.facts.apply_email == ""
    assert result.email_rejected is True


def test_no_email_is_not_a_rejection():
    assert verify_facts(make_facts(apply_email=""), POSTING).email_rejected is False
