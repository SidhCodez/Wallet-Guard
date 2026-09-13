"""Small, deterministic currency-conversion helper."""

import pandas as pd


# The schema is detected lazily because importing this module must not read files
# or perform other work.  After the first lookup, all later lookups reuse it.
_RATE_SCHEMA: str | None = None


def _detect_rate_schema(rates_df: pd.DataFrame) -> str:
    """Return the supported currency-pair schema used by ``rates_df``."""
    columns = set(rates_df.columns)

    if {"from_currency", "to_currency"}.issubset(columns):
        return "separate_columns"
    if "currency_pair" in columns:
        return "currency_pair"

    raise ValueError(
        "rates_df must contain either 'currency_pair' or both "
        "'from_currency' and 'to_currency' columns"
    )


def convert(
    amount: float,
    from_ccy: str,
    to_ccy: str,
    date: str,
    rates_df: pd.DataFrame,
) -> float:
    """Convert ``amount`` using the fixed rate for a date and currency pair.

    Keeping conversion here, rather than calculating rates elsewhere, gives the
    rest of the pipeline one predictable place to apply the challenge's dated
    exchange-rate table.
    """
    # A same-currency conversion needs no rate lookup and must preserve the
    # amount exactly as requested by the challenge contract.
    if from_ccy == to_ccy:
        return amount

    global _RATE_SCHEMA
    if _RATE_SCHEMA is None:
        _RATE_SCHEMA = _detect_rate_schema(rates_df)

    # Compare dates as text because the loader intentionally leaves CSV values
    # unparsed, and the public function receives the date as a string.
    date_mask = rates_df["rate_date"].astype(str) == str(date)
    if _RATE_SCHEMA == "separate_columns":
        pair_mask = (
            (rates_df["from_currency"] == from_ccy)
            & (rates_df["to_currency"] == to_ccy)
        )
    else:
        pair_mask = rates_df["currency_pair"] == f"{from_ccy}_{to_ccy}"

    matching_rates = rates_df.loc[date_mask & pair_mask, "rate"]
    if matching_rates.empty:
        raise ValueError(f"No rate for {from_ccy}->{to_ccy} on {date}")

    return float(amount * matching_rates.iloc[0])


if __name__ == "__main__":
    # This block is only a tiny manual demonstration; importing the module does
    # not load the dataset or print anything.
    rates = pd.read_csv("../dataset/exchange_rates.csv")
    sample_date = str(rates.iloc[0]["rate_date"])

    # Same currency: this proves the input is returned without a table lookup.
    print("USD -> USD:", convert(100.0, "USD", "USD", sample_date, rates))

    # Existing pair: use the first row so this example works with either schema.
    first_row = rates.iloc[0]
    if "currency_pair" in rates.columns:
        sample_from, sample_to = str(first_row["currency_pair"]).split("_", 1)
    else:
        sample_from = str(first_row["from_currency"])
        sample_to = str(first_row["to_currency"])
    print(
        f"{sample_from} -> {sample_to}:",
        convert(1.0, sample_from, sample_to, sample_date, rates),
    )

    # Missing pair: the required ValueError is shown rather than hidden.
    try:
        convert(1.0, "ZZZ", "YYY", sample_date, rates)
    except ValueError as error:
        print("Missing pair:", error)
"""Small, deterministic currency-conversion helper."""

import pandas as pd


# The schema is detected lazily because importing this module must not read files
# or perform other work.  After the first lookup, all later lookups reuse it.
_RATE_SCHEMA: str | None = None


def _detect_rate_schema(rates_df: pd.DataFrame) -> str:
    """Return the supported currency-pair schema used by ``rates_df``."""
    columns = set(rates_df.columns)

    if {"from_currency", "to_currency"}.issubset(columns):
        return "separate_columns"
    if "currency_pair" in columns:
        return "currency_pair"

    raise ValueError(
        "rates_df must contain either 'currency_pair' or both "
        "'from_currency' and 'to_currency' columns"
    )


