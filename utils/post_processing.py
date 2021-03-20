import pandas as pd


def auto_marking_(df: pd.DataFrame) -> pd.DataFrame:
    social = df.title.str.contains("社宅") | df.title.str.contains("社會住宅")
    df.loc[social, "mark"] = "x"
    df.loc[df["車 位"].str.contains("機械"), "mark"] = "x"
    return df


def adjust_price_(df: pd.DataFrame) -> pd.DataFrame:
    df["price_adjusted"] = (
        df["price"] * (df["poster"].str.contains("收取服務費").astype("float") * 1/24 + 1)
    ).astype("int")
    df["price_adjusted"] = (
        df["price_adjusted"] +
        df["管理費"].str.replace("元/月", "").str.replace("--", "0").str.replace("無", "0").astype("int")
    )
    df["price_adjusted"] = (
        df["price_adjusted"] + df["車 位"].str.contains("費用另計").astype("int") * 2500
    )
    return df
