def ensure_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in EXPECTED_COLS:
        if c not in df.columns:
            if c == "Stärke (1-4)":
                df[c] = 4
            elif c == "Abwesend":
                df[c] = False
            else:
                df[c] = ""
    
    # Garantierte Typ-Konvertierung für st.data_editor Kompatibilität
    df["Name"] = df["Name"].astype(str)
    df["Stärke (1-4)"] = pd.to_numeric(df["Stärke (1-4)"], errors="coerce").fillna(4).clip(1, 4).astype(int)
    df["Abwesend"] = df["Abwesend"].astype(bool)
    
    return df[EXPECTED_COLS]