def convert(
    amount: float,
    from_ccy: str,
    to_ccy: str,
    date: str,
    rates_df: pd.DataFrame,
) -> float:
    """Convert ``amount`` using the fixed rate for a date and currency pair.

    Keeping conversion here, rather than calculating rates elsewhere, gives the
    rest of the pipeline one predictable place to apply the challenge's dated
    exchange-rate table.
    """
    # A same-currency conversion needs no rate lookup and must preserve the
    # amount exactly as requested by the challenge contract.
    if from_ccy == to_ccy:
        return amount

    global _RATE_SCHEMA
    if _RATE_SCHEMA is None:
        _RATE_SCHEMA = _detect_rate_schema(rates_df)

    # Compare dates as text because the loader intentionally leaves CSV values
    # unparsed, and the public function receives the date as a string.
    date_mask = rates_df["rate_date"].astype(str) == str(date)
    if _RATE_SCHEMA == "separate_columns":
        pair_mask = (
            (rates_df["from_currency"] == from_ccy)
            & (rates_df["to_currency"] == to_ccy)
        )
    else:
        pair_mask = rates_df["currency_pair"] == f"{from_ccy}_{to_ccy}"

    matching_rates = rates_df.loc[date_mask & pair_mask, "rate"]
    if matching_rates.empty:
        raise ValueError(f"No rate for {from_ccy}->{to_ccy} on {date}")

    return float(amount * matching_rates.iloc[0])


if __name__ == "__main__":
    # This block is only a tiny manual demonstration; importing the module does
    # not load the dataset or print anything.
    rates = pd.read_csv("../dataset/exchange_rates.csv")
    sample_date = str(rates.iloc[0]["rate_date"])

    # Same currency: this proves the input is returned without a table lookup.
    print("USD -> USD:", convert(100.0, "USD", "USD", sample_date, rates))

    # Existing pair: use the first row so this example works with either schema.
    first_row = rates.iloc[0]
    if "currency_pair" in rates.columns:
        sample_from, sample_to = str(first_row["currency_pair"]).split("_", 1)
    else:
        sample_from = str(first_row["from_currency"])
        sample_to = str(first_row["to_currency"])
    print(
        f"{sample_from} -> {sample_to}:",
        convert(1.0, sample_from, sample_to, sample_date, rates),
    )

    # Missing pair: the required ValueError is shown rather than hidden.
    try:
        convert(1.0, "ZZZ", "YYY", sample_date, rates)
    except ValueError as error:
        print("Missing pair:", error)
"""Small, deterministic currency-conversion helper."""

import pandas as pd


# The schema is detected lazily because importing this module must not read files
# or perform other work.  After the first lookup, all later lookups reuse it.
_RATE_SCHEMA: str | None = None


def _detect_rate_schema(rates_df: pd.DataFrame) -> str:
    """Return the supported currency-pair schema used by ``rates_df``."""
    columns = set(rates_df.columns)

    if {"from_currency", "to_currency"}.issubset(columns):
        return "separate_columns"
    if "currency_pair" in columns:
        return "currency_pair"

    raise ValueError(
        "rates_df must contain either 'currency_pair' or both "
        "'from_currency' and 'to_currency' columns"
    )


def convert(
    amount: float,
    from_ccy: str,
    to_ccy: str,
    date: str,
    rates_df: pd.DataFrame,
) -> float:
    """Convert ``amount`` using the fixed rate for a date and currency pair.

    Keeping conversion here, rather than calculating rates elsewhere, gives the
    rest of the pipeline one predictable place to apply the challenge's dated
    exchange-rate table.
    """
    # A same-currency conversion needs no rate lookup and must preserve the
    # amount exactly as requested by the challenge contract.
    if from_ccy == to_ccy:
        return amount

    global _RATE_SCHEMA
    if _RATE_SCHEMA is None:
        _RATE_SCHEMA = _detect_rate_schema(rates_df)

    # Compare dates as text because the loader intentionally leaves CSV values
    # unparsed, and the public function receives the date as a string.
    date_mask = rates_df["rate_date"].astype(str) == str(date)
    if _RATE_SCHEMA == "separate_columns":
        pair_mask = (
            (rates_df["from_currency"] == from_ccy)
            & (rates_df["to_currency"] == to_ccy)
        )
    else:
        pair_mask = rates_df["currency_pair"] == f"{from_ccy}_{to_ccy}"

    matching_rates = rates_df.loc[date_mask & pair_mask, "rate"]
    if matching_rates.empty:
        raise ValueError(f"No rate for {from_ccy}->{to_ccy} on {date}")

    return float(amount * matching_rates.iloc[0])


