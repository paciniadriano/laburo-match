"""Places the eligibility rules can resolve: countries, regions and ambiguous terms.

First name of each country is the one shown to people; the others are spellings that postings
use. Extending a list never changes how a job is judged unless the new name appears in it: a
place that is not here resolves to "unknown", which can only make a job `doubtful`.
"""

# ISO 3166-1 alpha-2 -> names (English display name first).
COUNTRIES: dict[str, tuple[str, ...]] = {
    "AR": ("Argentina",),
    "BO": ("Bolivia",),
    "BR": ("Brazil", "Brasil"),
    "CL": ("Chile",),
    "CO": ("Colombia",),
    "CR": ("Costa Rica",),
    "CU": ("Cuba",),
    "DO": ("Dominican Republic", "Republica Dominicana"),
    "EC": ("Ecuador",),
    "SV": ("El Salvador",),
    "GT": ("Guatemala",),
    "HN": ("Honduras",),
    "MX": ("Mexico",),
    "NI": ("Nicaragua",),
    "PA": ("Panama",),
    "PY": ("Paraguay",),
    "PE": ("Peru",),
    "UY": ("Uruguay",),
    "VE": ("Venezuela",),
    "US": (
        "United States",
        "United States of America",
        "USA",
        "US",
        "U.S.",
        "U.S.A.",
        "Estados Unidos",
        "EEUU",
        "EE.UU.",
    ),  # fmt: skip
    "CA": ("Canada",),
    "GB": ("United Kingdom", "UK", "Great Britain", "Reino Unido"),
    "ES": ("Spain", "Espana"),
    "PT": ("Portugal",),
    "DE": ("Germany", "Alemania"),
    "FR": ("France", "Francia"),
    "IT": ("Italy", "Italia"),
    "NL": ("Netherlands", "Holland", "Paises Bajos"),
    "IE": ("Ireland", "Irlanda"),
    "PL": ("Poland", "Polonia"),
    "CH": ("Switzerland", "Suiza"),
    "AU": ("Australia",),
    "IN": ("India",),
}

_LATAM = "AR BO BR CL CO CR CU DO EC SV GT HN MX NI PA PY PE UY VE".split()
_EU = "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split()
_SOUTH_AMERICA = "AR BO BR CL CO EC GY PY PE SR UY VE".split()

REGIONS: dict[str, frozenset[str]] = {
    "LATAM": frozenset(_LATAM),
    "EU": frozenset(_EU),
    "SOUTH_AMERICA": frozenset(_SOUTH_AMERICA),
}
REGION_NAMES: dict[str, tuple[str, ...]] = {
    "LATAM": ("LATAM", "Latin America", "Latinoamerica", "America Latina"),
    "EU": ("EU", "European Union", "Union Europea", "UE"),
    "SOUTH_AMERICA": ("South America", "Sudamerica", "America del Sur"),
}

# Terms that name no definite set of countries. A job open to "Worldwide" may still exclude
# yours; "Americas" may or may not include a given country. They can only mean `doubtful`.
AMBIGUOUS_TERMS = (
    "worldwide", "global", "anywhere", "everywhere", "international", "world",
    "americas", "emea", "apac", "remote", "remoto",
)  # fmt: skip

# Payroll phrases that only make sense for someone who can be paid through the US system.
# Ordinary contract types ("contractor", "prestacion de servicios") say nothing about where
# you may live, but these do. Phase 4 maps them to work-authorization requirements.
US_PAYROLL_MARKERS = ("w2", "w 2", "1099", "ssn", "social security")
