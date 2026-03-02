import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Fakturace - Schvalování", layout="wide")

# ==========================================
# MAPOVÁNÍ SLUŽEB A AGREGÁTORŮ
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

st.title(f"Fakturace: {vybrany_mesic}")

tab_schvalovani, tab_historie = st.tabs(["Položky ke schválení", "Celková historie"])

# ==========================================
# ZÁLOŽKA 1: SCHVALOVÁNÍ (Checklist)
# ==========================================
with tab_schvalovani:
    st.write("Zde je seznam všech očekávaných faktur pro tento měsíc.")
    
    # Zjištění, zda už je konec měsíce (pro červený alert)
    # Převedeme vybraný měsíc a aktuální čas na porovnatelný formát
    vybrany_m, vybrany_r = int(vybrany_mesic.split('/')[0]), int(vybrany_mesic.split('/')[1])
    aktualni_m, aktualni_r = datetime.now().month, datetime.now().year
    
    # Alert se ukáže, pokud jsme v aktuálním měsíci (nebo starším) a chybí data
    je_po_termínu = (aktualni_r > vybrany_r) or (aktualni_r == vybrany_r and aktualni_m >= vybrany_m)

    df_mesic = df[df["Mesic"] == vybrany_mesic].copy()

    # Hlavička tabulky
    h1, h2, h3, h4, h5, h6 = st.columns([2.5, 2, 1.5, 1.5, 1.5, 1.5])
    h1.write("**Služba / Agregátor**")
    h2.write("**Částka a Měna**")
    h3.write("**Martin Urban**")
    h4.write("**Jiří Iwonski**")
    h5.write("**Martin Čejka**")
    h6.write("**Akce**")
    st.markdown("---")

    # Procházíme natvrdo VŠECHNY služby a agregátory podle vašeho seznamu
    for sluzba, agregatori in SLUZBY_AGREGATORI.items():
        for agregator in agregatori:
            # Zkusíme najít, jestli už k této kombinaci pro daný měsíc existuje záznam
            zaznam = df_mesic[(df_mesic["Sluzba"] == sluzba) & (df_mesic["Agregator"] == agregator)]
            
            unikatni_klic = f"{sluzba}_{agregator}".replace(" ", "_")
            dnes = datetime.now().strftime("%d.%m.")
            
            c1, c2, c3, c4, c5, c6 = st.columns([2.5, 2, 1.5, 1.5, 1.5, 1.5])
            
            # --- POKUD ZÁZNAM CHYBÍ (Ještě nebylo zadáno) ---
            if zaznam.empty:
                # Nastavení červeného alertu, pokud chybí vyplnění a už by mělo být
                if je_po_termínu:
                    c1.markdown(f"**:red[🚨 {sluzba}]**\n\n**:red[*( {agregator} )*]**")
                else:
                    c1.write(f"**{sluzba}**\n\n*( {agregator} )*")
                
                if role == "Martin Urban":
                    # Urban vidí políčka pro zadání
                    with c2:
                        input_castka = st.number_input("Částka", min_value=0.0, format="%.2f", step=100.0, key=f"castka_{unikatni_klic}", label_visibility="collapsed")
                        input_mena = st.selectbox("Měna", ["Kč", "EUR"], key=f"mena_{unikatni_klic}", label_visibility="collapsed")
                    
                    c3.write("⏳ Čeká na zadání")
                    c4.write("⏳")
                    c5.write("⏳")
                    
                    with c6:
                        if st.button("Schválit", key=f"btn_{unikatni_klic}", type="primary"):
                            nove_id = str(datetime.now().timestamp())
                            novy_zaznam = pd.DataFrame([{
                                "ID": nove_id, "Mesic": vybrany_mesic, "Sluzba": sluzba, "Agregator": agregator,
                                "Castka": input_castka, "Mena": input_mena, 
                                "Urban": f"Urban ({dnes})", "Iwonski": "", "Cejka": ""
                            }])
                            df = pd.concat([df, novy_zaznam], ignore_index=True)
                            conn.update(worksheet="Data", data=df)
                            st.cache_data.clear()
                            st.rerun()
                else:
                    # Ostatní role jen vidí, že se čeká na Urbana
                    c2.write("---")
                    c3.write("⏳ Čeká na M. Urbana")
                    c4.write("⏳")
                    c5.write("⏳")
                    c6.write("")

            # --- POKUD ZÁZNAM EXISTUJE (Už někdo zadal částku) ---
            else:
                row = zaznam.iloc[0]
                id_zaznamu = str(row['ID'])
                
                c1.write(f"**{row['Sluzba']}**\n\n*( {row['Agregator']} )*")
                
                try:
                    castka_format = f"{float(row['Castka']):,.2f} {row['Mena']}".replace(",", " ")
                except:
                    castka_format = f"{row['Castka']} {row['Mena']}"
                c2.write(f"**{castka_format}**")
                
                c3.write("✅ " + row['Urban'] if row['Urban'] != "" else "⏳ Čeká")
                c4.write("✅ " + row['Iwonski'] if row['Iwonski'] != "" else "⏳ Čeká")
                c5.write("✅ " + row['Cejka'] if row['Cejka'] != "" else "⏳ Čeká")
                
                # Tlačítka pro další role
                with c6:
                    if role == "Martin Urban":
                        st.write("Hotovo")
                            
                    elif role == "Jiří Iwonski":
                        if row['Iwonski'] == "":
                            if st.button("Schválit", key=f"i_{id_zaznamu}", type="primary"):
                                df.loc[df['ID'] == id_zaznamu, 'Iwonski'] = f"Jiw ({dnes})"
                                conn.update(worksheet="Data", data=df)
                                st.cache_data.clear()
                                st.rerun()
                        else:
                            st.write("Hotovo")
                            
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
                            
            st.markdown("---") # Oddělovač řádků

# ==========================================
# ZÁLOŽKA 2: HISTORIE
# ==========================================
with tab_historie:
    st.subheader("Kompletní historie fakturací")
    if df.empty:
        st.info("Databáze je zatím prázdná.")
    else:
        df_zobrazeni = df.drop(columns=["ID"])
        st.dataframe(df_zobrazeni, use_container_width=True, hide_index=True)
