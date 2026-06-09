from app.adapters.option_parser import parse_option_contract


def test_parse_option_contract_reads_underlying_type_and_strike():
    parsed = parse_option_contract("US.NVDA260619P00150000")
    assert parsed["underlying"] == "NVDA"
    assert parsed["option_type"] == "PUT"
    assert parsed["strike"] == 150.0


def test_parse_option_contract_supports_shorter_live_opend_format():
    parsed = parse_option_contract("US.SOFI260618P15000")
    assert parsed["underlying"] == "SOFI"
    assert parsed["option_type"] == "PUT"
    assert parsed["strike"] == 15.0
