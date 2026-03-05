# =========================================
# Team-/Gruppen-Generator – GitHub-integriert
# =========================================
# Features:
# - Teilnehmerlisten als CSV im Repo-Verzeichnis "participants/" verwalten
# - Neues Anlegen, Bearbeiten, Löschen
# - Automatischer Upload nach GitHub (Create/Update/Delete) bei vorhandenem Secret
# - Optionaler "Neu von GitHub laden"-Knopf (Pull/Overwrite lokal)
# - Korrigierte Session-State/Selectbox-Logik (kein Default+State-Konflikt)
# - Snake-Draft-Teamverteilung nach Stärke
# =========================================

import os
import re
import io
import base64
import json
import random
from datetime import datetime

import pandas as pd
import streamlit as st
import requests


# ----------------------------------------
# Streamlit Setup (muss als erstes kommen)
# ----------------------------------------
st.set_page_config(
    page_title="Team-/Gruppen-Generator – Jürg Boltshauser",
    page_icon="🏆",
    layout="wide",
)

# ----------------------------------------
# Header
# ----------------------------------------
st.markdown("""
    <div style='background-color:#f0f2f6;padding:15px;border-radius:10px'>
        <h2 style='margin:0;'>Jürg Boltshauser – 10.02.2026</h2>
    </div>
""", unsafe_allow_html=True)

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
except Exception:
    BASE_DIR = os.path.realpath(os.getcwd())

PARTICIPANTS_DIR = os.path.join(BASE_DIR, "participants")
os.makedirs(PARTICIPANTS_DIR, exist_ok=True)

EXPECTED_COLS = ["Name", "Stärke (1-4)", "Abwesend"]

# ----------------------------------------
# GitHub Settings aus Secrets (falls vorhanden)
# ----------------------------------------
GITHUB_TOKEN = st.secrets.get("github_token")
GITHUB_REPO = st.secrets.get("github_repo")
GITHUB_BRANCH = st.secrets.get("github_branch", "main")
GITHUB_ENABLED = bool(GITHUB_TOKEN and GITHUB_REPO and GITHUB_BRANCH)

GITHUB_API_BASE = "https://api.github.com"

# ----------------------------------------
# GitHub Helper-Funktionen
# ----------------------------------------
def gh_headers():
    if not GITHUB_ENABLED:
        return {}
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

def gh_contents_url(path: str, ref: str | None = None) -> str:
    if ref:
        return f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{path}?ref={ref}"
    return f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{path}"

def github_get_file_sha(path: str, branch: str) -> str | None:
    """Liefert SHA einer Datei oder None, wenn sie nicht existiert."""
    if not GITHUB_ENABLED:
        return None
    url = gh_contents_url(path, branch)
    r = requests.get(url, headers=gh_headers(), timeout=20)
    if r.status_code == 200:
        try:
            return r.json().get("sha")
        except Exception:
            return None
    elif r.status_code == 404:
        return None
    else:
        raise RuntimeError(f"GitHub get SHA fehlgeschlagen ({r.status_code}): {r.text}")

def github_list_participants(branch: str) -> list[str]:
    """Listet alle .csv-Dateien im participants/ Ordner im Repo."""
    if not GITHUB_ENABLED:
        # Fallback: lokal
        return sorted([f for f in os.listdir(PARTICIPANTS_DIR) if f.lower().endswith(".csv")], key=str.lower)

    url = gh_contents_url("participants", branch)
    r = requests.get(url, headers=gh_headers(), timeout=20)
    if r.status_code == 200:
        entries = r.json()
        csvs = [e["name"] for e in entries if e.get("type") == "file" and e.get("name", "").lower().endswith(".csv")]
        return sorted(csvs, key=str.lower)
    elif r.status_code == 404:
        # Ordner existiert noch nicht – leerer Zustand
        return []
    else:
        raise RuntimeError(f"GitHub Ordnerliste fehlgeschlagen ({r.status_code}): {r.text}")

