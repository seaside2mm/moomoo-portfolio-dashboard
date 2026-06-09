import re
from datetime import datetime


def parse_option_contract(contract_code: str) -> dict[str, object]:
    normalized = contract_code.split(".")[-1]
    match = re.fullmatch(
        r"(?P<underlying>[A-Z]+)(?P<expiry>\d{6})(?P<option_flag>[CP])(?P<strike>\d+)",
        normalized,
    )
    if not match:
        raise ValueError(f"unsupported option contract format: {contract_code}")
    underlying = match.group("underlying")
    expiry_token = match.group("expiry")
    option_flag = match.group("option_flag")
    strike_token = match.group("strike")
    option_type = "CALL" if option_flag == "C" else "PUT"
    expiry = datetime.strptime(expiry_token, "%y%m%d").date()
    strike = int(strike_token) / 1000
    return {
        "underlying": underlying,
        "expiry": expiry,
        "option_type": option_type,
        "strike": strike,
    }
