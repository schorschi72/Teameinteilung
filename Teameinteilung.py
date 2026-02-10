import os
import re
import io
import random
from datetime import datetime

import pandas as pd
import streamlit as st

# ----------------------------------------
# Streamlit Setup
# ----------------------------------------
st.set_page_config(
    page_title="Team-/Gruppen-Generator – Jürg Boltshauser",
    page_icon="🏆",
    layout="wide",
)

# ----------------------------------------
# CSS – verhindert Zeilenumbrüche bei Buttons
# ----------------------------------------
st.markdown("""
<style>
.stDownloadButton > button {
    white-space: nowrap !important;
    padding: 0.45rem 0.6rem !important;
}
</style>
""", unsafe_allow_html=True)

# ----------------------------------------
# CSV Persistenz
# ----------------------------------------
try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd()

PARTICIPANTS_DIR = os.path.join(BASE_DIR, "participants")
os.makedirs(PARTICIPANTS_DIR, exist_ok=True)

EXPECTED_COLS = ["Name", "Stärke (1-4)", "Abwesend"]


def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r"\s+", " ", name)
    if not name:
        raise ValueError("Listenname darf nicht leer sein.")
    return name


def list_names() -> list[str]:
    files = [f for f in os.listdir(PARTICIPANTS_DIR) if f.lower().endswith(".csv")]
    names = [os.path.splitext(f)[0] for f in files]
    return sorted(names, key=lambda s: s.lower())


def path_for_list(name: str) -> str:
    return os.path.join(PARTICIPANTS_DIR, sanitize_filename(name) + ".csv")


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

    df["Stärke (1-4)"] = pd.to_numeric(df["Stärke (1-4)"], errors="coerce").fillna(4).clip(1, 4).astype(int)
    df["Abwesend"] = df["Abwesend"].astype(bool)

    return df[EXPECTED_COLS]


def load_participants(name: str) -> pd.DataFrame:
    p = path_for_list(name)
    if not os.path.exists(p):
        return pd.DataFrame(columns=EXPECTED_COLS)
    try:
        df = pd.read_csv(p, encoding="utf-8")
    except Exception:
        df = pd.read_csv(p, encoding="latin-1")
    return ensure_cols(df)


def save_participants(name: str, df: pd.DataFrame):
    ensure_cols(df).to_csv(path_for_list(name), index=False, encoding="utf-8")


def create_list(name: str):
    save_participants(name, pd.DataFrame(columns=EXPECTED_COLS))


def delete_list(name: str):
    p = path_for_list(name)
    if os.path.exists(p):
        os.remove(p)