def github_download_file(path: str, branch: str) -> bytes | None:
    """Lädt Dateiinhalt (bytes) aus GitHub. Gibt None zurück, wenn nicht vorhanden."""
    if not GITHUB_ENABLED:
        return None
    url = gh_contents_url(path, branch)
    r = requests.get(url, headers=gh_headers(), timeout=20)
    if r.status_code == 200:
        data = r.json()
        if data.get("encoding") == "base64" and "content" in data:
            try:
                return base64.b64decode(data["content"])
            except Exception as e:
                raise RuntimeError(f"GitHub base64 decode Fehler: {e}")
        else:
            # Fallback: raw download URL, falls nötig
            download_url = data.get("download_url")
            if download_url:
                r2 = requests.get(download_url, headers=gh_headers(), timeout=20)
                r2.raise_for_status()
                return r2.content
            return None
    elif r.status_code == 404:
        return None
    else:
        raise RuntimeError(f"GitHub Download fehlgeschlagen ({r.status_code}): {r.text}")

def github_upload_file(path: str, content_bytes: bytes, branch: str, commit_message: str | None = None) -> None:
    """Erstellt/Aktualisiert Datei in GitHub (PUT /contents)."""
    if not GITHUB_ENABLED:
        return
    url = gh_contents_url(path)
    sha = github_get_file_sha(path, branch)
    payload = {
        "message": commit_message or f"Update {path}",
        "content": base64.b64encode(content_bytes).decode("utf-8"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=gh_headers(), json=payload, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"GitHub Upload fehlgeschlagen ({r.status_code}): {r.text}")

def github_delete_file(path: str, branch: str, commit_message: str | None = None) -> None:
    """Löscht Datei in GitHub (DELETE /contents)."""
    if not GITHUB_ENABLED:
        return
    sha = github_get_file_sha(path, branch)
    if not sha:
        return  # nichts zu löschen
    url = gh_contents_url(path)
    payload = {
        "message": commit_message or f"Delete {path}",
        "sha": sha,
        "branch": branch,
    }
    r = requests.delete(url, headers=gh_headers(), json=payload, timeout=30)
    if r.status_code not in (200, 204):
        raise RuntimeError(f"GitHub Delete fehlgeschlagen ({r.status_code}): {r.text}")

# ----------------------------------------
# Lokale Datei-Helfer
# ----------------------------------------
def path_for_list(filename: str) -> str:
    return os.path.join(PARTICIPANTS_DIR, filename)

def write_local_file(filename: str, data: bytes) -> None:
    p = path_for_list(filename)
    with open(p, "wb") as f:
        f.write(data)

def read_local_csv(filename: str) -> pd.DataFrame:
    p = path_for_list(filename)
    if not os.path.exists(p):
        return pd.DataFrame(columns=EXPECTED_COLS)
    try:
        df = pd.read_csv(p, encoding="utf-8")
    except Exception:
        df = pd.read_csv(p, encoding="latin-1")
    return df

# ----------------------------------------
# App-Funktionen
# ----------------------------------------
def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r"\s+", " ", name)
    if not name:
        raise ValueError("Listenname darf nicht leer sein.")
    return name

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

def list_names() -> list[str]:
    """Quelle der Wahrheit: GitHub (falls Secrets), sonst lokal."""
    if GITHUB_ENABLED:
        files = github_list_participants(GITHUB_BRANCH)
        # Sicherstellen, dass lokal gespiegelt wird (optional)
        for f in files:
            # Falls lokal fehlt, hole es herunter (Best Effort)
            p = path_for_list(f)
            if not os.path.exists(p):
                content = github_download_file(f"participants/{f}", GITHUB_BRANCH)
                if content is not None:
                    write_local_file(f, content)
        return files
    else:
        files = [f for f in os.listdir(PARTICIPANTS_DIR) if f.lower().endswith(".csv")]
        return sorted(files, key=str.lower)

def extract_prefixes(files: list[str]) -> list[str]:
    prefixes = set()
    for f in files:
        m = re.match(r"^\(([A-Za-z]{3})\)", f)
        if m:
            prefixes.add(m.group(1).upper())
    return sorted(prefixes)

