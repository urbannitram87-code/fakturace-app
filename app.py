import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Fakturace - Schvalování", layout="wide")

# ==========================================
# MAPOVÁNÍ SLUŽEB A AGREGÁTORŮ
# ==========================================
SLUZBY_AGREGATORI = {
    "Audiotex": ["ATS", "T-Mobile", "Quantcom (ex. DIAL)"],
    "Premium SMS": ["ATS", "ATS (s doručenkou)", "BOKU", "ComGate Payments", "ComGate (SMS s doručenkou)", "GLOBDATA", "Comverga", "Fórum dárců"],
    "M-platba": ["Apple", "ATS", "Docomo Digital (Bango)", "Globdata", "Boku Network Services Estonia OÜ (ex Fortumo) - Tidal", "Boku Network Services Estonia OÜ (ex Fortumo) - Ostatní", "GM Europe", "Google", "Boku (Microsoft)"]
}

# Generování měsíců
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
st.sidebar.title("⚙️ Nastavení")
role = st.sidebar.selectbox("Přihlášen jako:", ["Martin Urban", "Jiří Iwonski", "Martin Čejka"])
vybrany_mesic = st.sidebar.selectbox("Fakturační měsíc:", mesice)

st.title(f"Fakturace: {vybrany_mesic}")
st.write("Vyberte službu v záložkách níže. Každý agregátor má svou vlastní přehlednou kartu.")

# --- ZJIŠTĚNÍ ALERTU (Zda jsme po termínu) ---
vybrany_m, vybrany_r = int(vybrany_mesic.split('/')[0]), int(vybrany_mesic.split('/')[1])
aktualni_m, aktualni_r = datetime.now().month, datetime.now().year
je_po_termínu = (aktualni_r > vybrany_r) or (aktualni_r == vybrany_r and aktualni_m >= vybrany_m)

# Vytvoření záložek pro služby + 1 pro historii
nazvy_sluzeb = list(SLUZBY_AGREGATORI.keys())
tabs = st.tabs(nazvy_sluzeb + ["🗂️ Celková historie"])

df_mesic = df[df["Mesic"] == vybrany_mesic].copy()

# ==========================================
# VYKRESLENÍ ZÁLOŽEK PRO JEDNOTLIVÉ SLUŽBY
# ==========================================
for i, sluzba in enumerate(nazvy_sluzeb):
    with tabs[i]:
        st.subheader(f"Přehled pro: {sluzba}")
        
        # Projdeme všechny agregátory pro danou službu
        for agregator in SLUZBY_AGREGATORI[sluzba]:
            zaznam = df_mesic[(df_mesic["Sluzba"] == sluzba) & (df_mesic["Agregator"] == agregator)]
            unikatni_klic = f"{sluzba}_{agregator}".replace(" ", "_")
            dnes = datetime.now().strftime("%d.%m.")
            
            # KARTA PRO KAŽDÉHO AGREGÁTORA (Vytvoří hezký rámeček)
            with st.container(border=True):
                
                # --- POKUD ZÁZNAM CHYBÍ (Čeká se na zadání) ---
                if zaznam.empty:
                    c1, c2, c3 = st.columns([1, 1, 1])
                    
                    # Název agregátoru (Červený, pokud je po termínu)
                    if je_po_termínu:
                        c1.markdown(f"### 🚨 :red[{agregator}]")
                        c1.caption(":red[Chybí částka za tento měsíc!]")
                    else:
                        c1.markdown(f"### {agregator}")
                        c1.caption("Čeká se na zadání...")
                    
                    # Zobrazíme formulář pro Urbana
                    if role == "Martin Urban":
                        with c2:
                            input_castka = st.number_input("Zadat částku", min_value=0.0, format="%.2f", step=100.0, key=f"castka_{unikatni_klic}")
                        with c3:
                            input_mena = st.selectbox("Měna", ["Kč", "EUR"], key=f"mena_{unikatni_klic}")
                            st.write("") # Odřádkování pro srovnání tlačítek
                            if st.button("Uložit a schválit", key=f"btn_{unikatni_klic}", type="primary", use_container_width=True):
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
                        c2.info("⏳ Čeká se, až Martin Urban zadá částku.")

                # --- POKUD ZÁZNAM EXISTUJE (Je zadáno) ---
                else:
                    row = zaznam.iloc[0]
                    id_zaznamu = str(row['ID'])
                    
                    try:
                        castka_format = f"{float(row['Castka']):,.2f} {row['Mena']}".replace(",", " ")
                    except:
                        castka_format = f"{row['Castka']} {row['Mena']}"
                    
                    # Horní řádek karty (Název a částka)
                    col_nadpis, col_castka, col_akce = st.columns([2, 2, 1])
                    col_nadpis.markdown(f"### ✅ {agregator}")
                    col_castka.markdown(f"### {castka_format}")
                    
                    # Možnost smazání (Pouze pro Urbana)
                    with col_akce:
                        if role == "Martin Urban":
                            if st.button("🗑️ Smazat / Opravit", key=f"del_{id_zaznamu}"):
                                # Odstraní záznam z tabulky
                                df = df[df['ID'] != id_zaznamu]
                                conn.update(worksheet="Data", data=df)
                                st.cache_data.clear()
                                st.rerun()

                    st.divider() # Jemná oddělovací čára v rámci karty
                    
                    # Spodní řádek karty (Schvalovací workflow)
                    s1, s2, s3 = st.columns(3)
                    
                    # Urban
                    s1.write("**Zadal (Urban):**")
                    s1.success(row['Urban'])
                    
                    # Iwonski
                    s2.write("**Schválil (Iwonski):**")
                    if row['Iwonski'] != "":
                        s2.success(row['Iwonski'])
                    else:
                        if role == "Jiří Iwonski":
                            if s2.button("Schválit za Iwonskiho", key=f"i_{id_zaznamu}", type="primary"):
                                df.loc[df['ID'] == id_zaznamu, 'Iwonski'] = f"Jiw ({dnes})"
                                conn.update(worksheet="Data", data=df)
                                st.cache_data.clear()
                                st.rerun()
                        else:
                            s2.warning("⏳ Čeká na Iwonskiho")
                            
                    # Čejka
                    s3.write("**Schválil (Čejka):**")
                    if row['Cejka'] != "":
                        s3.success(row['Cejka'])
                    else:
                        if role == "Martin Čejka":
                            if row['Iwonski'] != "":
                                if s3.button("Finálně schválit (Čejka)", key=f"c_{id_zaznamu}", type="primary"):
                                    df.loc[df['ID'] == id_zaznamu, 'Cejka'] = f"Martin ({dnes})"
                                    conn.update(worksheet="Data", data=df)
                                    st.cache_data.clear()
                                    st.rerun()
                            else:
                                s3.warning("⏳ Čeká na Iwonskiho")
                        else:
                            if row['Iwonski'] == "":
                                s3.write("⏳ Zablokováno (Čeká na předchozí)")
                            else:
                                s3.warning("⏳ Čeká na Čejku")

# ==========================================
# ZÁLOŽKA HISTORIE
# ==========================================
with tabs[-1]:
    st.subheader("🗂️ Kompletní historie fakturací")
    if df.empty:
        st.info("Databáze je zatím prázdná.")
    else:
        df_zobrazeni = df.drop(columns=["ID"])
        st.dataframe(df_zobrazeni, use_container_width=True, hide_index=True)