if __name__ == "__main__":
    # This block is only a tiny manual demonstration; importing the module does
    # not load the dataset or print anything.
    rates = pd.read_csv("../dataset/exchange_rates.csv")
    sample_date = str(rates.iloc[0]["rate_date"])

    # Same currency: this proves the input is returned without a table lookup.
    print("USD -> USD:", convert(100.0, "USD", "USD", sample_date, rates))

    # Existing pair: use the first row so this example works with either schema.
    first_row = rates.iloc[0]
    if "currency_pair" in rates.columns:
        sample_from, sample_to = str(first_row["currency_pair"]).split("_", 1)
    else:
        sample_from = str(first_row["from_currency"])
        sample_to = str(first_row["to_currency"])
    print(
        f"{sample_from} -> {sample_to}:",
        convert(1.0, sample_from, sample_to, sample_date, rates),
    )

    # Missing pair: the required ValueError is shown rather than hidden.
    try:
        convert(1.0, "ZZZ", "YYY", sample_date, rates)
    except ValueError as error:
        print("Missing pair:", error)
"""Small, deterministic currency-conversion helper."""

import pandas as pd


# The schema is detected lazily because importing this module must not read files
# or perform other work.  After the first lookup, all later lookups reuse it.
_RATE_SCHEMA: str | None = None


def _detect_rate_schema(rates_df: pd.DataFrame) -> str:
    """Return the supported currency-pair schema used by ``rates_df``."""
    columns = set(rates_df.columns)

    if {"from_currency", "to_currency"}.issubset(columns):
        return "separate_columns"
    if "currency_pair" in columns:
        return "currency_pair"

    raise ValueError(
        "rates_df must contain either 'currency_pair' or both "
        "'from_currency' and 'to_currency' columns"
    )


def convert(
    amount: float,
    from_ccy: str,
    to_ccy: str,
    date: str,
    rates_df: pd.DataFrame,
) -> float:
    """Convert ``amount`` using the fixed rate for a date and currency pair.

    Keeping conversion here, rather than calculating rates elsewhere, gives the
    rest of the pipeline one predictable place to apply the challenge's dated
    exchange-rate table.
    """
    # A same-currency conversion needs no rate lookup and must preserve the
    # amount exactly as requested by the challenge contract.
    if from_ccy == to_ccy:
        return amount

    global _RATE_SCHEMA
    if _RATE_SCHEMA is None:
        _RATE_SCHEMA = _detect_rate_schema(rates_df)

    # Compare dates as text because the loader intentionally leaves CSV values
    # unparsed, and the public function receives the date as a string.
    date_mask = rates_df["rate_date"].astype(str) == str(date)
    if _RATE_SCHEMA == "separate_columns":
        pair_mask = (
            (rates_df["from_currency"] == from_ccy)
            & (rates_df["to_currency"] == to_ccy)
        )
    else:
        pair_mask = rates_df["currency_pair"] == f"{from_ccy}_{to_ccy}"

    matching_rates = rates_df.loc[date_mask & pair_mask, "rate"]
    if matching_rates.empty:
        raise ValueError(f"No rate for {from_ccy}->{to_ccy} on {date}")

    return float(amount * matching_rates.iloc[0])


if __name__ == "__main__":
    # This block is only a tiny manual demonstration; importing the module does
    # not load the dataset or print anything.
    rates = pd.read_csv("../dataset/exchange_rates.csv")
    sample_date = str(rates.iloc[0]["rate_date"])

    # Same currency: this proves the input is returned without a table lookup.
    print("USD -> USD:", convert(100.0, "USD", "USD", sample_date, rates))

    # Existing pair: use the first row so this example works with either schema.
    first_row = rates.iloc[0]
    if "currency_pair" in rates.columns:
        sample_from, sample_to = str(first_row["currency_pair"]).split("_", 1)
    else:
        sample_from = str(first_row["from_currency"])
        sample_to = str(first_row["to_currency"])
    print(
        f"{sample_from} -> {sample_to}:",
        convert(1.0, sample_from, sample_to, sample_date, rates),
    )

    # Missing pair: the required ValueError is shown rather than hidden.
    try:
        convert(1.0, "ZZZ", "YYY", sample_date, rates)
    except ValueError as error:
        print("Missing pair:", error)
