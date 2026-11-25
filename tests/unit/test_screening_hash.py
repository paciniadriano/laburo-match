from src.app.screening.screening_hash import screening_hash
from src.models.profile import Constraints


def _constraints(**changes) -> Constraints:
    base = {"country": "AR", "citizenships": ["AR", "ES"], "accepted_modalities": ["remote"]}
    return Constraints(**{**base, **changes})


def test_the_same_constraints_give_the_same_hash():
    assert screening_hash(_constraints()) == screening_hash(_constraints())


def test_the_order_of_a_list_does_not_change_the_hash():
    assert screening_hash(_constraints(citizenships=["AR", "ES"])) == screening_hash(
        _constraints(citizenships=["ES", "AR"])
    )


def test_a_different_country_changes_the_hash():
    assert screening_hash(_constraints(country="AR")) != screening_hash(_constraints(country="UY"))


def test_never_asked_is_not_the_same_as_confirmed_empty():
    never_asked = _constraints(work_authorizations=None)
    confirmed_none = _constraints(work_authorizations=[])

    assert screening_hash(never_asked) != screening_hash(confirmed_none)
