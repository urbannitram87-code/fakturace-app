import streamlit as st
import pandas as pd
from datetime import datetime
import urllib.parse
import io
from streamlit_gsheets import GSheetsConnection

# Nastavení širokého rozvržení stránky
st.set_page_config(page_title="O2 Fakturace - Schvalování", layout="wide")

# ==========================================
# 1. KONFIGURACE A PŘIHLÁŠENÍ
# ==========================================

def check_password():
    """Vrací True, pokud uživatel zadal správné přihlašovací údaje."""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.title("🔐 Vstup do systému fakturace")
        user = st.selectbox("Vyberte své jméno:", ["Martin Urban", "Jiří Iwonski", "Martin Čejka"])
        password = st.text_input("Zadejte heslo:", type="password")
        
        if st.button("Přihlásit se"):
            # Převod jména na klíč pro secrets (např. "Martin Urban" -> "martin_urban")
            user_key = user.lower().replace(" ", "_").replace("í", "i")
            
            # Kontrola hesla proti Secrets
            if user_key in st.secrets["credentials"] and password == st.secrets["credentials"][user_key]:
                st.session_state["authenticated"] = True
                st.session_state["user_role"] = user
                st.rerun()
            else:
                st.error("❌ Nesprávné heslo!")
        return False
    return True

# Spuštění kontroly přihlášení
if not check_password():
    st.stop() # Pokud není přihlášen, zbytek kódu se nespustí

# --- HLAVNÍ DATA A KONFIGURACE ---
SLUZBY_AGREGATORI = {
    "Audiotex": ["ATS", "T-Mobile", "Quantcom (ex. DIAL)"],
    "Premium SMS": ["ATS", "ATS (s doručenkou)", "BOKU", "ComGate Payments", "ComGate (SMS s doručenkou)", "GLOBDATA", "Comverga", "Fórum dárců"],
    "M-platba": ["Apple", "ATS", "Docomo Digital (Bango)", "Globdata", "Boku Network Services Estonia OÜ (ex Fortumo) - Tidal", "Boku Network Services Estonia OÜ (ex Fortumo) - Ostatní", "GM Europe", "Google", "Boku (Microsoft)"]
}
OSTATNI_PARTNERI = ["Mobilní pohotovost", "Zásilkovna", "Teya", "KB SmartPay"]
EMAIL_IWONSKI = "jiri.iwonski@o2.cz"
EMAIL_CEJKA = "martin.cejka@o2.cz"
mesice = [f"{m:02d}/2026" for m in range(2, 13)] + [f"{m:02d}/2027" for m in range(1, 13)]

# --- PŘIPOJENÍ ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        df = conn.read(worksheet="Data", usecols=list(range(10)))
        if df.empty or "ID" not in df.columns:
            return pd.DataFrame(columns=["ID", "Mesic", "Sluzba", "Agregator", "Castka", "Mena", "Urban", "Iwonski", "Cejka", "Provize"])
        df = df.fillna("")
        df['ID'] = df['ID'].astype(str)
        df['Castka'] = pd.to_numeric(df['Castka'], errors='coerce').fillna(0)
        df['Provize'] = pd.to_numeric(df['Provize'], errors='coerce').fillna(0)
        return df
    except Exception:
        return pd.DataFrame(columns=["ID", "Mesic", "Sluzba", "Agregator", "Castka", "Mena", "Urban", "Iwonski", "Cejka", "Provize"])

df = load_data()

# --- POSTRANNÍ PANEL (Upravený) ---
st.sidebar.title("👤 Uživatel")
st.sidebar.info(f"Přihlášen jako:\n**{st.session_state['user_role']}**")
role = st.session_state["user_role"]

if st.sidebar.button("Odhlásit se"):
    st.session_state["authenticated"] = False
    st.rerun()

vybrany_mesic = st.sidebar.selectbox("Fakturační období:", mesice)

# --- ZBYTEK APLIKACE (Identický s předchozí verzí) ---

def zpozdeni_dnu(text_statusu):
    if not text_statusu or "(" not in text_statusu: return 0
    try:
        datum_str = text_statusu.split("(")[1].replace(")", "").strip()
        datum_schvaleni = datetime.strptime(datum_str, "%d.%m.%Y")
        return (datetime.now() - datum_schvaleni).days
    except:
        return 0

st.title(f"Fakturace: {vybrany_mesic}")

# Logika deadline
v_m, v_r = int(vybrany_mesic.split('/')[0]), int(vybrany_mesic.split('/')[1])
d_m = 1 if v_m == 12 else v_m + 1
d_r = v_r + 1 if v_m == 12 else v_r
deadline_datum = datetime(d_r, d_m, 25)
je_po_termínu = datetime.now() > deadline_datum

