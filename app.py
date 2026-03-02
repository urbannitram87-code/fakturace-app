import streamlit as st
import pandas as pd
from datetime import datetime
import datetime as dt
import urllib.parse
import io
import unicodedata
from streamlit_gsheets import GSheetsConnection

# Nastavení širokého rozvržení stránky
st.set_page_config(page_title="O2 Fakturace - Schvalování", layout="wide")

# ==========================================
# 1. KONFIGURACE A PŘIHLÁŠENÍ
# ==========================================

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.title("🔐 Vstup do systému fakturace")
        user = st.selectbox("Vyberte své jméno:", ["Martin Urban", "Jiří Iwonski", "Martin Čejka"])
        password = st.text_input("Zadejte heslo:", type="password")
        
        if st.button("Přihlásit se"):
            normalized = unicodedata.normalize('NFKD', user)
            user_key = "".join([c for c in normalized if not unicodedata.combining(c)])
            user_key = user_key.lower().replace(" ", "_")
            
            if user_key in st.secrets["credentials"] and password == st.secrets["credentials"][user_key]:
                st.session_state["authenticated"] = True
                st.session_state["user_role"] = user
                st.rerun()
            else:
                st.error(f"❌ Nesprávné heslo pro uživatele {user}!")
        return False
    return True

if not check_password():
    st.stop()

# --- HLAVNÍ KONFIGURACE ---
SLUZBY_AGREGATORI = {
    "Audiotex": ["ATS", "T-Mobile", "Quantcom (ex. DIAL)"],
    "Premium SMS": ["ATS", "ATS (s doručenkou)", "BOKU", "ComGate Payments", "ComGate (SMS s doručenkou)", "GLOBDATA", "Comverga", "Fórum dárců"],
    "M-platba": ["Apple", "ATS", "Docomo Digital (Bango)", "Globdata", "Boku Network Services Estonia OÜ (ex Fortumo) - Tidal", "Boku Network Services Estonia OÜ (ex Fortumo) - Ostatní", "GM Europe", "Google", "Boku (Microsoft)"]
}
OSTATNI_PARTNERI = ["Mobilní pohotovost", "Zásilkovna", "Teya", "KB SmartPay"]

EMAIL_IWONSKI = "jiri.iwonski@o2.cz"
EMAIL_CEJKA = "martin.cejka@o2.cz"

mesice = [f"{m:02d}/2026" for m in range(1, 13)] + [f"{m:02d}/2027" for m in range(1, 13)]

# --- PŘIPOJENÍ K DATŮM ---
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

def zpozdeni_dnu(text_statusu):
    if not text_statusu or "(" not in text_statusu: return 0
    try:
        datum_str = text_statusu.split("(")[1].replace(")", "").strip()
        datum_schvaleni = datetime.strptime(datum_str, "%d.%m.%Y")
        return (datetime.now() - datum_schvaleni).days
    except:
        return 0

# --- POSTRANNÍ PANEL A NOTIFIKACE ---
st.sidebar.title("👤 Uživatel")
st.sidebar.info(f"Přihlášen jako:\n**{st.session_state['user_role']}**")
role = st.session_state["user_role"]

# Výpočet předchozího měsíce jako výchozí hodnoty
dnes = dt.date.today()
prvni_den_v_mesici = dnes.replace(day=1)
minuly_mesic = prvni_den_v_mesici - dt.timedelta(days=1)
vychozi_mesic_str = minuly_mesic.strftime("%m/%Y")

try:
    vychozi_index = mesice.index(vychozi_mesic_str)
except ValueError:
    vychozi_index = len(mesice) - 1 # Záchrana, pokud se nenajde

vybrany_mesic = st.sidebar.selectbox("Fakturační období:", mesice, index=vychozi_index)

st.title(f"Fakturace: {vybrany_mesic}")

# Výpočet úkolů (notifikací) pro přihlášeného uživatele pro VYBRANÝ MĚSÍC
df_mesic = df[df["Mesic"] == vybrany_mesic].copy()
cekajici_ukoly = 0

if role == "Jiří Iwonski":
    cekajici_ukoly = len(df_mesic[(df_mesic['Urban'] != '') & (~df_mesic['Urban'].str.contains('N/A')) & (df_mesic['Iwonski'] == '')])
elif role == "Martin Čejka":
    cekajici_ukoly = len(df_mesic[(df_mesic['Iwonski'] != '') & (~df_mesic['Iwonski'].str.contains('N/A')) & (df_mesic['Cejka'] == '')])
elif role == "Martin Urban":
    ocekavany_pocet = sum(len(v) for v in SLUZBY_AGREGATORI.values())
    zadanu_pocet = len(df_mesic[df_mesic['Sluzba'] != 'Ostatní'])
    cekajici_ukoly = ocekavany_pocet - zadanu_pocet
    if cekajici_ukoly < 0: cekajici_ukoly = 0