"""Small, deterministic currency-conversion helper."""

import pandas as pd


# The schema is detected lazily because importing this module must not read files
# or perform other work.  After the first lookup, all later lookups reuse it.
_RATE_SCHEMA: str | None = None


def _detect_rate_schema(rates_df: pd.DataFrame) -> str:
    """Return the supported currency-pair schema used by ``rates_df``."""
    columns = set(rates_df.columns)

    if {"from_currency", "to_currency"}.issubset(columns):
        return "separate_columns"
    if "currency_pair" in columns:
        return "currency_pair"

    raise ValueError(
        "rates_df must contain either 'currency_pair' or both "
        "'from_currency' and 'to_currency' columns"
    )


def convert(
    amount: float,
    from_ccy: str,
    to_ccy: str,
    date: str,
    rates_df: pd.DataFrame,
) -> float:
    """Convert ``amount`` using the fixed rate for a date and currency pair.

    Keeping conversion here, rather than calculating rates elsewhere, gives the
    rest of the pipeline one predictable place to apply the challenge's dated
    exchange-rate table.
    """
    # A same-currency conversion needs no rate lookup and must preserve the
    # amount exactly as requested by the challenge contract.
    if from_ccy == to_ccy:
        return amount

    global _RATE_SCHEMA
    if _RATE_SCHEMA is None:
        _RATE_SCHEMA = _detect_rate_schema(rates_df)

    # Compare dates as text because the loader intentionally leaves CSV values
    # unparsed, and the public function receives the date as a string.
    date_mask = rates_df["rate_date"].astype(str) == str(date)
    if _RATE_SCHEMA == "separate_columns":
        pair_mask = (
            (rates_df["from_currency"] == from_ccy)
            & (rates_df["to_currency"] == to_ccy)
        )
    else:
        pair_mask = rates_df["currency_pair"] == f"{from_ccy}_{to_ccy}"

    matching_rates = rates_df.loc[date_mask & pair_mask, "rate"]
    if matching_rates.empty:
        raise ValueError(f"No rate for {from_ccy}->{to_ccy} on {date}")

    return float(amount * matching_rates.iloc[0])


if __name__ == "__main__":
    # This block is only a tiny manual demonstration; importing the module does
    # not load the dataset or print anything.
    rates = pd.read_csv("../dataset/exchange_rates.csv")
    sample_date = str(rates.iloc[0]["rate_date"])

    # Same currency: this proves the input is returned without a table lookup.
    print("USD -> USD:", convert(100.0, "USD", "USD", sample_date, rates))

    # Existing pair: use the first row so this example works with either schema.
    first_row = rates.iloc[0]
    if "currency_pair" in rates.columns:
        sample_from, sample_to = str(first_row["currency_pair"]).split("_", 1)
    else:
        sample_from = str(first_row["from_currency"])
        sample_to = str(first_row["to_currency"])
    print(
        f"{sample_from} -> {sample_to}:",
        convert(1.0, sample_from, sample_to, sample_date, rates),
    )

    # Missing pair: the required ValueError is shown rather than hidden.
    try:
        convert(1.0, "ZZZ", "YYY", sample_date, rates)
    except ValueError as error:
        print("Missing pair:", error)
"""Small, deterministic currency-conversion helper."""

import pandas as pd


# The schema is detected lazily because importing this module must not read files
# or perform other work.  After the first lookup, all later lookups reuse it.
_RATE_SCHEMA: str | None = None


def _detect_rate_schema(rates_df: pd.DataFrame) -> str:
    """Return the supported currency-pair schema used by ``rates_df``."""
    columns = set(rates_df.columns)

    if {"from_currency", "to_currency"}.issubset(columns):
        return "separate_columns"
    if "currency_pair" in columns:
        return "currency_pair"

    raise ValueError(
        "rates_df must contain either 'currency_pair' or both "
        "'from_currency' and 'to_currency' columns"
    )