nazvy_sluzeb = list(SLUZBY_AGREGATORI.keys())
tabs = st.tabs(nazvy_sluzeb + ["📦 Ostatní", "📈 Analytika", "🗂️ Celková historie"])
df_mesic = df[df["Mesic"] == vybrany_mesic].copy()

# 2. STANDARDNÍ SLUŽBY
for i, sluzba in enumerate(nazvy_sluzeb):
    with tabs[i]:
        st.subheader(f"Přehled pro: {sluzba}")
        for agregator in SLUZBY_AGREGATORI[sluzba]:
            zaznam = df_mesic[(df_mesic["Sluzba"] == sluzba) & (df_mesic["Agregator"] == agregator)]
            u_key = f"{sluzba}_{agregator}".replace(" ", "_")
            dnes = datetime.now().strftime("%d.%m.%Y")
            
            with st.container(border=True):
                if zaznam.empty:
                    c1, c2, c3 = st.columns([1, 1, 1])
                    if je_po_termínu:
                        c1.markdown(f"### 🚨 :red[{agregator}]")
                        c1.caption(f":red[Chybí částka! Deadline byl 25.{d_m:02d}.{d_r}]")
                    else:
                        c1.markdown(f"### {agregator}")
                        c1.caption("Čeká se na zadání částky...")
                    
                    if role == "Martin Urban":
                        with c2:
                            in_c = st.number_input("Částka", min_value=0.0, value=None, format="%.2f", key=f"c_{u_key}", placeholder="Zadejte částku")
                        with c3:
                            in_m = st.selectbox("Měna", ["Kč", "EUR"], key=f"m_{u_key}")
                            if st.button("Uložit a schválit", key=f"b_{u_key}", type="primary", use_container_width=True, disabled=in_c is None):
                                nove_id = str(datetime.now().timestamp())
                                n_z = pd.DataFrame([{"ID": nove_id, "Mesic": vybrany_mesic, "Sluzba": sluzba, "Agregator": agregator, "Castka": in_c, "Mena": in_m, "Urban": f"Urban ({dnes})", "Iwonski": "", "Cejka": "", "Provize": 0}])
                                df = pd.concat([df, n_z], ignore_index=True)
                                conn.update(worksheet="Data", data=df); st.cache_data.clear(); st.rerun()
                    else:
                        c2.info("⏳ Čeká na Urbana")
                else:
                    row = zaznam.iloc[0]
                    c_f = f"{float(row['Castka']):,.2f} {row['Mena']}".replace(",", " ")
                    col_l, col_r, col_d = st.columns([2, 2, 1])
                    col_l.markdown(f"### ✅ {agregator}")
                    col_r.markdown(f"### {c_f}")
                    if role == "Martin Urban" and col_d.button("🗑️ Smazat", key=f"del_{row['ID']}"):
                        df = df[df['ID'] != str(row['ID'])]
                        conn.update(worksheet="Data", data=df); st.cache_data.clear(); st.rerun()
                    st.divider()
                    s1, s2, s3 = st.columns(3)
                    s1.success(f"**Urban:** {row['Urban']}")
                    if row['Iwonski']: s2.success(f"**Jiw:** {row['Iwonski']}")
                    elif role == "Jiří Iwonski":
                        if s2.button("Schválit (Jiw)", key=f"i_{row['ID']}", type="primary"):
                            df.loc[df['ID'] == str(row['ID']), 'Iwonski'] = f"Jiw ({dnes})"
                            conn.update(worksheet="Data", data=df); st.cache_data.clear(); st.rerun()
                    else:
                        dny = zpozdeni_dnu(row['Urban'])
                        if dny >= 5:
                            s2.error(f"⏳ Čeká ({dny} dní)")
                            p, t = urllib.parse.quote(f"Urgence: {agregator}"), urllib.parse.quote(f"Ahoj Jiří, prosím o schválení {c_f} pro {agregator}. Díky!")
                            s2.link_button("✉️ Urgovat", f"mailto:{EMAIL_IWONSKI}?subject={p}&body={t}")
                        else: s2.warning("⏳ Čeká na Iwonskiho")
                    if row['Cejka']: s3.success(f"**Martin:** {row['Cejka']}")
                    elif role == "Martin Čejka":
                        if row['Iwonski'] and s3.button("Finálně schválit", key=f"c_{row['ID']}", type="primary"):
                            df.loc[df['ID'] == str(row['ID']), 'Cejka'] = f"Martin ({dnes})"
                            conn.update(worksheet="Data", data=df); st.cache_data.clear(); st.rerun()
                        else: s3.warning("Čeká na Jirku")
                    else:
                        if row['Iwonski']:
                            dny = zpozdeni_dnu(row['Iwonski'])
                            if dny >= 5:
                                s3.error(f"⏳ Čeká ({dny} dní)")
                                p, t = urllib.parse.quote(f"Urgence: {agregator}"), urllib.parse.quote(f"Ahoj Martine, prosím o schválení {c_f} pro {agregator}. Díky!")
                                s3.link_button("✉️ Urgovat", f"mailto:{EMAIL_CEJKA}?subject={p}&body={t}")
                            else: s3.warning("⏳ Čeká na Čejku")
                        else: s3.write("⏳ Blokováno")

