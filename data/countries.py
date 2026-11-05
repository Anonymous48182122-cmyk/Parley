"""
Which country a company belongs to, for the flag shown beside it.

Three sources agree on one two letter ISO code (the same codes the flag images are named by):
- a Yahoo symbol's suffix names the exchange it trades on (7203.T is Tokyo, SAP.DE is Xetra);
- Nasdaq's stock list gives every US listed company's home country by name ("Taiwan", "Ireland"), so
  TSMC on the NYSE carries Taiwan's flag and not the American one;
- the Indian and plain US lists are IN and US.
"""

COUNTRY_NAMES = {
    "US": "United States", "IN": "India", "GB": "United Kingdom", "DE": "Germany", "FR": "France", "NL": "Netherlands",
    "IT": "Italy", "ES": "Spain", "PT": "Portugal", "BE": "Belgium", "AT": "Austria", "CH": "Switzerland",
    "SE": "Sweden", "DK": "Denmark", "NO": "Norway", "FI": "Finland", "IS": "Iceland", "IE": "Ireland",
    "PL": "Poland", "CZ": "Czechia", "HU": "Hungary", "GR": "Greece", "TR": "Turkey", "IL": "Israel",
    "SA": "Saudi Arabia", "QA": "Qatar", "AE": "United Arab Emirates", "EG": "Egypt", "ZA": "South Africa",
    "JP": "Japan", "CN": "China", "HK": "Hong Kong", "KR": "South Korea", "TW": "Taiwan", "SG": "Singapore",
    "AU": "Australia", "NZ": "New Zealand", "CA": "Canada", "BR": "Brazil", "MX": "Mexico", "AR": "Argentina",
    "CL": "Chile", "CO": "Colombia", "PE": "Peru", "ID": "Indonesia", "TH": "Thailand", "MY": "Malaysia",
    "PH": "Philippines", "VN": "Vietnam", "LU": "Luxembourg", "BM": "Bermuda", "KY": "Cayman Islands",
    "VG": "British Virgin Islands", "JE": "Jersey", "GG": "Guernsey", "MH": "Marshall Islands", "MC": "Monaco",
    "PA": "Panama", "PR": "Puerto Rico", "RU": "Russia", "UA": "Ukraine", "KZ": "Kazakhstan", "CY": "Cyprus",
    "MT": "Malta", "NG": "Nigeria", "KE": "Kenya", "PK": "Pakistan", "BD": "Bangladesh", "LK": "Sri Lanka",
    "UY": "Uruguay", "GI": "Gibraltar", "CR": "Costa Rica", "VI": "U.S. Virgin Islands", "KH": "Cambodia",
    "JO": "Jordan", "IM": "Isle of Man", "CW": "Curacao", "BS": "Bahamas",
}

# Yahoo exchange suffix -> country. A suffix is only trusted when it is in this list, which is what
# keeps US share classes (BRK.B, BF.B) from being read as an exchange.
SUFFIX_COUNTRY = {
    "NS": "IN", "BO": "IN",
    "L": "GB", "IL": "GB",
    "DE": "DE", "F": "DE", "BE": "DE", "DU": "DE", "HM": "DE", "MU": "DE", "SG": "DE", "HA": "DE",
    "PA": "FR", "AS": "NL", "MI": "IT", "MC": "ES", "LS": "PT", "BR": "BE", "VI": "AT", "SW": "CH",
    "ST": "SE", "CO": "DK", "OL": "NO", "HE": "FI", "IC": "IS", "IR": "IE", "WA": "PL", "PR": "CZ",
    "BD": "HU", "AT": "GR", "IS": "TR", "TA": "IL", "SR": "SA", "QA": "QA", "CA": "EG", "JO": "ZA",
    "T": "JP", "HK": "HK", "SS": "CN", "SZ": "CN", "KS": "KR", "KQ": "KR", "TW": "TW", "TWO": "TW",
    "SI": "SG", "AX": "AU", "NZ": "NZ", "TO": "CA", "V": "CA", "NE": "CA", "CN": "CA",
    "SA": "BR", "MX": "MX", "BA": "AR", "SN": "CL", "JK": "ID", "BK": "TH", "KL": "MY", "PS": "PH", "VN": "VN",
}

# Nasdaq's country names -> ISO
_NAME_TO_ISO = {name.lower(): iso for iso, name in COUNTRY_NAMES.items()}
_NAME_TO_ISO.update({
    "united states": "US", "usa": "US", "korea": "KR", "republic of korea": "KR", "south korea": "KR",
    "uk": "GB", "united kingdom": "GB", "great britain": "GB", "england": "GB", "hong kong sar": "HK",
    "china mainland": "CN", "macau": "HK", "cayman": "KY", "bvi": "VG", "the netherlands": "NL",
    "holland": "NL", "uae": "AE", "russian federation": "RU", "czech republic": "CZ", "turkiye": "TR",
})

# Currencies quoted in a fraction of the main unit; the price is divided by this to get the main unit
SUBUNIT_CURRENCIES = {"GBp": ("GBP", 100), "GBX": ("GBP", 100), "ZAc": ("ZAR", 100), "ZAC": ("ZAR", 100), "ILA": ("ILS", 100)}


def iso_from_name(name):
    """ISO code for a country named in words ("Taiwan"); None when it is not recognised."""
    if not name:
        return None
    return _NAME_TO_ISO.get(str(name).strip().lower())


def suffix_of(symbol):
    """The exchange suffix of a Yahoo symbol if it is a known one ("7203.T" -> "T"), else None."""
    if not symbol or "." not in symbol:
        return None
    suffix = symbol.rsplit(".", 1)[1].upper()
    return suffix if suffix in SUFFIX_COUNTRY else None


def is_global_symbol(symbol):
    """True for a symbol on a non US, non Indian exchange (7203.T, SAP.DE, 0700.HK), where US class
    shares like BRK.B are not mistaken for one."""
    s = suffix_of(symbol)
    return bool(s) and SUFFIX_COUNTRY[s] not in ("IN",)


def country_of_symbol(symbol):
    """The country of the exchange a Yahoo symbol trades on; US when it has no exchange suffix."""
    s = suffix_of(symbol)
    return SUFFIX_COUNTRY[s] if s else "US"


def country_name(iso):
    return COUNTRY_NAMES.get((iso or "").upper())
