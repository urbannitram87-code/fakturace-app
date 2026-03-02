import streamlit as st
import pandas as pd
from datetime import datetime
import urllib.parse
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

# Reálné e-maily kolegů z O2
EMAIL_IWONSKI = "jiri.iwonski@o2.cz"
EMAIL_CEJKA = "martin.cejka@o2.cz"

mesice = [f"{m:02d}/2026" for m in range(2, 13)] + [f"{m:02d}/2027" for m in range(1, 13)]

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

# Funkce pro výpočet dní od schválení předchozím (např. z textu "Urban (17.02.)")
def zpozdeni_dnu(text_statusu):
    if not text_statusu or "(" not in text_statusu: return 0
    try:
        datum_str = text_statusu.split("(")[1].replace(")", "") + str(datetime.now().year)
        datum_schvaleni = datetime.strptime(datum_str, "%d.%m.%Y")
        return (datetime.now() - datum_schvaleni).days
    except:
        return 0

# --- POSTRANNÍ PANEL ---
st.sidebar.title("⚙️ Nastavení")
role = st.sidebar.selectbox("Přihlášen jako:", ["Martin Urban", "Jiří Iwonski", "Martin Čejka"])
vybrany_mesic = st.sidebar.selectbox("Fakturační měsíc:", mesice)

st.title(f"Fakturace: {vybrany_mesic}")

# --- LOGIKA ALERTU (25. den NÁSLEDUJÍCÍHO měsíce) ---
vybrany_m, vybrany_r = int(vybrany_mesic.split('/')[0]), int(vybrany_mesic.split('/')[1])
# Posuneme měsíc o 1 dopředu (ošetření přelomu roku)
deadline_m = 1 if vybrany_m == 12 else vybrany_m + 1
deadline_r = vybrany_r + 1 if vybrany_m == 12 else vybrany_r
deadline_datum = datetime(deadline_r, deadline_m, 25)

je_po_termínu = datetime.now() > deadline_datum

nazvy_sluzeb = list(SLUZBY_AGREGATORI.keys())
tabs = st.tabs(nazvy_sluzeb + ["🗂️ Celková historie"])
df_mesic = df[df["Mesic"] == vybrany_mesic].copy()

