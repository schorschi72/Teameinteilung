import os
import re
import io
import random
from datetime import datetime

import pandas as pd
import streamlit as st

st.markdown("""
    <div style='background-color:#f0f2f6;padding:15px;border-radius:10px'>
        <h2 style='margin:0;'>Jürg Boltshauser – 10.02.2026</h2>
    </div>
""", unsafe_allow_html=True)

# ----------------------------------------
# Streamlit Setup
# ----------------------------------------
st.set_page_config(
    page_title="Team-/Gruppen-Generator – Jürg Boltshauser",
    page_icon="🏆",
    layout="wide",
)

# ----------------------------------------
# CSS
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
# CSV Persistenz – stabiler Projektpfad
# ----------------------------------------
try:
    BASE_DIR = os.path.dirname(os.path.realpath(__file__))
except:
    BASE_DIR = os.path.realpath(os.getcwd())

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
    return sorted(files, key=lambda s: s.lower())


def path_for_list(filename: str) -> str:
    return os.path.join(PARTICIPANTS_DIR, filename)


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

    df["Stärke (1-4)"] = (
        pd.to_numeric(df["Stärke (1-4)"], errors="coerce")
        .fillna(4)
        .clip(1, 4)
        .astype(int)
    )
    df["Abwesend"] = df["Abwesend"].astype(bool)

    return df[EXPECTED_COLS]


def load_participants(filename: str) -> pd.DataFrame:
    p = path_for_list(filename)
    if not os.path.exists(p):
        return pd.DataFrame(columns=EXPECTED_COLS)
    try:
        df = pd.read_csv(p, encoding="utf-8")
    except:
        df = pd.read_csv(p, encoding="latin-1")
    return ensure_cols(df)


def save_participants(filename: str, df: pd.DataFrame):
    ensure_cols(df).to_csv(path_for_list(filename), index=False, encoding="utf-8")


def create_list(name: str):
    filename = sanitize_filename(name) + ".csv"
    save_participants(filename, pd.DataFrame(columns=EXPECTED_COLS))


def delete_list(filename: str):
    p = path_for_list(filename)
    if os.path.exists(p):
        os.remove(p)


