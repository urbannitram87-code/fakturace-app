import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Fakturace - Excel Zobrazení", layout="wide")

# --- PŘIPOJENÍ ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNKCE PRO NAČTENÍ DAT ---
@st.cache_data(ttl=5) # Nová data se stahují každých 5 vteřin
def load_data():
    try:
        df = conn.read(worksheet="Data", usecols=[0,1,2,3,4,5])
        if df.empty or "Mesic" not in df.columns:
            return pd.DataFrame(columns=["Mesic", "Agregator", "Castka", "Urban", "Iwonski", "Cejka"])
        return df.dropna(how="all")
    except:
        return pd.DataFrame(columns=["Mesic", "Agregator", "Castka", "Urban", "Iwonski", "Cejka"])

df = load_data()

# --- VÝCHOZÍ SEZNAM (přesně podle vašeho screenshotu) ---
VYCHOZI_AGREGATORI = [
    "ATS", "ATS (s doručenkou)", "BOKU", "ComGate Payments", 
    "ComGate (SMS s doručenkou)", "GLOBDATA", "Comverga", "Fórum dárců"
]

# --- POSTRANNÍ PANEL ---
st.sidebar.title("Nastavení")
role = st.sidebar.selectbox("Kdo právě schvaluje:", ["Martin Urban", "Jiří Iwonski", "Martin Čejka"])
mesic = st.sidebar.text_input("Zadejte měsíc (např. I.2026)", value="I.2026")

st.title(f"Přehled fakturace: {mesic}")

# Filtrace dat jen pro aktuální vybraný měsíc
df_mesic = df[df["Mesic"] == mesic].copy()

# ==========================================
# 1. ZADÁVÁNÍ (MARTIN URBAN)
# ==========================================
if role == "Martin Urban":
    st.info("💡 Zadejte částky přímo do tabulky jako v Excelu. Můžete libovolně přepisovat částky. Až budete hotov, klikněte dole na Uložit.")
    
    if df_mesic.empty:
        # Předvyplníme tabulku vašimi agregátory, pokud je pro daný měsíc zatím prázdná
        df_mesic = pd.DataFrame({
            "Mesic": mesic,
            "Agregator": VYCHOZI_AGREGATORI,
            "Castka": 0.0,
            "Urban": "", "Iwonski": "", "Cejka": ""
        })
        
    # Interaktivní "Excel" tabulka přímo ve Streamlitu
    upravena_tabulka = st.data_editor(
        df_mesic,
        column_config={
            "Mesic": st.column_config.TextColumn("Měsíc", disabled=True),
            "Agregator": st.column_config.TextColumn("Agregátor (služba)"),
            "Castka": st.column_config.NumberColumn("Částka (Kč)", format="%.2f", step=100.0),
            "Urban": st.column_config.TextColumn("Zadal (Urban)", disabled=True),
            "Iwonski": st.column_config.TextColumn("Schválil (Iwonski)", disabled=True),
            "Cejka": st.column_config.TextColumn("Schválil (Čejka)", disabled=True),
        },
        hide_index=True,
        num_rows="dynamic", # Umožňuje přidat další řádek, pokud by přibyl agregátor
        use_container_width=True
    )
    
    if st.button("Uložit a potvrdit částky", type="primary"):
        dnes = datetime.now().strftime("%d.%m.%Y")
        # Zapíše k částkám vaše jméno a dnešní datum
        mask = (upravena_tabulka["Castka"] > 0) & (upravena_tabulka["Urban"] == "")
        upravena_tabulka.loc[mask, "Urban"] = f"Urban ({dnes})"
        
        # Nahradí stará data pro tento měsíc novými a odešle do cloudu
        df_ostatni = df[df["Mesic"] != mesic]
        df_vysledek = pd.concat([df_ostatni, upravena_tabulka], ignore_index=True)
        conn.update(worksheet="Data", data=df_vysledek)
        st.cache_data.clear()
        st.success("Uloženo! Data se propsala do Google Tabulky.")
        st.rerun()

# ==========================================
# 2. SCHVALOVÁNÍ (IWONSKI)
# ==========================================
elif role == "Jiří Iwonski":
    st.dataframe(df_mesic, hide_index=True, use_container_width=True)
    
    if not df_mesic.empty:
        if st.button("Schválit vše za měsíc " + mesic, type="primary"):
            dnes = datetime.now().strftime("%d.%m.")
            # Schválí vše, co už Urban zadal
            mask = (df["Mesic"] == mesic) & (df["Urban"] != "") & (df["Iwonski"] == "")
            df.loc[mask, "Iwonski"] = f"Jiw ({dnes})"
            conn.update(worksheet="Data", data=df)
            st.cache_data.clear()
            st.success("Vše úspěšně schváleno!")
            st.rerun()

# ==========================================
# 3. SCHVALOVÁNÍ (ČEJKA)
# ==========================================
elif role == "Martin Čejka":
    st.dataframe(df_mesic, hide_index=True, use_container_width=True)
    
    if not df_mesic.empty:
        if st.button("Finálně schválit za " + mesic, type="primary"):
            dnes = datetime.now().strftime("%d.%m.")
            # Schválí vše, co už prošlo přes Iwonskiho
            mask = (df["Mesic"] == mesic) & (df["Iwonski"] != "") & (df["Cejka"] == "")
            df.loc[mask, "Cejka"] = f"Martin ({dnes})"
            conn.update(worksheet="Data", data=df)
            st.cache_data.clear()
            st.success("Finálně schváleno!")
            st.rerun()
