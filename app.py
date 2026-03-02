import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Fakturace - Schvalování", layout="wide")

# ==========================================
# MAPOVÁNÍ SLUŽEB A AGREGÁTORŮ (Dle vašeho zadání)
# ==========================================
SLUZBY_AGREGATORI = {
    "Audiotex": [
        "ATS", "T-Mobile", "Quantcom (ex. DIAL)"
    ],
    "Premium SMS": [
        "ATS", "ATS (s doručenkou)", "BOKU", "ComGate Payments", 
        "ComGate (SMS s doručenkou)", "GLOBDATA", "Comverga", "Fórum dárců"
    ],
    "M-platba": [
        "Apple", "ATS", "Docomo Digital (Bango)", "Globdata", 
        "Boku Network Services Estonia OÜ (ex Fortumo) - Tidal", 
        "Boku Network Services Estonia OÜ (ex Fortumo) - Ostatní", 
        "GM Europe", "Google", "Boku (Microsoft)"
    ]
}

# Generování měsíců (od 02/2026 do konce roku 2027)
mesice = [f"{m:02d}/2026" for m in range(2, 13)] + [f"{m:02d}/2027" for m in range(1, 13)]

# --- PŘIPOJENÍ A NAČTENÍ DAT ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        df = conn.read(worksheet="Data", usecols=list(range(9)))
        if df.empty or "ID" not in df.columns:
            return pd.DataFrame(columns=["ID", "Mesic", "Sluzba", "Agregator", "Castka", "Mena", "Urban", "Iwonski", "Cejka"])
        
        df = df.fillna("")
        df['ID'] = df['ID'].astype(str)
        return df
    except Exception:
        return pd.DataFrame(columns=["ID", "Mesic", "Sluzba", "Agregator", "Castka", "Mena", "Urban", "Iwonski", "Cejka"])

df = load_data()

# --- POSTRANNÍ PANEL ---
st.sidebar.title("Nastavení")
role = st.sidebar.selectbox("Kdo právě schvaluje:", ["Martin Urban", "Jiří Iwonski", "Martin Čejka"])
vybrany_mesic = st.sidebar.selectbox("Vyberte měsíc pro schvalování:", mesice)

st.title(f"Fakturace")

# Rozdělení do záložek
tab_schvalovani, tab_historie = st.tabs(["Schvalování: " + vybrany_mesic, "Celková historie a přehled"])

