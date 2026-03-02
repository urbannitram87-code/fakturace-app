import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Fakturace - Schvalování", layout="wide")

# ==========================================
# VAŠE MAPOVÁNÍ SLUŽEB A AGREGÁTORŮ
# (Sem můžete přepsat svůj reálný seznam)
# ==========================================
MAPOVANI = {
    "Premium SMS": "ATS",
    "Premium SMS (s doručenkou)": "ATS (s doručenkou)",
    "M-platba": "BOKU",
    "Audiotex": "ComGate Payments",
    "SMS (s doručenkou)": "ComGate (SMS s doručenkou)",
    "Hlasové služby": "GLOBDATA",
    "Ostatní služby": "Comverga",
    "Dárcovské SMS": "Fórum dárců"
}

# Generování měsíců (od 02/2026 do konce roku 2027)
mesice = [f"{m:02d}/2026" for m in range(2, 13)] + [f"{m:02d}/2027" for m in range(1, 13)]

# --- PŘIPOJENÍ ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        df = conn.read(worksheet="Data", usecols=list(range(9)))
        if df.empty or "ID" not in df.columns:
            return pd.DataFrame(columns=["ID", "Mesic", "Sluzba", "Agregator", "Castka", "Mena", "Urban", "Iwonski", "Cejka"])
        
        # Ošetření prázdných hodnot (NaN) na prázdný text
        df = df.fillna("")
        # Zajištění, že ID je vždy text (aby fungovalo porovnávání)
        df['ID'] = df['ID'].astype(str)
        return df
    except Exception as e:
        return pd.DataFrame(columns=["ID", "Mesic", "Sluzba", "Agregator", "Castka", "Mena", "Urban", "Iwonski", "Cejka"])

df = load_data()

# --- POSTRANNÍ PANEL ---
st.sidebar.title("Nastavení")
role = st.sidebar.selectbox("Kdo právě schvaluje:", ["Martin Urban", "Jiří Iwonski", "Martin Čejka"])
vybrany_mesic = st.sidebar.selectbox("Vyberte měsíc:", mesice)

st.title(f"Přehled pro měsíc: {vybrany_mesic}")

# ==========================================
# 1. PŘIDÁVÁNÍ NOVÝCH FAKTUR (Jen Urban)
# ==========================================
if role == "Martin Urban":
    with st.expander("➕ Přidat novou fakturu k vybranému měsíci", expanded=False):
        with st.form("nova_faktura"):
            col1, col2, col3 = st.columns([2, 1, 1])
            sluzba = col1.selectbox("Služba (Agregátor se doplní sám)", list(MAPOVANI.keys()))
            castka = col2.number_input("Částka", min_value=0.0, format="%.2f", step=100.0)
            mena = col3.selectbox("Měna", ["Kč", "EUR"])
            
            if st.form_submit_button("Vytvořit položku"):
                nove_id = str(datetime.now().timestamp()) # Vytvoří unikátní ID z aktuálního času
                agregator = MAPOVANI[sluzba]
                
                novy_zaznam = pd.DataFrame([{
                    "ID": nove_id,
                    "Mesic": vybrany_mesic,
                    "Sluzba": sluzba,
                    "Agregator": agregator,
                    "Castka": castka,
                    "Mena": mena,
                    "Urban": "",
                    "Iwonski": "",
                    "Cejka": ""
                }])
                
                df = pd.concat([df, novy_zaznam], ignore_index=True)
                conn.update(worksheet="Data", data=df)
                st.cache_data.clear()
                st.success(f"Položka {sluzba} ({castka} {mena}) přidána!")
                st.rerun()

st.divider()
st.subheader("Položky ke schválení")

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
        
        # 1. a 2. Sloupec: Informace o faktuře
        c1.write(f"**{row['Sluzba']}**\n\n*( {row['Agregator']} )*")
        c2.write(f"**{float(row['Castka']):,.2f} {row['Mena']}**")
        
        # 3. až 5. Sloupec: Statusy schvalovatelů
        c3.write("✅ " + row['Urban'] if row['Urban'] != "" else "⏳ Čeká")
        c4.write("✅ " + row['Iwonski'] if row['Iwonski'] != "" else "⏳ Čeká")
        c5.write("✅ " + row['Cejka'] if row['Cejka'] != "" else "⏳ Čeká")
        
        # 6. Sloupec: Tlačítka (Zobrazí se jen tomu, kdo je na řadě)
        dnes = datetime.now().strftime("%d.%m.")
        id_zaznamu = str(row['ID'])
        
        with c6:
            if role == "Martin Urban":
                if row['Urban'] == "":
                    if st.button("Schválit (Urban)", key=f"u_{id_zaznamu}"):
                        df.loc[df['ID'] == id_zaznamu, 'Urban'] = f"Urban ({dnes})"
                        conn.update(worksheet="Data", data=df)
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.write("Schváleno")
                    
            elif role == "Jiří Iwonski":
                if row['Urban'] != "" and row['Iwonski'] == "":
                    if st.button("Schválit (Jiw)", key=f"i_{id_zaznamu}"):
                        df.loc[df['ID'] == id_zaznamu, 'Iwonski'] = f"Jiw ({dnes})"
                        conn.update(worksheet="Data", data=df)
                        st.cache_data.clear()
                        st.rerun()
                elif row['Iwonski'] != "":
                    st.write("Schváleno")
                else:
                    st.write("Čeká na M. Urbana")
                    
            elif role == "Martin Čejka":
                if row['Iwonski'] != "" and row['Cejka'] == "":
                    if st.button("Schválit (Martin)", key=f"c_{id_zaznamu}", type="primary"):
                        df.loc[df['ID'] == id_zaznamu, 'Cejka'] = f"Martin ({dnes})"
                        conn.update(worksheet="Data", data=df)
                        st.cache_data.clear()
                        st.rerun()
                elif row['Cejka'] != "":
                    st.write("Plně schváleno 🎉")
                else:
                    st.write("Čeká na kolegy")
        
        st.markdown("---") # Oddělovač mezi řádky# Filtrace dat jen pro aktuální vybraný měsíc
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