st.sidebar.divider()
if cekajici_ukoly > 0:
    st.sidebar.warning(f"🔔 **K vyřízení (tento měsíc): {cekajici_ukoly}**")
else:
    st.sidebar.success("✅ **Vše vyřízeno**")

if st.sidebar.button("Odhlásit se"):
    st.session_state["authenticated"] = False
    st.rerun()

# --- LOGIKA DEADLINE ---
v_m, v_r = int(vybrany_mesic.split('/')[0]), int(vybrany_mesic.split('/')[1])
d_m = 1 if v_m == 12 else v_m + 1
d_r = v_r + 1 if v_m == 12 else v_r
deadline_datum = datetime(d_r, d_m, 25)
je_po_termínu = datetime.now() > deadline_datum

# Definice záložek
nazvy_sluzeb = list(SLUZBY_AGREGATORI.keys())
tabs = st.tabs(nazvy_sluzeb + ["📦 Ostatní", "📈 Analytika", "🗂️ Celková historie"])

# ==========================================
# 2. STANDARDNÍ SLUŽBY
# ==========================================
for i, sluzba in enumerate(nazvy_sluzeb):
    with tabs[i]:
        st.subheader(f"Přehled pro: {sluzba}")
        for agregator in SLUZBY_AGREGATORI[sluzba]:
            zaznam = df_mesic[(df_mesic["Sluzba"] == sluzba) & (df_mesic["Agregator"] == agregator)]
            u_key = f"{sluzba}_{agregator}".replace(" ", "_")
            dnes_full = datetime.now().strftime("%d.%m.%Y")
            
            with st.container(border=True):
                # --- ZATÍM NEZADÁNO ---
                if zaznam.empty:
                    c1, c2, c3, c4 = st.columns([1.5, 1.2, 0.8, 1])
                    if je_po_termínu:
                        c1.markdown(f"### 🚨 :red[{agregator}]")
                        c1.caption(f":red[Chybí částka! Deadline byl 25.{d_m:02d}.{d_r}]")
                    else:
                        c1.markdown(f"### {agregator}")
                        c1.caption("Čeká se na zadání...")
                    
                    if role == "Martin Urban":
                        with c2:
                            in_c = st.number_input("Částka", min_value=0.0, value=None, format="%.2f", key=f"c_{u_key}", placeholder="Např. 50000", label_visibility="collapsed")
                        with c3:
                            in_m = st.selectbox("Měna", ["Kč", "EUR"], key=f"m_{u_key}", label_visibility="collapsed")
                        with c4:
                            if st.button("Uložit (Schválit)", key=f"b_{u_key}", type="primary", use_container_width=True, disabled=in_c is None):
                                nove_id = str(datetime.now().timestamp())
                                n_z = pd.DataFrame([{"ID": nove_id, "Mesic": vybrany_mesic, "Sluzba": sluzba, "Agregator": agregator, "Castka": in_c, "Mena": in_m, "Urban": f"Urban ({dnes_full})", "Iwonski": "", "Cejka": "", "Provize": 0}])
                                df = pd.concat([df, n_z], ignore_index=True)
                                conn.update(worksheet="Data", data=df); st.cache_data.clear(); st.rerun()
                            # NOVÉ TLAČÍTKO: Nevystaveno / N/A
                            if st.button("Nevystaveno / N/A", key=f"na_{u_key}", use_container_width=True):
                                nove_id = str(datetime.now().timestamp())
                                n_z = pd.DataFrame([{"ID": nove_id, "Mesic": vybrany_mesic, "Sluzba": sluzba, "Agregator": agregator, "Castka": 0.0, "Mena": "Kč", "Urban": f"N/A ({dnes_full})", "Iwonski": "N/A", "Cejka": "N/A", "Provize": 0}])
                                df = pd.concat([df, n_z], ignore_index=True)
                                conn.update(worksheet="Data", data=df); st.cache_data.clear(); st.rerun()
                    else:
                        c2.info("⏳ Čeká na Martina Urbana")

                # --- UŽ JE ZADÁNO ---
                else:
                    row = zaznam.iloc[0]
                    
                    # Logika pro "N/A" (Nevystaveno)
                    if "N/A" in str(row['Urban']):
                        col_l, col_r, col_d = st.columns([2, 2, 1])
                        col_l.markdown(f"### ⏸️ {agregator}")
                        col_r.markdown("### :gray[Faktura nevystavena (N/A)]")
                        if role == "Martin Urban" and col_d.button("🗑️ Zrušit N/A", key=f"del_{row['ID']}"):
                            df = df[df['ID'] != str(row['ID'])]
                            conn.update(worksheet="Data", data=df); st.cache_data.clear(); st.rerun()
                    
                    # Logika pro standardní fakturu
                    else:
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
                        
                        if row['Iwonski'] and row['Iwonski'] != "N/A": s2.success(f"**Jiw:** {row['Iwonski']}")
                        elif role == "Jiří Iwonski":
                            if s2.button("Schválit (Jiw)", key=f"i_{row['ID']}", type="primary"):
                                df.loc[df['ID'] == str(row['ID']), 'Iwonski'] = f"Jiw ({dnes_full})"
                                conn.update(worksheet="Data", data=df); st.cache_data.clear(); st.rerun()
                        else:
                            dny = zpozdeni_dnu(row['Urban'])
                            if dny >= 5:
                                s2.error(f"⏳ Čeká ({dny} dní)")
                                p, t = urllib.parse.quote(f"Urgence: {agregator}"), urllib.parse.quote(f"Ahoj Jiří, prosím o schválení {c_f} pro {agregator}. Díky!")
                                s2.link_button("✉️ Urgovat", f"mailto:{EMAIL_IWONSKI}?subject={p}&body={t}")
                            else: s2.warning("⏳ Čeká na Iwonskiho")

                        if row['Cejka'] and row['Cejka'] != "N/A": s3.success(f"**Martin:** {row['Cejka']}")
                        elif role == "Martin Čejka":
                            if row['Iwonski'] and s3.button("Finálně schválit", key=f"c_{row['ID']}", type="primary"):
                                df.loc[df['ID'] == str(row['ID']), 'Cejka'] = f"Martin ({dnes_full})"
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