# 3. OSTATNÍ
with tabs[len(nazvy_sluzeb)]:
    st.subheader("📦 Partneři - Přímé schvalování (Urban)")
    if role != "Martin Urban":
        st.warning("Tato sekce je určena pouze pro Martina Urbana.")
    else:
        for p in OSTATNI_PARTNERI:
            z = df_mesic[(df_mesic["Sluzba"] == "Ostatní") & (df_mesic["Agregator"] == p)]
            u_k = f"ost_{p}".replace(" ", "_")
            dnes = datetime.now().strftime("%d.%m.%Y")
            if z.empty:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
                    c1.markdown(f"### {p}")
                    in_c = c2.number_input("Částka", min_value=0.0, value=None, key=f"vc_{u_k}", placeholder="Kč/EUR")
                    in_p = c3.number_input("Provize", min_value=0.0, value=None, key=f"vp_{u_k}", placeholder="Provize")
                    in_m = c4.selectbox("Měna", ["Kč", "EUR"], key=f"vm_{u_k}")
                    if st.button("Uložit", key=f"vb_{u_k}", type="primary", disabled=in_c is None):
                        n_id = str(datetime.now().timestamp())
                        n_z = pd.DataFrame([{"ID": n_id, "Mesic": vybrany_mesic, "Sluzba": "Ostatní", "Agregator": p, "Castka": in_c, "Mena": in_m, "Urban": f"Urban ({dnes})", "Iwonski": "N/A", "Cejka": "N/A", "Provize": in_p if in_p else 0}])
                        df = pd.concat([df, n_z], ignore_index=True)
                        conn.update(worksheet="Data", data=df); st.cache_data.clear(); st.rerun()
            else:
                row = z.iloc[0]
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
                    c1.markdown(f"### ✅ {p}")
                    c2.metric("Částka", f"{row['Castka']:,.2f} {row['Mena']}".replace(",", " "))
                    c3.metric("Provize", f"{row['Provize']:,.2f} {row['Mena']}".replace(",", " "))
                    if c4.button("🗑️ Smazat", key=f"do_{row['ID']}"):
                        df = df[df['ID'] != str(row['ID'])]
                        conn.update(worksheet="Data", data=df); st.cache_data.clear(); st.rerun()

# 4. ANALYTIKA
with tabs[-2]:
    st.subheader("📈 Analytika nákladů a provizí")
    if df.empty or df['Castka'].sum() == 0:
        st.info("Zatím nejsou data pro analytiku.")
    else:
        m_sel = st.radio("Měna grafů:", ["Kč", "EUR"], horizontal=True)
        dg = df[df['Mena'] == m_sel].copy()
        if not dg.empty:
            dg['D'] = pd.to_datetime(dg['Mesic'], format='%m/%Y')
            dg = dg.sort_values('D')
            an1, an2 = st.tabs(["Standardní Služby", "Ostatní Partneři"])
            with an1:
                ds = dg[dg['Sluzba'] != 'Ostatní']
                if not ds.empty:
                    st.bar_chart(ds.pivot_table(index='Mesic', columns='Sluzba', values='Castka', aggfunc='sum').loc[ds['Mesic'].unique()])
            with an2:
                do = dg[dg['Sluzba'] == 'Ostatní']
                if not do.empty:
                    st.line_chart(do.pivot_table(index='Mesic', columns='Agregator', values='Castka', aggfunc='sum').loc[do['Mesic'].unique()])

# 5. HISTORIE
with tabs[-1]:
    st.subheader("🗂️ Kompletní historie")
    if not df.empty:
        exp_df = df.drop(columns=["ID"])
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w: exp_df.to_excel(w, index=False, sheet_name='Fakturace')
        st.download_button("📥 Stáhnout Excel (.xlsx)", buf.getvalue(), f"Fakturace_{datetime.now().strftime('%Y-%m-%d')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
        st.dataframe(exp_df, use_container_width=True, hide_index=True)
