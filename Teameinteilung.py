# web-app/Teameinteilung.py
import streamlit as st
import pandas as pd
import numpy as np
import io
import random
from datetime import datetime

# ---------- Seiteneinstellungen ----------
st.set_page_config(
    page_title="Team-/Gruppen-Generator – Jürg Boltshauser 09.02.2026",
    page_icon="🏆",
    layout="wide",
)

st.title("🏆 Team- / Gruppen-Generator")
st.caption("von **Jürg Boltshauser**, 09.02.2026")

st.markdown("""
Dieses Tool erstellt fair aufgeteilte Teams anhand von:
- **Namen**
- **Stärke** (1 = schwach, 4 = stark)
- **Abwesend**-Markierung

Wähle **Anzahl Gruppen** *oder* **Gruppengröße** und klicke **„Teams generieren“**.
""")

# ---------- Sidebar: Einstellungen ----------
with st.sidebar:
    st.header("⚙️ Einstellungen")
    seed_on = st.toggle("Zufalls-Seed verwenden (reproduzierbar)", value=False)
    seed_value = st.number_input("Seed", min_value=0, max_value=999999, value=42, step=1, disabled=not seed_on)
    st.markdown("---")
    st.markdown("**Titelleiste**")
    custom_title = st.text_input("Fenster-/Seiten-Titel", value="Team-/Gruppen-Generator – Jürg Boltshauser 09.02.2026")
    if custom_title:
        st.session_state["__title"] = custom_title  # nur visuell, Streamlit-Titel ist in set_page_config gesetzt
    st.markdown("---")
    st.info("💡 Tipp: Du kannst deine Liste auch in Excel vorbereiten und hier einfügen.")

# ---------- 1) Teilnehmerliste ----------
st.header("1️⃣ Teilnehmerliste eingeben")

raw_list = st.text_area(
    "Namen (eine Person pro Zeile):",
    height=200,
    placeholder="Max Muster\nLaura Beispiel\n..."
)

if raw_list.strip():
    names = [n.strip() for n in raw_list.splitlines() if n.strip()]
else:
    names = []

# ---------- 2) Teilnehmer bearbeiten ----------
st.header("2️⃣ Teilnehmer bearbeiten")
if len(names) > 0:
    base_df = pd.DataFrame({
        "Name": names,
        "Stärke (1-4)": [4] * len(names),
        "Abwesend": [False] * len(names),
    })
else:
    base_df = pd.DataFrame(columns=["Name", "Stärke (1-4)", "Abwesend"])

edited_df = st.data_editor(
    base_df,
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "Stärke (1-4)": st.column_config.NumberColumn(min_value=1, max_value=4, step=1),
        "Abwesend": st.column_config.CheckboxColumn(),
        "Name": st.column_config.TextColumn(),
    },
    key="editor",
)

# ---------- 3) Suche ----------
st.header("3️⃣ Suche")
col_s1, col_s2 = st.columns([1, 3])
with col_s1:
    search_term = st.text_input("🔍 Filtern nach Name", value="")
with col_s2:
    st.write("")  # spacing

if search_term:
    filtered_df = edited_df[edited_df["Name"].str.contains(search_term, case=False, na=False)]
else:
    filtered_df = edited_df

st.dataframe(filtered_df, use_container_width=True, height=260)

# ---------- 4) Teameinstellungen ----------
st.header("4️⃣ Teams generieren")
colA, colB, colC = st.columns([1, 1, 2])
with colA:
    num_groups = st.number_input("Anzahl Gruppen (Alternative zu Gruppengröße)", min_value=0, max_value=200, value=0, step=1)
with colB:
    group_size = st.number_input("Gruppengröße (Alternative zu Anzahl Gruppen)", min_value=0, max_value=200, value=0, step=1)
with colC:
    st.write("")
generate = st.button("🚀 Teams generieren")

# ---------- Hilfsfunktionen ----------
def snake_draft_allocation(df_sorted: pd.DataFrame, groups: int, rng: random.Random) -> list:
    """
    Verteilt Zeilen (Teilnehmer) im Snake-Draft-Verfahren auf 'groups' Teams.
    df_sorted: DataFrame, absteigend nach Stärke sortiert.
    """
    teams = [[] for _ in range(groups)]
    direction = 1
    idx = 0
    for _, row in df_sorted.iterrows():
        teams[idx].append(row.to_dict())
        idx += direction
        if idx == groups:
            idx = groups - 1
            direction = -1
        elif idx < 0:
            idx = 0
            direction = 1
    return teams

def to_csv_download(teams_list: list) -> bytes:
    """Erzeugt eine CSV als Bytes aus der Teamliste."""
    rows = []
    for gi, team in enumerate(teams_list, start=1):
        for person in team:
            rows.append({
                "Gruppe": gi,
                "Name": person["Name"],
                "Stärke": person["Stärke (1-4)"]
            })
    out_df = pd.DataFrame(rows)
    return out_df.to_csv(index=False).encode("utf-8")

# ---------- 5) Generierung ----------
if generate:
    # Abwesende raus
    present_df = edited_df[edited_df["Abwesend"] == False].copy()

    # Sanity Checks
    if len(present_df) == 0:
        st.error("Alle Teilnehmer sind abwesend!")
        st.stop()

    # Seed optional setzen (beeinflusst nur die Randomisierung vor dem Sortieren)
    rng = random.Random(seed_value if seed_on else None)

    # Bei gleicher Stärke zufällig durchmischen, damit die Reihenfolge nicht starr ist
    # (wir fügen eine kleine Zufallsspalte hinzu und sortieren danach sekundär)
    present_df["__shuffle"] = [rng.random() for _ in range(len(present_df))]
    present_df = present_df.sort_values(by=["Stärke (1-4)", "__shuffle"], ascending=[False, True]).drop(columns="__shuffle")

    # Anzahl Gruppen bestimmen
    if num_groups > 0 and group_size == 0:
        groups_count = int(num_groups)
    elif group_size > 0 and num_groups == 0:
        groups_count = (len(present_df) + int(group_size) - 1) // int(group_size)
    else:
        st.error("Bitte EINE Option wählen: **Anzahl Gruppen** ODER **Gruppengröße**.")
        st.stop()

    if groups_count <= 0:
        st.error("Gruppenzahl muss > 0 sein.")
        st.stop()

    # Snake Draft
    teams = snake_draft_allocation(present_df, groups_count, rng)

    # Anzeige
    st.header("5️⃣ Ergebnis")
    total_people = sum(len(t) for t in teams)
    st.write(f"**{groups_count} Gruppen**, **{total_people} anwesend**")

    cols = st.columns(min(groups_count, 4))  # bis zu 4 Spalten nebeneinander
    for i, team in enumerate(teams, start=1):
        col = cols[(i - 1) % len(cols)]
        with col:
            st.subheader(f"Gruppe {i}")
            if len(team) == 0:
                st.info("Keine Personen in dieser Gruppe.")
                continue
            team_df = pd.DataFrame(team)
            total_strength = int(team_df["Stärke (1-4)"].sum())
            st.write(f"**Gesamtstärke: {total_strength}**")
            st.dataframe(team_df[["Name", "Stärke (1-4)"]], use_container_width=True, hide_index=True, height=200)

    # Download
    st.markdown("---")
    csv_bytes = to_csv_download(teams)
    filename = f"Teams_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
    st.download_button(
        label="⬇️ Teams als CSV herunterladen",
        data=csv_bytes,
        file_name=filename,
        mime="text/csv",
    )

    st.success("🎉 Teameinteilung abgeschlossen!")