# ==========================================
# 3. ZÁLOŽKA OSTATNÍ (NÁHLED PRO VŠECHNY)
# ==========================================
with tabs[len(nazvy_sluzeb)]:
    st.subheader("📦 Partneři - Ostatní")
    
    for p in OSTATNI_PARTNERI:
        z = df_mesic[(df_mesic["Sluzba"] == "Ostatní") & (df_mesic["Agregator"] == p)]
        u_k = f"ost_{p}".replace(" ", "_")
        dnes_full = datetime.now().strftime("%d.%m.%Y")
        
        with st.container(border=True):
            if z.empty:
                if role == "Martin Urban":
                    c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
                    c1.markdown(f"### {p}")
                    in_c = c2.number_input("Částka", min_value=0.0, value=None, key=f"vc_{u_k}", placeholder="Kč/EUR")
                    in_p = c3.number_input("Provize", min_value=0.0, value=None, key=f"vp_{u_k}", placeholder="Provize")
                    in_m = c4.selectbox("Měna", ["Kč", "EUR"], key=f"vm_{u_k}")
                    
                    b1, b2 = c4.columns(2)
                    if st.button("Uložit", key=f"vb_{u_k}", type="primary", use_container_width=True, disabled=in_c is None):
                        n_id = str(datetime.now().timestamp())
                        n_z = pd.DataFrame([{"ID": n_id, "Mesic": vybrany_mesic, "Sluzba": "Ostatní", "Agregator": p, "Castka": in_c, "Mena": in_m, "Urban": f"Urban ({dnes_full})", "Iwonski": "N/A", "Cejka": "N/A", "Provize": in_p if in_p else 0}])
                        df = pd.concat([df, n_z], ignore_index=True)
                        conn.update(worksheet="Data", data=df); st.cache_data.clear(); st.rerun()
                    if st.button("N/A", key=f"vna_{u_k}", use_container_width=True):
                        n_id = str(datetime.now().timestamp())
                        n_z = pd.DataFrame([{"ID": n_id, "Mesic": vybrany_mesic, "Sluzba": "Ostatní", "Agregator": p, "Castka": 0, "Mena": "Kč", "Urban": f"N/A ({dnes_full})", "Iwonski": "N/A", "Cejka": "N/A", "Provize": 0}])
                        df = pd.concat([df, n_z], ignore_index=True)
                        conn.update(worksheet="Data", data=df); st.cache_data.clear(); st.rerun()
                else:
                    c1, c2 = st.columns([1.5, 3])
                    c1.markdown(f"### {p}")
                    c2.info("⏳ Martin Urban zatím nezadal údaje pro tento měsíc.")
            else:
                row = z.iloc[0]
                if "N/A" in str(row['Urban']):
                    c1, c2, c3 = st.columns([1.5, 2, 1])
                    c1.markdown(f"### ⏸️ {p}")
                    c2.markdown("### :gray[Nevystaveno / N/A]")
                    if role == "Martin Urban" and c3.button("🗑️ Zrušit N/A", key=f"do_{row['ID']}", use_container_width=True):
                        df = df[df['ID'] != str(row['ID'])]
                        conn.update(worksheet="Data", data=df); st.cache_data.clear(); st.rerun()
                else:
                    c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
                    c1.markdown(f"### ✅ {p}")
                    c2.metric("Částka", f"{row['Castka']:,.2f} {row['Mena']}".replace(",", " "))
                    c3.metric("Provize", f"{row['Provize']:,.2f} {row['Mena']}".replace(",", " "))
                    
                    if role == "Martin Urban":
                        if c4.button("🗑️ Smazat", key=f"do_{row['ID']}", use_container_width=True):
                            df = df[df['ID'] != str(row['ID'])]
                            conn.update(worksheet="Data", data=df); st.cache_data.clear(); st.rerun()
                    else:
                        c4.write("👀 Jen pro čtení")

