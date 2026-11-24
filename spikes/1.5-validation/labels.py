"""Hand labels for spike 1.5, written BEFORE running any extraction.

Reference profile: Argentine citizen, resident in Argentina, no US work authorization.
`restrictions` lists only what constrains a candidate; `compatible` is for the reference profile.
`doubt` marks labels the human should review (None = confident).
"""
R = lambda kind, ev, quote, compatible: {"kind": kind, "evidence_kind": ev, "quotes": quote if isinstance(quote, list) else [quote], "compatible": compatible}

LABELS = {
 "01": dict(split="dev",  verdict="not_eligible", hidden=True,  doubt=None, restrictions=[
      R("location", "explicit", "Debes vivir en cualquier estado de USA (excluyente)", False)]),
 "02": dict(split="dev",  verdict="not_eligible", hidden=True,  doubt=None, restrictions=[
      R("location", "explicit", "Residencia actual en Colombia o Venezuela", False)]),
 "03": dict(split="test", verdict="not_eligible", hidden=True,  doubt=None, restrictions=[
      R("location", "explicit", "disponibilidad para trabajar remotamente desde Colombia", False)]),
 "04": dict(split="dev",  verdict="eligible",     hidden=True,  doubt="timezone", restrictions=[
      R("location", "explicit", "Remote within Latin America", True),
      R("timezone", "explicit", "At least five working hours of overlap with Pacific Time", "unknown")]),
 "05": dict(split="dev",  verdict="eligible",     hidden=True,  doubt="timezone", restrictions=[
      R("location", "explicit", "Based in Latin America", True),
      R("timezone", "explicit", "at least 6 hours of overlap with US Pacific time", "unknown")]),
 "06": dict(split="test", verdict="doubtful",     hidden=False, doubt=None, restrictions=[
      R("modality", "contradictory", ["Este rol es 100% remoto", "La modalidad híbrida que ofrecemos, ubicada en Las Condes"], "unknown")]),
 "07": dict(split="dev",  verdict="doubtful",     hidden=True,  doubt="visa", restrictions=[
      R("location", "explicit", "This is a remote role based in LATAM with required travel", True),
      R("visa", "explicit", "with a valid B1/B2 visa or ESTA eligibility already in place", "unknown")]),
 "08": dict(split="dev",  verdict="doubtful",     hidden=False, doubt="1099", restrictions=[
      R("payroll", "inferred", "1099 Contractor position", "unknown"),
      R("timezone", "explicit", "some overlap with U.S. Eastern Time", "unknown")]),
 "09": dict(split="test", verdict="eligible",     hidden=True,  doubt=None, restrictions=[
      R("location", "explicit", "Location: Remote — Latin America", True),
      R("timezone", "explicit", "some overlap with US Pacific Time", "unknown")]),
 "10": dict(split="dev",  verdict="eligible",     hidden=False, doubt=None, restrictions=[
      R("location", "explicit", "Fully remote. Work from anywhere", True),
      R("timezone", "explicit", "Daily overlap with US Eastern business hours", "unknown")]),
 "11": dict(split="dev",  verdict="doubtful",     hidden=False, doubt="remote_only", restrictions=[]),
 "12": dict(split="test", verdict="doubtful",     hidden=False, doubt="remote_only", restrictions=[]),
 "13": dict(split="dev",  verdict="eligible",     hidden=True,  doubt="timezone", restrictions=[
      R("location", "explicit", "100% remoto, desde cualquier país de Latinoamérica", True),
      R("timezone", "explicit", "Disponibilidad completa en horario de Ciudad de México, de 9:00 a 18:00", "unknown")]),
 "14": dict(split="dev",  verdict="not_eligible", hidden=False, doubt=None, restrictions=[
      R("modality", "explicit", "Trabajamos en un entorno híbrido que confía en tu autonomía", "unknown")]),
 "15": dict(split="test", verdict="not_eligible", hidden=False, doubt=None, restrictions=[
      R("location", "explicit", "Disponibilidad para trabajar en modalidad híbrida en nuestra oficina en Santiago", False)]),
}