# ----------------------------------------
# SIDEBAR – Listenverwaltung
# ----------------------------------------
with st.sidebar:
    st.header("👥 Teilnehmerlisten")

    all_lists = list_names()

    selected_list = st.selectbox(
        "Liste auswählen",
        options=all_lists,
        key="selected_list"
    )

    if selected_list:
        st.session_state["current_df"] = load_participants(selected_list)

    # Pending List Handler
    if "pending_list" in st.session_state:
        new_list = st.session_state["pending_list"]

        if "selected_list" in st.session_state:
            del st.session_state["selected_list"]

        st.session_state["selected_list"] = new_list
        st.session_state["current_df"] = load_participants(new_list)

        del st.session_state["pending_list"]
        st.rerun()

    # ----------------------------------------
    # Neue Liste anlegen – mit Copy/Paste
    # ----------------------------------------
    with st.expander("➕ Neue Liste anlegen"):
        new_list_name = st.text_input("Name der neuen Liste", key="new_list_name_input")

        st.markdown("### Teilnehmer einfügen (Copy & Paste)")
        st.markdown(
            "Format: `Nachname Vorname Klasse` – pro Zeile ein Teilnehmer.<br>"
            "Trennzeichen wie Leerzeichen, Tab, Komma, Semikolon werden automatisch erkannt.",
            unsafe_allow_html=True
        )

        pasted_text = st.text_area("Hier einfügen", height=200, key="paste_area")

        if st.button("Liste erstellen", key="btn_new_list"):
            name = new_list_name.strip()
            if not name:
                st.error("Bitte gültigen Listennamen eingeben.")
                st.stop()

            entries = []
            for raw_line in pasted_text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue

                clean = line.replace(";", " ").replace(",", " ")
                parts = [p for p in re.split(r"\s+", clean) if p]
                person_name = " ".join(parts)

                entries.append([person_name, 4, False])

            df_new = pd.DataFrame(entries, columns=EXPECTED_COLS)

            save_participants(name, df_new)
            st.session_state.pending_list = name
            st.rerun()

    # ----------------------------------------
    # Aktionen für bestehende Liste – ohne Umbenennen
    # ----------------------------------------
    if selected_list:
        with st.expander("⚙️ Aktionen"):

            # 2-Spalten Layout für perfekte Darstellung
            col_left, col_right = st.columns(2)

            with col_left:
                df_export = st.session_state.get("current_df", pd.DataFrame(columns=EXPECTED_COLS))
                st.download_button(
                    "📥 CSV herunterladen",
                    df_export.to_csv(index=False).encode("utf-8"),
                    file_name=f"{selected_list}.csv",
                    mime="text/csv",
                )

            with col_right:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    df_export.to_excel(writer, index=False)

                st.download_button(
                    "📄 Excel herunterladen",
                    buf.getvalue(),
                    file_name=f"{selected_list}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            # Löschen
            if st.button("🗑 Liste löschen", type="secondary", key="delete_btn"):
                delete_list(selected_list)

                if "selected_list" in st.session_state:
                    del st.session_state["selected_list"]

                st.session_state["current_df"] = pd.DataFrame(columns=EXPECTED_COLS)
                st.rerun()


# ----------------------------------------
# Hauptbereich
# ----------------------------------------
st.title("🏆 Team- / Gruppen-Generator")

# ------------------------------
# 1) Teilnehmer bearbeiten
# ------------------------------
st.header("1️⃣ Teilnehmer bearbeiten")

df = ensure_cols(st.session_state.get("current_df", pd.DataFrame(columns=EXPECTED_COLS)))

edited_df = st.data_editor(
    df,
    width="stretch",
    num_rows="dynamic",
    column_config={
        "Name": st.column_config.TextColumn("Name"),
        "Stärke (1-4)": st.column_config.NumberColumn("Stärke (1-4)", min_value=1, max_value=4, step=1),
        "Abwesend": st.column_config.CheckboxColumn("Abwesend"),
    },
    key="editor"
)

if selected_list:
    if st.button("💾 Änderungen speichern", type="primary", key="save_btn"):
        save_participants(selected_list, ensure_cols(edited_df))
        st.success("Liste gespeichert.")
        st.session_state["current_df"] = load_participants(selected_list)
        st.rerun()

# ------------------------------
# 2) Suche
# ------------------------------
st.header("2️⃣ Suche")

search_term = st.text_input("🔍 Filter nach Name", key="search_input")

if search_term:
    filtered = edited_df[edited_df["Name"].str.contains(search_term, case=False, na=False)]
else:
    filtered = edited_df

st.dataframe(filtered, width="stretch", height=250)

# ------------------------------
# 3) Teams generieren
# ------------------------------
st.header("3️⃣ Teams generieren")

col1, col2 = st.columns(2)
num_groups = col1.number_input("Anzahl Gruppen", min_value=0, max_value=100, value=0, key="num_groups")
group_size = col2.number_input("Gruppengröße", min_value=0, max_value=100, value=0, key="group_size")

generate = st.button("🚀 Teams generieren", key="generate_btn")


def snake_draft(df_sorted: pd.DataFrame, groups: int, rng: random.Random):
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


def export_csv(teams: list[list[dict]]) -> bytes:
    rows = []
    for gi, team in enumerate(teams, start=1):
        for person in team:
            rows.append({
                "Gruppe": gi,
                "Name": person["Name"],
                "Stärke": person["Stärke (1-4)"],
            })
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


if generate:
    present = edited_df[edited_df["Abwesend"] == False].copy()

    if present.empty:
        st.error("Alle Teilnehmer sind abwesend!")
        st.stop()

    rng = random.Random()
    present["__r"] = [rng.random() for _ in range(len(present))]
    present = present.sort_values(["Stärke (1-4)", "__r"], ascending=[False, True]).drop(columns="__r")

    if num_groups > 0 and group_size == 0:
        groups_count = int(num_groups)
    elif group_size > 0 and num_groups == 0:
        groups_count = (len(present) + int(group_size) - 1) // int(group_size)
    else:
        st.error("Bitte EINE Auswahl treffen: Gruppenanzahl ODER Gruppengröße")
        st.stop()

    if groups_count <= 0:
        st.error("Die berechnete Gruppenzahl ist 0. Bitte Eingaben prüfen.")
        st.stop()

    teams = snake_draft(present, groups_count, rng)

    st.subheader("Ergebnis")
    cols = st.columns(min(4, groups_count))

    for i, team in enumerate(teams, start=1):
        with cols[(i - 1) % len(cols)]:
            st.markdown(f"### Gruppe {i}")
            if not team:
                st.info("Keine Personen in dieser Gruppe.")
                continue
            df_team = pd.DataFrame(team)
            st.write(f"**Gesamtstärke:** {df_team['Stärke (1-4)'].sum()}")
            st.dataframe(df_team[["Name", "Stärke (1-4)"]], width="stretch", hide_index=True)

    st.download_button(
        "⬇️ Teams als CSV",
        export_csv(teams),
        file_name=f"Teams_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        key="download_teams_csv"
    )