def convert(
    amount: float,
    from_ccy: str,
    to_ccy: str,
    date: str,
    rates_df: pd.DataFrame,
) -> float:
    """Convert ``amount`` using the fixed rate for a date and currency pair.

    Keeping conversion here, rather than calculating rates elsewhere, gives the
    rest of the pipeline one predictable place to apply the challenge's dated
    exchange-rate table.
    """
    # A same-currency conversion needs no rate lookup and must preserve the
    # amount exactly as requested by the challenge contract.
    if from_ccy == to_ccy:
        return amount

    global _RATE_SCHEMA
    if _RATE_SCHEMA is None:
        _RATE_SCHEMA = _detect_rate_schema(rates_df)

    # Compare dates as text because the loader intentionally leaves CSV values
    # unparsed, and the public function receives the date as a string.
    date_mask = rates_df["rate_date"].astype(str) == str(date)
    if _RATE_SCHEMA == "separate_columns":
        pair_mask = (
            (rates_df["from_currency"] == from_ccy)
            & (rates_df["to_currency"] == to_ccy)
        )
    else:
        pair_mask = rates_df["currency_pair"] == f"{from_ccy}_{to_ccy}"

    matching_rates = rates_df.loc[date_mask & pair_mask, "rate"]
    if matching_rates.empty:
        raise ValueError(f"No rate for {from_ccy}->{to_ccy} on {date}")

    return float(amount * matching_rates.iloc[0])


if __name__ == "__main__":
    # This block is only a tiny manual demonstration; importing the module does
    # not load the dataset or print anything.
    rates = pd.read_csv("../dataset/exchange_rates.csv")
    sample_date = str(rates.iloc[0]["rate_date"])

    # Same currency: this proves the input is returned without a table lookup.
    print("USD -> USD:", convert(100.0, "USD", "USD", sample_date, rates))

    # Existing pair: use the first row so this example works with either schema.
    first_row = rates.iloc[0]
    if "currency_pair" in rates.columns:
        sample_from, sample_to = str(first_row["currency_pair"]).split("_", 1)
    else:
        sample_from = str(first_row["from_currency"])
        sample_to = str(first_row["to_currency"])
    print(
        f"{sample_from} -> {sample_to}:",
        convert(1.0, sample_from, sample_to, sample_date, rates),
    )

    # Missing pair: the required ValueError is shown rather than hidden.
    try:
        convert(1.0, "ZZZ", "YYY", sample_date, rates)
    except ValueError as error:
        print("Missing pair:", error)
"""Small, deterministic currency-conversion helper."""

import pandas as pd


# The schema is detected lazily because importing this module must not read files
# or perform other work.  After the first lookup, all later lookups reuse it.
_RATE_SCHEMA: str | None = None


def _detect_rate_schema(rates_df: pd.DataFrame) -> str:
    """Return the supported currency-pair schema used by ``rates_df``."""
    columns = set(rates_df.columns)

    if {"from_currency", "to_currency"}.issubset(columns):
        return "separate_columns"
    if "currency_pair" in columns:
        return "currency_pair"

    raise ValueError(
        "rates_df must contain either 'currency_pair' or both "
        "'from_currency' and 'to_currency' columns"
    )


def convert(
    amount: float,
    from_ccy: str,
    to_ccy: str,
    date: str,
    rates_df: pd.DataFrame,
) -> float:
    """Convert ``amount`` using the fixed rate for a date and currency pair.

    Keeping conversion here, rather than calculating rates elsewhere, gives the
    rest of the pipeline one predictable place to apply the challenge's dated
    exchange-rate table.
    """
    # A same-currency conversion needs no rate lookup and must preserve the
    # amount exactly as requested by the challenge contract.
    if from_ccy == to_ccy:
        return amount

    global _RATE_SCHEMA
    if _RATE_SCHEMA is None:
        _RATE_SCHEMA = _detect_rate_schema(rates_df)

    # Compare dates as text because the loader intentionally leaves CSV values
    # unparsed, and the public function receives the date as a string.
    date_mask = rates_df["rate_date"].astype(str) == str(date)
    if _RATE_SCHEMA == "separate_columns":
        pair_mask = (
            (rates_df["from_currency"] == from_ccy)
            & (rates_df["to_currency"] == to_ccy)
        )
    else:
        pair_mask = rates_df["currency_pair"] == f"{from_ccy}_{to_ccy}"

    matching_rates = rates_df.loc[date_mask & pair_mask, "rate"]
    if matching_rates.empty:
        raise ValueError(f"No rate for {from_ccy}->{to_ccy} on {date}")

    return float(amount * matching_rates.iloc[0])


