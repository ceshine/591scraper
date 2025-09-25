import re

import pandas as pd


def parse_price(price_str: str) -> int:
    if price_str == "" or "--" in price_str or "無" in price_str:
        return 0
    try:
        return int(re.match(r"^([\d,]+)\w+", price_str).group(1).replace(",", ""))
    except AttributeError:
        return 0


def auto_marking_(df: pd.DataFrame) -> pd.DataFrame:
    df["mark"] = ""
    social = df.title.str.contains("社宅") | df.title.str.contains("社會住宅") | df.desc.str.contains("社會住宅")
    df.loc[social, "mark"] = "x"
    df.loc[df["提供設備"].str.contains("機械車位"), "mark"] = "x"
    return df


def adjust_price_(df: pd.DataFrame) -> pd.DataFrame:
    df["price_adjusted"] = (
        df["price"] * (df["poster"].str.contains("收取服務費").astype("float") * 1 / 24 + 1)
    ).astype("int")
    df["price_adjusted"] = df["price_adjusted"] + df["管理費"].fillna("").apply(parse_price)
    df["price_adjusted"] = df["price_adjusted"] + df["車位費"].fillna("").str.contains("費用另計").astype("int") * 2500
    return df