# ==========================================
# ZÁLOŽKA 1: SCHVALOVÁNÍ (Aktuální měsíc)
# ==========================================
with tab_schvalovani:
    
    # PŘIDÁVÁNÍ NOVÝCH FAKTUR (Zobrazí se jen Urbanovi)
    if role == "Martin Urban":
        with st.expander("➕ Přidat novou položku k vybranému měsíci", expanded=False):
            # Pro dynamické načítání nepoužíváme st.form, ale obyčejné sloupce
            col1, col2 = st.columns(2)
            sluzba = col1.selectbox("Vyberte službu", list(SLUZBY_AGREGATORI.keys()))
            agregator = col2.selectbox("Vyberte agregátor", SLUZBY_AGREGATORI[sluzba])
            
            col3, col4 = st.columns(2)
            castka = col3.number_input("Částka", min_value=0.0, format="%.2f", step=100.0)
            mena = col4.selectbox("Měna", ["Kč", "EUR"])
            
            if st.button("Vytvořit položku ke schválení", type="primary"):
                nove_id = str(datetime.now().timestamp())
                
                novy_zaznam = pd.DataFrame([{
                    "ID": nove_id, "Mesic": vybrany_mesic, "Sluzba": sluzba, "Agregator": agregator,
                    "Castka": castka, "Mena": mena, "Urban": "", "Iwonski": "", "Cejka": ""
                }])
                
                df = pd.concat([df, novy_zaznam], ignore_index=True)
                conn.update(worksheet="Data", data=df)
                st.cache_data.clear()
                st.success(f"Položka {agregator} ({castka} {mena}) byla úspěšně přidána!")
                st.rerun()

    st.divider()
    st.subheader(f"Položky ke schválení za {vybrany_mesic}")

    # Filtrace dat jen pro aktuální měsíc
    df_mesic = df[df["Mesic"] == vybrany_mesic].copy()

    if df_mesic.empty:
        st.info("V tomto měsíci zatím nejsou zadány žádné faktury.")
    else:
        # Hlavička pro náš seznam
        h1, h2, h3, h4, h5, h6 = st.columns([2, 2, 1.5, 1.5, 1.5, 1.5])
        h1.write("**Služba / Agregátor**")
        h2.write("**Částka**")
        h3.write("**Martin Urban**")
        h4.write("**Jiří Iwonski**")
        h5.write("**Martin Čejka**")
        h6.write("**Akce**")
        st.markdown("---")

        # Vykreslení každého řádku zvlášť
        for index, row in df_mesic.iterrows():
            c1, c2, c3, c4, c5, c6 = st.columns([2, 2, 1.5, 1.5, 1.5, 1.5])
            
            c1.write(f"**{row['Sluzba']}**\n\n*( {row['Agregator']} )*")
            # Bezpečné formátování částky
            try:
                castka_format = f"{float(row['Castka']):,.2f} {row['Mena']}".replace(",", " ")
            except:
                castka_format = f"{row['Castka']} {row['Mena']}"
                
            c2.write(f"**{castka_format}**")
            
            c3.write("✅ " + row['Urban'] if row['Urban'] != "" else "⏳ Čeká")
            c4.write("✅ " + row['Iwonski'] if row['Iwonski'] != "" else "⏳ Čeká")
            c5.write("✅ " + row['Cejka'] if row['Cejka'] != "" else "⏳ Čeká")
            
            dnes = datetime.now().strftime("%d.%m.")
            id_zaznamu = str(row['ID'])
            
            # Tlačítka podle rolí
            with c6:
                if role == "Martin Urban":
                    if row['Urban'] == "":
                        if st.button("Schválit", key=f"u_{id_zaznamu}"):
                            df.loc[df['ID'] == id_zaznamu, 'Urban'] = f"Urban ({dnes})"
                            conn.update(worksheet="Data", data=df)
                            st.cache_data.clear()
                            st.rerun()
                    else:
                        st.write("Hotovo")
                        
                elif role == "Jiří Iwonski":
                    if row['Urban'] != "" and row['Iwonski'] == "":
                        if st.button("Schválit", key=f"i_{id_zaznamu}"):
                            df.loc[df['ID'] == id_zaznamu, 'Iwonski'] = f"Jiw ({dnes})"
                            conn.update(worksheet="Data", data=df)
                            st.cache_data.clear()
                            st.rerun()
                    elif row['Iwonski'] != "":
                        st.write("Hotovo")
                    else:
                        st.write("Čeká na Urbana")
                        
                elif role == "Martin Čejka":
                    if row['Iwonski'] != "" and row['Cejka'] == "":
                        if st.button("Schválit", key=f"c_{id_zaznamu}", type="primary"):
                            df.loc[df['ID'] == id_zaznamu, 'Cejka'] = f"Martin ({dnes})"
                            conn.update(worksheet="Data", data=df)
                            st.cache_data.clear()
                            st.rerun()
                    elif row['Cejka'] != "":
                        st.write("Schváleno 🎉")
                    else:
                        st.write("Čeká na kolegy")
            
            st.markdown("---")

# ==========================================
# ZÁLOŽKA 2: HISTORIE
# ==========================================
with tab_historie:
    st.subheader("Kompletní historie fakturací")
    st.write("Zde vidíte všechny zadané a schválené položky napříč všemi měsíci.")
    
    if df.empty:
        st.info("Databáze je zatím prázdná.")
    else:
        # Skryjeme sloupec ID, aby tabulka vypadala čistěji
        df_zobrazeni = df.drop(columns=["ID"])
        st.dataframe(df_zobrazeni, use_container_width=True, hide_index=True)