# ==========================================
# 4. ANALYTIKA (VYLEPŠENÁ)
# ==========================================
with tabs[-2]:
    st.subheader("📈 Analytika a reporty")
    if df.empty or df['Castka'].sum() == 0:
        st.info("Zatím nejsou uložena žádná data s nenulovou částkou.")
    else:
        m_sel = st.radio("Vyberte měnu pro grafy:", ["Kč", "EUR"], horizontal=True)
        dg = df[(df['Mena'] == m_sel) & (~df['Urban'].str.contains('N/A'))].copy()
        
        if dg.empty:
            st.warning(f"Žádná platná data v měně {m_sel}")
        else:
            # Převedeme Měsíc na skutečné Datum, aby grafy Streamlitu pochopily osu X!
            dg['Datum'] = pd.to_datetime(dg['Mesic'], format='%m/%Y')
            
            an1, an2, an3 = st.tabs(["📊 Souhrn za Služby", "🔍 Detail Agregátorů", "📦 Ostatní (S Provizí)"])
            
            # --- ZÁLOŽKA 1: SLUŽBY ---
            with an1:
                ds = dg[dg['Sluzba'] != 'Ostatní']
                if not ds.empty:
                    st.markdown(f"**Celkové náklady podle služeb ({m_sel})**")
                    # Seskupení podle Data a Služby, vytvoření tabulky pro graf
                    ds_grouped = ds.groupby(['Datum', 'Sluzba'])['Castka'].sum().reset_index()
                    pivot_s = ds_grouped.pivot(index='Datum', columns='Sluzba', values='Castka').fillna(0)
                    st.bar_chart(pivot_s)
                else: st.info("Žádná data.")

            # --- ZÁLOŽKA 2: AGREGÁTOŘI ---
            with an2:
                ds = dg[dg['Sluzba'] != 'Ostatní']
                if not ds.empty:
                    vybrana_sluzba = st.selectbox("Vyberte službu pro detailní pohled:", ds['Sluzba'].unique())
                    da = ds[ds['Sluzba'] == vybrana_sluzba]
                    
                    st.markdown(f"**Vývoj nákladů jednotlivých agregátorů ({vybrana_sluzba})**")
                    da_grouped = da.groupby(['Datum', 'Agregator'])['Castka'].sum().reset_index()
                    pivot_a = da_grouped.pivot(index='Datum', columns='Agregator', values='Castka').fillna(0)
                    st.line_chart(pivot_a)
                else: st.info("Žádná data.")

            # --- ZÁLOŽKA 3: OSTATNÍ ---
            with an3:
                do = dg[dg['Sluzba'] == 'Ostatní']
                if not do.empty:
                    st.markdown(f"**Vývoj fakturované ČÁSTKY ({m_sel})**")
                    do_c_grouped = do.groupby(['Datum', 'Agregator'])['Castka'].sum().reset_index()
                    pivot_oc = do_c_grouped.pivot(index='Datum', columns='Agregator', values='Castka').fillna(0)
                    st.line_chart(pivot_oc)
                    
                    st.markdown(f"**Vývoj PROVIZÍ ({m_sel})**")
                    do_p_grouped = do.groupby(['Datum', 'Agregator'])['Provize'].sum().reset_index()
                    pivot_op = do_p_grouped.pivot(index='Datum', columns='Agregator', values='Provize').fillna(0)
                    st.bar_chart(pivot_op)
                else: st.info("Žádná data pro Ostatní.")

# ==========================================
# 5. HISTORIE A EXCEL EXPORT
# ==========================================
with tabs[-1]:
    st.subheader("🗂️ Kompletní historie")
    if not df.empty:
        exp_df = df.drop(columns=["ID"])
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w: 
            exp_df.to_excel(w, index=False, sheet_name='Fakturace')
        st.download_button("📥 Stáhnout Excel (.xlsx)", buf.getvalue(), f"Fakturace_{datetime.now().strftime('%Y-%m-%d')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
        st.dataframe(exp_df, use_container_width=True, hide_index=True)
