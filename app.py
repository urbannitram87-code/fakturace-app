import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Schvalování Faktur", layout="wide")

# Připojení ke Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Funkce pro načtení a zápis dat
def get_data(worksheet):
    return conn.read(worksheet=worksheet, usecols=list(range(10)))

def update_data(worksheet, df):
    conn.update(worksheet=worksheet, data=df)

# Postranní panel
st.sidebar.title("Nastavení uživatele")
role = st.sidebar.selectbox("Přihlášen jako:", ["Martin Urban", "Jiří Iwonski", "Martin Čejka", "Admin/Zápis"])

st.title("Systém pro schvalování faktur (Online)")
tab1, tab2, tab3 = st.tabs(["Schvalování faktur", "Nová faktura", "Nastavení agregátorů"])

sluzby = ["Premium SMS", "Audiotex", "M-platba"]

# Načtení aktuálních dat
try:
    df_agregatory = get_data("Agregatory").dropna(how="all")
    df_faktury = get_data("Faktury").dropna(how="all")
except:
    st.error("Chyba načítání dat. Zkontrolujte připojení ke Google Tabulce.")
    st.stop()

# --- TAB 3: AGREGÁTORY ---
with tab3:
    st.header("Fixace agregátorů")
    
    # Převedení df na slovník pro snazší zobrazení
    agg_dict = dict(zip(df_agregatory['Sluzba'], df_agregatory['Agregator'])) if not df_agregatory.empty else {}
    
    with st.form("agg_form"):
        ag_psms = st.text_input("Premium SMS", value=agg_dict.get("Premium SMS", ""))
        ag_audiotex = st.text_input("Audiotex", value=agg_dict.get("Audiotex", ""))
        ag_mplatba = st.text_input("M-platba", value=agg_dict.get("M-platba", ""))
        
        if st.form_submit_button("Uložit agregátory"):
            nove_agregatory = pd.DataFrame({
                "Sluzba": ["Premium SMS", "Audiotex", "M-platba"],
                "Agregator": [ag_psms, ag_audiotex, ag_mplatba]
            })
            update_data("Agregatory", nove_agregatory)
            st.success("Uloženo! Stránka se obnoví.")
            st.rerun()

# --- TAB 2: NOVÁ FAKTURA ---
with tab2:
    st.header("Zadání faktury")
    if len(agg_dict) < 3:
        st.warning("Nejprve uložte agregátory v záložce Nastavení.")
    else:
        with st.form("inv_form"):
            mesic = st.date_input("Měsíc (jakýkoliv den v měsíci)").strftime("%Y-%m")
            sluzba = st.selectbox("Služba", sluzby)
            castka = st.number_input("Částka", min_value=0.0, format="%.2f")
            mena = st.selectbox("Měna", ["Kč", "EUR"])
            
            if st.form_submit_button("Vytvořit záznam"):
                nove_id = 1 if df_faktury.empty else int(df_faktury['ID'].max()) + 1
                agregator = agg_dict.get(sluzba, "Neznámý")
                
                novy_zaznam = pd.DataFrame([{
                    "ID": nove_id, "Mesic": mesic, "Sluzba": sluzba, "Agregator": agregator,
                    "Castka": castka, "Mena": mena, "Status": "Čeká na M. Urbana",
                    "Urban_cas": "", "Iwonski_cas": "", "Cejka_cas": ""
                }])
                
                df_faktury = pd.concat([df_faktury, novy_zaznam], ignore_index=True)
                update_data("Faktury", df_faktury)
                st.success("Faktura přidána!")
                st.rerun()

# --- TAB 1: SCHVALOVÁNÍ ---
with tab1:
    st.header("Přehled a schvalování")
    if df_faktury.empty:
        st.info("Zatím zde nejsou žádné faktury.")
    else:
        st.dataframe(df_faktury, use_container_width=True)
        st.divider()
        st.subheader("Akce ke schválení")
        
        for index, row in df_faktury.iterrows():
            status = row['Status']
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Zobrazíme jen to, co čeká na akci
            if status != "Plně schváleno":
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**ID {row['ID']} | {row['Mesic']} | {row['Sluzba']}** - {row['Castka']} {row['Mena']} ({status})")
                
                with col2:
                    if role == "Martin Urban" and status == "Čeká na M. Urbana":
                        if st.button("Schválit (Urban)", key=f"u_{row['ID']}"):
                            df_faktury.at[index, 'Urban_cas'] = now_str
                            df_faktury.at[index, 'Status'] = 'Čeká na J. Iwonskiho'
                            update_data("Faktury", df_faktury)
                            st.rerun()
                            
                    elif role == "Jiří Iwonski" and status == "Čeká na J. Iwonskiho":
                        if st.button("Schválit (Iwonski)", key=f"i_{row['ID']}"):
                            df_faktury.at[index, 'Iwonski_cas'] = now_str
                            df_faktury.at[index, 'Status'] = 'Čeká na M. Čejku'
                            update_data("Faktury", df_faktury)
                            st.rerun()
                            
                    elif role == "Martin Čejka" and status == "Čeká na M. Čejku":
                        if st.button("Schválit (Čejka)", key=f"c_{row['ID']}"):
                            df_faktury.at[index, 'Cejka_cas'] = now_str
                            df_faktury.at[index, 'Status'] = 'Plně schváleno'
                            update_data("Faktury", df_faktury)
                            st.rerun()