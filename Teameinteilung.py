import pandas as pd

EXPECTED_COLS = [
    # ...
]

def ensure_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in EXPECTED_COLS:
        if c not in df.columns:
            df[c] = ""
    return df
``