# ==========================================
# VYKRESLENÍ ZÁLOŽEK
# ==========================================
for i, sluzba in enumerate(nazvy_sluzeb):
    with tabs[i]:
        st.subheader(f"Přehled pro: {sluzba}")
        
        for agregator in SLUZBY_AGREGATORI[sluzba]:
            zaznam = df_mesic[(df_mesic["Sluzba"] == sluzba) & (df_mesic["Agregator"] == agregator)]
            unikatni_klic = f"{sluzba}_{agregator}".replace(" ", "_")
            dnes = datetime.now().strftime("%d.%m.")
            
            with st.container(border=True):
                # --- CHYBÍ ZADÁNÍ ---
                if zaznam.empty:
                    c1, c2, c3 = st.columns([1, 1, 1])
                    if je_po_termínu:
                        c1.markdown(f"### 🚨 :red[{agregator}]")
                        c1.caption(f":red[Chybí částka! Termín byl 25.{deadline_m:02d}.]")
                    else:
                        c1.markdown(f"### {agregator}")
                        c1.caption("Čeká se na zadání...")
                    
                    if role == "Martin Urban":
                        with c2:
                            input_castka = st.number_input("Zadat částku", min_value=0.0, format="%.2f", step=100.0, key=f"castka_{unikatni_klic}")
                        with c3:
                            input_mena = st.selectbox("Měna", ["Kč", "EUR"], key=f"mena_{unikatni_klic}")
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
                        c2.info("⏳ Čeká se na Martina Urbana")

                # --- JE ZADÁNO ---
                else:
                    row = zaznam.iloc[0]
                    id_zaznamu = str(row['ID'])
                    castka_format = f"{float(row['Castka']):,.2f} {row['Mena']}".replace(",", " ") if row['Castka'] else ""
                    
                    col_nadpis, col_castka, col_akce = st.columns([2, 2, 1])
                    col_nadpis.markdown(f"### ✅ {agregator}")
                    col_castka.markdown(f"### {castka_format}")
                    
                    with col_akce:
                        if role == "Martin Urban":
                            if st.button("🗑️ Smazat/Opravit", key=f"del_{id_zaznamu}"):
                                df = df[df['ID'] != id_zaznamu]
                                conn.update(worksheet="Data", data=df)
                                st.cache_data.clear()
                                st.rerun()

                    st.divider()
                    s1, s2, s3 = st.columns(3)
                    
                    # 1. URBAN
                    s1.write("**Zadal (Urban):**")
                    s1.success(row['Urban'])
                    
                    # 2. IWONSKI
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
                            dny_cekani = zpozdeni_dnu(row['Urban'])
                            if dny_cekani >= 5:
                                s2.error(f"⏳ Čeká na Iwonskiho ({dny_cekani} dní)")
                                # Předvyplněný e-mail
                                predmet = urllib.parse.quote(f"Urgence schválení: {agregator} za {vybrany_mesic}")
                                telo = urllib.parse.quote(f"Ahoj Jiří,\n\nprosím tě o schválení částky {castka_format} pro {agregator} v naší schvalovací aplikaci.\n\nDíky, Martin")
                                s2.link_button("✉️ Poslat urgenci", f"mailto:{EMAIL_IWONSKI}?subject={predmet}&body={telo}")
                            else:
                                s2.warning(f"⏳ Čeká na Iwonskiho")
                            
                    # 3. ČEJKA
                    s3.write("**Schválil (Čejka):**")
                    if row['Cejka'] != "":
                        s3.success(row['Cejka'])
                    else:
                        if role == "Martin Čejka":
                            if row['Iwonski'] != "":
                                if s3.button("Finálně schválit", key=f"c_{id_zaznamu}", type="primary"):
                                    df.loc[df['ID'] == id_zaznamu, 'Cejka'] = f"Martin ({dnes})"
                                    conn.update(worksheet="Data", data=df)
                                    st.cache_data.clear()
                                    st.rerun()
                            else:
                                s3.warning("⏳ Čeká na Iwonskiho")
                        else:
                            if row['Iwonski'] != "":
                                dny_cekani = zpozdeni_dnu(row['Iwonski'])
                                if dny_cekani >= 5:
                                    s3.error(f"⏳ Čeká na Čejku ({dny_cekani} dní)")
                                    predmet = urllib.parse.quote(f"Urgence schválení: {agregator} za {vybrany_mesic}")
                                    telo = urllib.parse.quote(f"Ahoj Martine,\n\nprosím tě o finální schválení částky {castka_format} pro {agregator} v naší schvalovací aplikaci.\n\nDíky, Martin")
                                    s3.link_button("✉️ Poslat urgenci", f"mailto:{EMAIL_CEJKA}?subject={predmet}&body={telo}")
                                else:
                                    s3.warning("⏳ Čeká na Čejku")
                            else:
                                s3.write("⏳ Zablokováno (Čeká na Iwonskiho)")

# ==========================================
# ZÁLOŽKA HISTORIE (Export Excel)
# ==========================================
with tabs[-1]:
    st.subheader("🗂️ Kompletní historie fakturací")
    
    if df.empty:
        st.info("Databáze je zatím prázdná.")
    else:
        df_zobrazeni = df.drop(columns=["ID"])
        
        # Generování CSV speciálně upraveného pro otevření v českém Excelu
        csv = df_zobrazeni.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
        
        st.download_button(
            label="📥 Stáhnout historii do Excelu (CSV)",
            data=csv,
            file_name=f"Fakturace_Historie_{datetime.now().strftime('%Y-%m-%d')}.csv",
            mime="text/csv",
            type="primary"
        )
        
        st.dataframe(df_zobrazeni, use_container_width=True, hide_index=True)
