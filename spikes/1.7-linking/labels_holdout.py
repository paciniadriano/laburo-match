"""Hand labels for the held-out set (postings 05 and 12), written BEFORE any run on them.

Same conventions as labels.py. Profile and evidence are unchanged (Martina Sosa). Labels follow the
criteria fixed during the main set: `related` never gives `partial`; weak evidence (basic, coursework,
vague) is never enough for `met`; "consuming APIs" is an acceptable `met` for API integrations
(user decision on p04-r03); a requirement needing a thing the CV does not show is `partial` or `missing`.
"""

JOBS = ["E1", "E2", "E3", "E4"]


def L(level, strong=(), related=(), doubt="", also_ok=()):
    return dict(level=level, strong=list(strong), related=list(related), doubt=doubt, also_ok=list(also_ok))


LABELS_HOLDOUT: dict[str, dict] = {
    # --- 05 ---
    "p05-r01": L("met", strong=JOBS,
                 doubt="Which jobs are 'full-stack'? Pampa (React + Node + PostgreSQL) clearly; freelance and Delta "
                       "(PHP / ASP.NET + JS) arguably; Nimbus is frontend. Pampa + freelance + Delta alone give 5.9y"),
    "p05-r02": L("met", strong=["E6"], also_ok=["partial"],
                 doubt="Accepts deep TypeScript (4.7y, detailed) instead of Go, but 'proven ability to pick up Go fast' is not verifiable"),
    "p05-r03": L("met", strong=["E5", "E7"]),
    "p05-r04": L("missing"),  # nice to have; no React Native
    "p05-r05": L("missing"),  # webhooks / telephony / event-based systems: nothing in the CV
    "p05-r06": L(None),  # soft
    "p05-r07": L("met", strong=["E10"],
                 doubt="PostgreSQL / SQL at Pampa Fintech (live product); 'operating in production' is not written in the CV"),
    "p05-r08": L("met"),  # English C1
    "p05-r09": L(None),  # condition
    "p05-r10": L("missing"),  # nice to have; Telnyx / Twilio
    "p05-r11": L("missing"),  # nice to have; LLM-powered features
    # --- 12 ---
    "p12-r01": L("partial",
                 doubt="Python is 'coursework' (weak) and Django is absent. User decision before the run: `partial` "
                       "(conservative; the review stop asks about it)"),
    "p12-r02": L("partial", strong=["E10"]),  # PostgreSQL yes; schema changes on live systems not shown
    "p12-r03": L("missing"),  # Celery / RabbitMQ / Redis / background jobs: nothing
    "p12-r04": L("partial", strong=["E13"],
                 doubt="Consumed GraphQL APIs (accepted as integration, see p04-r03); 'knows what happens when they fail' not shown"),
    "p12-r05": L("met", strong=["E11", "E20"],
                 doubt="Unit and component testing (E11) and weekly code reviews (E20); 'code quality' is generic"),
    "p12-r06": L("missing"),  # monitoring / incidents / production support: nothing
    "p12-r07": L(None),  # soft
    "p12-r08": L("met"),  # English C1
    "p12-r09": L("missing"),  # nice to have; travel industry
    "p12-r10": L("met", strong=["E2"], also_ok=["partial"],
                 doubt="Pampa Fintech: 'onboarding and payments flows' (E2 note); no Stripe or invoicing mentioned"),
    "p12-r11": L("missing"),  # nice to have; AI-powered features
    "p12-r12": L("met", strong=["E14"]),  # nice to have; "Docker, Kubernetes or AWS": AWS S3/CloudFront is detailed
}