def extract_prefixes(files: list[str]) -> list[str]:
    """
    Extrahiert eindeutige 3-Buchstaben-Kürzel aus Dateinamen im Format '(ABC) ...'
    """
    prefixes = set()
    for f in files:
        m = re.match(r"^\(([A-Za-z]{3})\)", f)
        if m:
            prefixes.add(m.group(1).upper())
    return sorted(prefixes)

def load_participants(filename: str) -> pd.DataFrame:
    """Lädt immer die aktuellste Version: bei GitHub-Setup direkt aus GitHub, sonst lokal."""
    if GITHUB_ENABLED:
        remote_bytes = github_download_file(f"participants/{filename}", GITHUB_BRANCH)
        if remote_bytes is not None:
            # lokal aktualisieren
            write_local_file(filename, remote_bytes)
            try:
                df = pd.read_csv(io.BytesIO(remote_bytes))
            except Exception:
                df = pd.read_csv(io.BytesIO(remote_bytes), encoding="latin-1")
            return ensure_cols(df)
        # Fallback lokal
        return ensure_cols(read_local_csv(filename))
    else:
        return ensure_cols(read_local_csv(filename))

def save_participants(filename: str, df: pd.DataFrame) -> None:
    """Speichert lokal + (falls aktiviert) nach GitHub."""
    csv_bytes = ensure_cols(df).to_csv(index=False).encode("utf-8")

    # lokal
    write_local_file(filename, csv_bytes)

    # GitHub
    if GITHUB_ENABLED:
        github_upload_file(
            path=f"participants/{filename}",
            content_bytes=csv_bytes,
            branch=GITHUB_BRANCH,
            commit_message=f"Save {filename} via Streamlit app",
        )

def create_list(name: str) -> str:
    filename = sanitize_filename(name) + ".csv"
    # Leere Liste anlegen
    empty_df = pd.DataFrame(columns=EXPECTED_COLS)
    save_participants(filename, empty_df)
    return filename

def delete_list(filename: str) -> None:
    # lokal
    p = path_for_list(filename)
    if os.path.exists(p):
        os.remove(p)

    # GitHub
    if GITHUB_ENABLED:
        github_delete_file(
            path=f"participants/{filename}",
            branch=GITHUB_BRANCH,
            commit_message=f"Delete {filename} via Streamlit app",
        )

# ----------------------------------------
# Team-Logik
# ----------------------------------------
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
            rows.append({"Gruppe": gi, "Name": p["Name"], "Stärke": p["Stärke (1-4)"]})
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")

# ----------------------------------------
# HAUPTBEREICH UI
# ----------------------------------------
st.title("🏆 Team- / Gruppen-Generator")

