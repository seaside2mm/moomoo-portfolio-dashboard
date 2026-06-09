from app.adapters.fx_converter import FxConverter


def test_fx_converter_returns_jpy_for_same_currency():
    converter = FxConverter({"JPY": 1.0, "USD": 150.0})
    assert converter.to_jpy(100, "JPY") == 100


def test_fx_converter_returns_none_when_rate_missing():
    converter = FxConverter({"JPY": 1.0})
    assert converter.to_jpy(100, "USD") is None