if __name__ == "__main__":
    # This block is only a tiny manual demonstration; importing the module does
    # not load the dataset or print anything.
    rates = pd.read_csv("../dataset/exchange_rates.csv")
    sample_date = str(rates.iloc[0]["rate_date"])

    # Same currency: this proves the input is returned without a table lookup.
    print("USD -> USD:", convert(100.0, "USD", "USD", sample_date, rates))

    # Existing pair: use the first row so this example works with either schema.
    first_row = rates.iloc[0]
    if "currency_pair" in rates.columns:
        sample_from, sample_to = str(first_row["currency_pair"]).split("_", 1)
    else:
        sample_from = str(first_row["from_currency"])
        sample_to = str(first_row["to_currency"])
    print(
        f"{sample_from} -> {sample_to}:",
        convert(1.0, sample_from, sample_to, sample_date, rates),
    )

    # Missing pair: the required ValueError is shown rather than hidden.
    try:
        convert(1.0, "ZZZ", "YYY", sample_date, rates)
    except ValueError as error:
        print("Missing pair:", error)
"""Small, deterministic currency-conversion helper."""

import pandas as pd


# The schema is detected lazily because importing this module must not read files
# or perform other work.  After the first lookup, all later lookups reuse it.
_RATE_SCHEMA: str | None = None


def _detect_rate_schema(rates_df: pd.DataFrame) -> str:
    """Return the supported currency-pair schema used by ``rates_df``."""
    columns = set(rates_df.columns)

    if {"from_currency", "to_currency"}.issubset(columns):
        return "separate_columns"
    if "currency_pair" in columns:
        return "currency_pair"

    raise ValueError(
        "rates_df must contain either 'currency_pair' or both "
        "'from_currency' and 'to_currency' columns"
    )


def convert(
    amount: float,
    from_ccy: str,
    to_ccy: str,
    date: str,
    rates_df: pd.DataFrame,
) -> float:
    """Convert ``amount`` using the fixed rate for a date and currency pair.

    Keeping conversion here, rather than calculating rates elsewhere, gives the
    rest of the pipeline one predictable place to apply the challenge's dated
    exchange-rate table.
    """
    # A same-currency conversion needs no rate lookup and must preserve the
    # amount exactly as requested by the challenge contract.
    if from_ccy == to_ccy:
        return amount

    global _RATE_SCHEMA
    if _RATE_SCHEMA is None:
        _RATE_SCHEMA = _detect_rate_schema(rates_df)

    # Compare dates as text because the loader intentionally leaves CSV values
    # unparsed, and the public function receives the date as a string.
    date_mask = rates_df["rate_date"].astype(str) == str(date)
    if _RATE_SCHEMA == "separate_columns":
        pair_mask = (
            (rates_df["from_currency"] == from_ccy)
            & (rates_df["to_currency"] == to_ccy)
        )
    else:
        pair_mask = rates_df["currency_pair"] == f"{from_ccy}_{to_ccy}"

    matching_rates = rates_df.loc[date_mask & pair_mask, "rate"]
    if matching_rates.empty:
        raise ValueError(f"No rate for {from_ccy}->{to_ccy} on {date}")

    return float(amount * matching_rates.iloc[0])


if __name__ == "__main__":
    # This block is only a tiny manual demonstration; importing the module does
    # not load the dataset or print anything.
    rates = pd.read_csv("../dataset/exchange_rates.csv")
    sample_date = str(rates.iloc[0]["rate_date"])

    # Same currency: this proves the input is returned without a table lookup.
    print("USD -> USD:", convert(100.0, "USD", "USD", sample_date, rates))

    # Existing pair: use the first row so this example works with either schema.
    first_row = rates.iloc[0]
    if "currency_pair" in rates.columns:
        sample_from, sample_to = str(first_row["currency_pair"]).split("_", 1)
    else:
        sample_from = str(first_row["from_currency"])
        sample_to = str(first_row["to_currency"])
    print(
        f"{sample_from} -> {sample_to}:",
        convert(1.0, sample_from, sample_to, sample_date, rates),
    )

    # Missing pair: the required ValueError is shown rather than hidden.
    try:
        convert(1.0, "ZZZ", "YYY", sample_date, rates)
    except ValueError as error:
        print("Missing pair:", error)