# Sidebar – Listenverwaltung
with st.sidebar:
    st.header("👥 Teilnehmerlisten")

    # 1) Verfügbare Dateien lesen
    try:
        files = list_names()

        # --- Kürzel extrahieren ---
        all_prefixes = extract_prefixes(files)

        prefix_selection = st.selectbox(
            "Filter nach Benutzer-Kürzel",
            options=["Alle"] + all_prefixes,
            index=0,
        )

        # --- Filter anwenden ---
        if prefix_selection != "Alle":
            pattern = fr"^\({prefix_selection}\)"
            files = [f for f in files if re.match(pattern, f, flags=re.IGNORECASE)]

    except Exception as e:
        st.error(f"Fehler beim Laden der Listen: {e}")
        files = []

    mapping = {f: os.path.splitext(f)[0] for f in files}
    options = list(mapping.keys())

    # 2) Pending Auswahl aus vorherigem Run übernehmen (vor Widget!)
    if "pending_file" in st.session_state:
        pf = st.session_state["pending_file"]
        del st.session_state["pending_file"]
        if pf in options:
            st.session_state["selected_file"] = pf

    # 3) Sicherstellen, dass selected_file gültig ist (vor Widget!)
    if "selected_file" not in st.session_state or st.session_state["selected_file"] not in options:
        st.session_state["selected_file"] = options[0] if options else None

    # 4) Selectbox – keine index-Übergabe, nur key, um Konflikte zu vermeiden
    selected_file = st.selectbox(
        "Liste auswählen",
        options=options,
        format_func=lambda f: mapping.get(f, f),
        key="selected_file",
    )

    # 5) Daten der gewählten Liste laden
    if selected_file:
        try:
            current_df = load_participants(selected_file)
        except Exception as e:
            st.error(f"Fehler beim Laden von {selected_file}: {e}")
            current_df = pd.DataFrame(columns=EXPECTED_COLS)
    else:
        current_df = pd.DataFrame(columns=EXPECTED_COLS)

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

        if st.button("Liste erstellen", type="primary"):
            if not new_list_name.strip():
                st.error("Bitte gültigen Listennamen eingeben.")
                st.stop()

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
            try:
                filename = sanitize_filename(new_list_name.strip()) + ".csv"
                save_participants(filename, df_new)
                st.success(f"Liste '{filename}' angelegt und gespeichert.")
                # Nach erfolgreichem Speichern: Pending-Auswahl setzen und neu laden
                st.session_state["pending_file"] = filename
                st.rerun()
            except Exception as e:
                st.error(f"Fehler beim Anlegen: {e}")

    # Aktionen
    if selected_file:
        with st.expander("⚙️ Aktionen"):
            col_left, col_right = st.columns(2)

            with col_left:
                st.download_button(
                    "📥 CSV herunterladen",
                    current_df.to_csv(index=False).encode("utf-8"),
                    file_name=selected_file,
                    mime="text/csv",
                )

            with col_right:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    current_df.to_excel(writer, index=False)
                st.download_button(
                    "📄 Excel herunterladen",
                    buf.getvalue(),
                    file_name=selected_file.replace(".csv", ".xlsx"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            # Sync: Neu von GitHub laden (überschreibt lokal)
            if GITHUB_ENABLED and st.button("🔄 Neu von GitHub laden"):
                try:
                    remote = github_download_file(f"participants/{selected_file}", GITHUB_BRANCH)
                    if remote is None:
                        st.warning("Datei in GitHub nicht gefunden.")
                    else:
                        write_local_file(selected_file, remote)
                        st.success("Neu aus GitHub geladen.")
                        st.rerun()
                except Exception as e:
                    st.error(f"GitHub-Download-Fehler: {e}")

            # Löschen
            if st.button("🗑 Liste löschen"):
                try:
                    delete_list(selected_file)
                    st.success(f"Liste '{selected_file}' gelöscht.")
                    # Auswahl neu setzen
                    remaining = list_names()
                    st.session_state["pending_file"] = remaining[0] if remaining else None
                    st.rerun()
                except Exception as e:
                    st.error(f"Löschen fehlgeschlagen: {e}")

# 1 – Teilnehmer bearbeiten
st.header("1️⃣ Teilnehmer bearbeiten")

df = ensure_cols(current_df)

edited_df = st.data_editor(
    df,
    width="stretch",
    num_rows="dynamic",
    column_config={
        "Name": st.column_config.TextColumn("Name"),
        "Stärke (1-4)": st.column_config.NumberColumn("Stärke (1-4)", min_value=1, max_value=4, step=1),
        "Abwesend": st.column_config.CheckboxColumn("Abwesend"),
    },
    key="editor_df",
)

# Speichern
if selected_file:
    if st.button("💾 Änderungen speichern", type="primary"):
        try:
            save_participants(selected_file, ensure_cols(edited_df))
            st.success("Liste gespeichert (lokal + GitHub).")
            st.rerun()
        except Exception as e:
            st.error(f"Speichern fehlgeschlagen: {e}")

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

# Optional: Debug-Infos unter Expander
with st.expander("🧪 Debug", expanded=False):
    st.write("GitHub aktiviert:", GITHUB_ENABLED)
    st.write("Repo/Branch:", GITHUB_REPO, GITHUB_BRANCH)
    st.write("Arbeitsverzeichnis:", os.getcwd())
    try:
        st.write("Lokaler participants-Inhalt:", os.listdir(PARTICIPANTS_DIR))
    except Exception as e:
        st.write("Fehler beim Lesen des lokalen Ordners:", e)