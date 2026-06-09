class FxConverter:
    def __init__(self, rates: dict[str, float]) -> None:
        self.rates = {key.upper(): value for key, value in rates.items()}

    def to_jpy(self, amount: float | None, currency: str | None) -> float | None:
        if amount is None or currency is None:
            return None
        normalized_currency = currency.upper()
        if normalized_currency == "JPY":
            return amount
        rate = self.rates.get(normalized_currency)
        if rate is None:
            return None
        return amount * rate

    def set_rate(self, currency: str, rate: float) -> None:
        self.rates[currency.upper()] = rate