# ----------------------------------------
# SIDEBAR – Listenverwaltung
# ----------------------------------------
with st.sidebar:
    st.header("👥 Teilnehmerlisten")

    # 1) Verfügbare Dateien lesen
    files = list_names()
    mapping = {f: os.path.splitext(f)[0] for f in files}
    options = list(mapping.keys())

    # 2) Falls gerade eine neue Liste erstellt wurde, setze sie als Auswahl,
    #    aber WICHTIG: VOR dem selectbox-Widget.
    if "pending_file" in st.session_state:
        pf = st.session_state["pending_file"]
        # pending Flag entfernen, damit es nur einmal wirkt
        del st.session_state["pending_file"]
        # Nur setzen, wenn die Datei wirklich existiert (Race-Condition vermeiden)
        if pf in options:
            st.session_state["selected_file"] = pf

    # 3) Initialwert für selected_file, falls noch nicht gesetzt
    if "selected_file" not in st.session_state:
        st.session_state["selected_file"] = options[0] if options else None

    # 4) selectbox anzeigen; der Wert kommt/bleibt aus st.session_state["selected_file"]
    #    Kein manuelles Setzen nach dem Widget!
    selected_file = st.selectbox(
        "Liste auswählen",
        options=options,
        index=(options.index(st.session_state["selected_file"]) if st.session_state["selected_file"] in options else 0) if options else None,
        format_func=lambda f: mapping.get(f, f),
        key="selected_file",  # Widget kontrolliert den State
    )

    # 5) Daten der gewählten Liste in den State laden (Daten, nicht den Widget-Key setzen)
    if selected_file:
        st.session_state["current_df"] = load_participants(selected_file)
    else:
        st.session_state["current_df"] = pd.DataFrame(columns=EXPECTED_COLS)

    # Neue Liste anlegen
    with st.expander("➕ Neue Liste anlegen"):
        new_list_name = st.text_input("Name der neuen Liste")

        st.markdown("### Teilnehmer einfügen (Copy & Paste)")
        st.markdown(
            "Format: `Nachname Vorname Klasse` – pro Zeile ein Teilnehmer.<br>"
            "Trennzeichen wie Leerzeichen, Tab, Komma, Semikolon werden automatisch erkannt.",
            unsafe_allow_html=True,
        )

        pasted_text = st.text_area("Hier einfügen", height=200)

        if st.button("Liste erstellen"):
            if not new_list_name.strip():
                st.error("Bitte gültigen Listennamen eingeben.")
                st.stop()

            filename = sanitize_filename(new_list_name.strip()) + ".csv"

            entries = []
            for line in pasted_text.splitlines():
                clean = line.strip()
                if not clean:
                    continue

                clean = clean.replace(";", " ").replace(",", " ")
                parts = [p for p in re.split(r"\s+", clean) if p]
                person_name = " ".join(parts)
                entries.append([person_name, 4, False])

            df_new = pd.DataFrame(entries, columns=EXPECTED_COLS)
            save_participants(filename, df_new)

            # Nur das Flag setzen und rerun — die selectbox übernimmt im nächsten Run
            st.session_state["pending_file"] = filename
            st.rerun()

    # Aktionen
    if selected_file:
        with st.expander("⚙️ Aktionen"):
            col_left, col_right = st.columns(2)
            df_export = st.session_state.get("current_df", pd.DataFrame(columns=EXPECTED_COLS))

            with col_left:
                st.download_button(
                    "📥 CSV herunterladen",
                    df_export.to_csv(index=False).encode("utf-8"),
                    file_name=selected_file,
                    mime="text/csv",
                )

            with col_right:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    df_export.to_excel(writer, index=False)

                st.download_button(
                    "📄 Excel herunterladen",
                    buf.getvalue(),
                    file_name=selected_file.replace(".csv", ".xlsx"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            if st.button("🗑 Liste löschen"):
                delete_list(selected_file)
                # Liste in State leeren und ggf. neue Auswahl setzen
                remaining = list_names()
                st.session_state["current_df"] = pd.DataFrame(columns=EXPECTED_COLS)
                if remaining:
                    st.session_state["selected_file"] = remaining[0]
                else:
                    st.session_state["selected_file"] = None
                st.rerun()


# ----------------------------------------
# HAUPTBEREICH
# ----------------------------------------
st.title("🏆 Team- / Gruppen-Generator")

# 1 – Teilnehmer bearbeiten
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
)

selected_file = st.session_state.get("selected_file")

if selected_file:
    if st.button("💾 Änderungen speichern", type="primary"):
        save_participants(selected_file, ensure_cols(edited_df))
        st.success("Liste gespeichert.")
        st.session_state["current_df"] = load_participants(selected_file)
        st.rerun()

# 2 – Suche
st.header("2️⃣ Suche")

search_term = st.text_input("🔍 Filter nach Name")

filtered = (
    edited_df[edited_df["Name"].str.contains(search_term, case=False, na=False)]
    if search_term else edited_df
)

st.dataframe(filtered, width="stretch", height=250)

# 3 – Teams generieren
st.header("3️⃣ Teams generieren")

col1, col2 = st.columns(2)
num_groups = col1.number_input("Anzahl Gruppen", min_value=0, max_value=100, value=0)
group_size = col2.number_input("Gruppengröße", min_value=0, max_value=100, value=0)

generate = st.button("🚀 Teams generieren")


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


def export_csv(teams):
    rows = []
    for gi, team in enumerate(teams, start=1):
        for p in team:
            rows.append(
                {"Gruppe": gi, "Name": p["Name"], "Stärke": p["Stärke (1-4)"]}
            )
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


if generate:
    present = edited_df[edited_df["Abwesend"] == False].copy()

    if present.empty:
        st.error("Alle Teilnehmer sind abwesend!")
        st.stop()

    rng = random.Random()
    present["__r"] = [rng.random() for _ in range(len(present))]
    present = (
        present.sort_values(["Stärke (1-4)", "__r"], ascending=[False, True])
        .drop(columns="__r")
    )

    if num_groups > 0 and group_size == 0:
        groups_count = int(num_groups)
    elif group_size > 0 and num_groups == 0:
        groups_count = (len(present) + int(group_size) - 1) // int(group_size)
    else:
        st.error("Bitte EINE Auswahl treffen: Gruppenanzahl ODER Gruppengröße")
        st.stop()

    if groups_count <= 0:
        st.error("Die berechnete Gruppenzahl ist 0.")
        st.stop()

    teams = snake_draft(present, groups_count, rng)

    st.subheader("Ergebnis")
    cols = st.columns(min(4, groups_count))

    for i, team in enumerate(teams, start=1):
        with cols[(i - 1) % len(cols)]:
            st.markdown(f"### Gruppe {i}")
            if not team:
                st.info("Keine Personen.")
                continue
            df_team = pd.DataFrame(team)
            st.write(f"**Gesamtstärke:** {df_team['Stärke (1-4)'].sum()}")
            st.dataframe(df_team[["Name", "Stärke (1-4)"]], hide_index=True)

    st.download_button(
        "⬇️ Teams als CSV",
        export_csv(teams),
        file_name=f"Teams_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )