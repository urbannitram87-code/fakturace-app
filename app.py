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
            st.rerun()    st.header("Fixace agregátorů")
    
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
