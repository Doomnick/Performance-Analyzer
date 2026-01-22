import pandas as pd
import numpy as np
from pathlib import Path
import os
os.environ["GIO_USE_VFS"] = "local"
os.environ["G_MESSAGES_DEBUG"] = ""
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

# --- POMOCNÉ FUNKCE ---

def get_file_stems(path, pattern="*.txt"):
    if not path or path == "Nenalezeno" or not os.path.exists(path):
        return []
    return [f.stem.strip() for f in Path(path).glob(pattern)]

def time_to_seconds(t_str):
    try:
        if pd.isna(t_str) or t_str == "" or t_str == "--": return 0.0
        parts = str(t_str).split(':')
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2].replace(',', '.'))
        return 0.0
    except: return 0.0

# --- UI LOGIKA ---

def build_comparison_df(paths, inputs):
    YES, NO = "✅", "❌"
    ant_path = paths.get("antropometrie")
    antropo_counts, antropo_ids_list = {}, []
    if ant_path and os.path.exists(ant_path):
        excel_files = list(Path(ant_path).glob("*.xls*"))
        if excel_files:
            try:
                xl = pd.ExcelFile(excel_files[0])
                sn = "Data_Sheet" if "Data_Sheet" in xl.sheet_names else xl.sheet_names[0]
                df_ant = pd.read_excel(xl, sheet_name=sn)
                if 'ID' in df_ant.columns:
                    df_ant['ID'] = df_ant['ID'].astype(str).str.strip()
                    antropo_counts = df_ant['ID'].value_counts().to_dict()
                    antropo_ids_list = list(antropo_counts.keys())
            except: pass

    all_ids = sorted(list(set(antropo_ids_list + get_file_stems(paths.get("wingate")) + 
                              get_file_stems(paths.get("srovnani")) + get_file_stems(paths.get("srovnani2")) + 
                              get_file_stems(paths.get("spiro"), "*.xls*"))))
    rows = []
    for idx in all_ids:
        row = {"ID": idx, "Antropometrie": YES if idx in antropo_ids_list else NO,
               "Wingate": YES if idx in get_file_stems(paths.get("wingate")) else NO,
               "Srovnání 1": YES if idx in get_file_stems(paths.get("srovnani")) else NO,
               "Srovnání 2": YES if idx in get_file_stems(paths.get("srovnani2")) else NO,
               "Spirometrie": YES if idx in get_file_stems(paths.get("spiro"), "*.xls*") else NO,
               "Počet v Antrop.": int(antropo_counts.get(idx, 0))}
        report = "FAILED"
        if row["Antropometrie"] == YES and row["Wingate"] == YES:
            if inputs.get('srovnani2'): report = "Triple" if (row["Počet v Antrop."] >= 3 and row["Srovnání 1"] == YES and row["Srovnání 2"] == YES) else "Missing Compar. 2"
            elif inputs.get('srovnani'): report = "Double" if (row["Počet v Antrop."] >= 2 and row["Srovnání 1"] == YES) else "Missing Compar. 1"
            else: report = "Single"
        elif row["Spirometrie"] == YES and row["Antropometrie"] == YES: report = "Spiro"
        if report != "FAILED" and "Missing" not in report and row["Spirometrie"] == YES and "Spiro" not in report: report += " + Spiro"
        row["Report"] = report
        rows.append(row)
    return pd.DataFrame(rows)

def check_errors(df, inputs):
    """OPRAVA: Nový error check počítající kategorie pro UI."""
    if df is None: return "Žádná data k analýze."
    counts = df["Report"].value_counts().to_dict()
    summary = "--- POČET REPORTŮ DLE KATEGORIÍ ---\n\n"
    for cat, count in counts.items():
        if "FAILED" in cat or "Missing" in cat:
            summary += f"❌ {cat}: {count} (Reporty nebudou vygenerovány)\n"
        else:
            summary += f"✅ {cat}: {count}\n"
    return summary

# --- VÝPOČETNÍ JÁDRO ---

def load_athlete_info(somato_folder, athlete_id):
    if not somato_folder: return None
    excel_files = list(Path(somato_folder).glob("*.xls*"))
    if not excel_files: return None
    df_somato = pd.read_excel(excel_files[0], sheet_name="Data_Sheet")
    df_somato['ID'] = df_somato['ID'].astype(str).str.strip()
    athlete_data = df_somato[df_somato['ID'] == str(athlete_id)].copy()
    if athlete_data.empty: return None
    date_col = 'Date_measurement' if 'Date_measurement' in athlete_data.columns else 'Date'
    athlete_data[date_col] = pd.to_datetime(athlete_data[date_col], errors='coerce')
    athlete_data = athlete_data.sort_values(by=date_col, ascending=True)
    latest = athlete_data.iloc[-1]
    birth_date = pd.to_datetime(latest.get('Birth'), errors='coerce')
    age = (latest[date_col] - birth_date).days // 365.25 if pd.notnull(birth_date) else 0
    return {
        "Name": f"{latest.get('Name', '')} {latest.get('Surname', '')}",
        "Birth": birth_date.strftime('%d/%m/%Y') if pd.notnull(birth_date) else "Neuvedeno",
        "Age": int(age), 
        "Height": round(float(latest.get('Height', 0)), 1), 
        "Weight": round(float(latest.get('Weight', 0)), 1),
        "Fat": round(float(latest.get('Fat', 0)), 1), 
        "ATH": round(float(latest.get('ATH', 0)), 1), 
        "LA": round(float(latest.get('LA', 0)), 1),
        "SJ": round(float(latest.get('SJ', 0)), 1), # PŘIDÁNO: Načtení Squat Jumpu
        "Date_measurement": latest[date_col].strftime('%d/%m/%Y'), 
        "ID": athlete_id, 
        "All_Records": athlete_data.to_dict('records')
    }

def process_single_wingate_file(file_path):
    encodings = ['utf-8', 'cp1250', 'latin1']
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(file_path, sep='\t', decimal=',', encoding=enc, on_bad_lines='skip')
            break
        except UnicodeDecodeError: continue
    
    if df is None: raise ValueError(f"Nelze načíst {file_path}")

    df = df.replace('--', np.nan)
    t_col = next((c for c in df.columns if 'elapsed' in c.lower() and 'total' in c.lower()), None)
    p_col_raw = next((c for c in df.columns if 'power' in c.lower() and ('w' in c.lower() or '[' in c or '(' in c)), None)
    tr_col = next((c for c in df.columns if 'turns' in c.lower()), None)
    hr_col = next((c for c in df.columns if 'heart' in c.lower() or 'tf' in c.lower()), None)

    df['sec_orig'] = df[t_col].apply(time_to_seconds)

    # --- LOGIKA OŘEZU PŘESNĚ DLE R ---
    # 1. Pokud hned první čas v souboru je > 3s, vynulujeme osu
    if df['sec_orig'].iloc[0] > 3:
        df['sec_orig'] = df['sec_orig'] - df['sec_orig'].iloc[0]
    
    # 2. Pokud je soubor delší než 31s, ořízneme ho od konce (vždy posledních 30s)
    elif df['sec_orig'].iloc[-1] > 31:
        cas_zacatku = df['sec_orig'].iloc[-1] - 30
        # Najdeme index nejbližší hodnotě (v R: which.min(abs(...)) - 1)
        idx_start = (df['sec_orig'] - cas_zacatku).abs().idxmin()
        df = df.iloc[idx_start:].copy()
        
        # Kontrola offsetu po ořezu zacátku
        if df['sec_orig'].iloc[0] > 3:
            df['sec_orig'] = df['sec_orig'] - df['sec_orig'].iloc[0]

    # Vytvoření finální čisté osy 0-30s pro výpočty
    df['sec'] = df['sec_orig'] - df['sec_orig'].iloc[0]
    df = df[df['sec'] <= 30.5].copy().reset_index(drop=True)
    
    for col in [p_col_raw, tr_col, hr_col]:
        if col: df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

    milestones, indices = [5, 10, 15, 20, 25], [0]
    for m in milestones:
        mask = df['sec'] >= m
        if mask.any(): indices.append(mask.values.argmax())
    indices.append(len(df))
    radky5s = int(round(np.mean(np.diff(indices)))) if len(indices) > 1 else 1
    
    df['RM5'] = df[p_col_raw].rolling(window=radky5s).mean()
    df['AvP_dopocet'] = df[p_col_raw].expanding().mean()
    
    pp = round(df[p_col_raw].max(), 0)
    minp = round(df[p_col_raw].iloc[len(df)//2:].min(), 0)
    pp5s, minp5s = round(df['RM5'].max(), 1), round(df['RM5'].min(), 1)
    avgp = round(df[p_col_raw].mean(), 1)
    total_work_j = df['AvP_dopocet'].mean() * 30 
    
    return {
        "df": df, "p_col": p_col_raw, "PP": pp, "Pmin": minp, "Drop": pp - minp, "AvgP": avgp,
        "TotalWork_kJ": round(total_work_j / 1000, 1), "TotalWork_J": total_work_j,
        "IU": round(((pp5s - minp5s) / pp5s) * 100, 1) if pp5s > 0 else 0,
        "PP5s": pp5s, "Pmin5s": minp5s, "Turns": int(df[tr_col].iloc[-1]) if tr_col else 0,
        "HRmax": int(df[hr_col].max()) if hr_col else 0
    }

def get_wingate_history(paths, athlete_info):
    history = []
    athlete_id = athlete_info['ID']
    folders = [("wingate", "Aktuální"), ("srovnani", "Srovnání 1"), ("srovnani2", "Srovnání 2")]
    somato_records = athlete_info.get('All_Records', [])[::-1] 
    
    for i, (key, label) in enumerate(folders):
        folder_path = paths.get(key)
        if not folder_path or folder_path == "Nenalezeno": continue
        f_path = Path(folder_path) / f"{athlete_id}.txt"
        
        if f_path.exists():
            res = process_single_wingate_file(f_path)
            s_record = somato_records[i] if i < len(somato_records) else somato_records[-1]
            weight = float(s_record.get('Weight', athlete_info['Weight']))
            
            res.update({
                "Label": label, "Weight": weight,
                "Fat": round(float(s_record.get('Fat', 0)), 1),
                "ATH": round(float(s_record.get('ATH', 0)), 1),
                "LA": round(float(s_record.get('LA', 0)), 1),
                "PP_kg": round(res["PP"] / weight, 2),
                "Work_TH": int(res["TotalWork_J"] / weight),
                "Date": s_record.get('Date_measurement').strftime('%d/%m/%Y') if hasattr(s_record.get('Date_measurement'), 'strftime') else str(s_record.get('Date_measurement')),
                "p_col": res["p_col"]
            })
            history.append(res)
    return history

SPORTS_NORMS = {
    "Hokej: dospělí": {"FVC": 4.7, "FEV1": 4.7, "VO2max": 58.0, "PowerVO2": 4.5, "Pmax": 15.7, "SJ": 45, "ANC": 365},
    "Hokej: junioři": {"FVC": 4.7, "FEV1": 4.7, "VO2max": 58.0, "PowerVO2": 4.4, "Pmax": 15.3, "SJ": 42, "ANC": 330},
    "Hokej: dorost":  {"FVC": 4.7, "FEV1": 4.7, "VO2max": 58.0, "PowerVO2": 4.4, "Pmax": 14.6, "SJ": 42, "ANC": 320},
    "Gymnastika":    {"FVC": 3.8, "FEV1": 3.1, "VO2max": 48.0, "PowerVO2": 3.3, "Pmax": 13.0, "SJ": 35, "ANC": 300}
}


def prepare_spiro_raw_data(df):
    """Převede čas 't' na relativní sekundy od začátku zátěže"""
    # 1. Vyčištění formátu (čárka -> tečka)
    df['t'] = df['t'].astype(str).str.replace(',', '.')
    
    # 2. Převod na datetime objekty
    df['t_dt'] = pd.to_datetime(df['t'], format='%H:%M:%S.%f', errors='coerce').fillna(
                 pd.to_datetime(df['t'], format='%H:%M:%S', errors='coerce'))
    
    # 3. Výpočet relativního času (sekundy od startu)
    df['rel_time'] = (df['t_dt'] - df['t_dt'].min()).dt.total_seconds()
    
    # 4. Výpočet VT_5s (plovoucí průměr) pro tabulkové hodnoty
    df['VT_5s'] = df['VT'].rolling(window=5, min_periods=1, center=False).mean()
    
    return df

def process_spiro_data(file_path, weight, sport, units_switch=False):
    # Načtení celého Excelu bez hlaviček pro volné hledání v info bloku
    raw_df = pd.read_excel(file_path, header=None)
    
    # 1. Identifikace dělícího řádku "BF" pro info blok
    bf_mask = raw_df.iloc[:, 0].astype(str).str.strip() == "BF"
    if not bf_mask.any():
        raise ValueError("V souboru nebyl nalezen klíčový řádek 'BF'.")
    
    bf_row_idx = raw_df[bf_mask].index[0]
    spiro_info = raw_df.iloc[:bf_row_idx + 1].copy()
    
    # 2. Pomocná funkce pro info blok s přesnou shodou (==)
    def get_info_val(label, col_idx):
        try:
            mask = spiro_info.iloc[:, 0].astype(str).str.strip() == label
            if not mask.any(): return 0.0
            val = spiro_info[mask].iloc[0, col_idx]
            if pd.isna(val) or val == "-": return 0.0
            return float(str(val).replace(',', '.').split()[0])
        except: return 0.0

    # Načtení sportovních norem (předpokládá existenci slovníku SPORTS_NORMS)
    norms = SPORTS_NORMS.get(sport, SPORTS_NORMS.get("hokej-dospělí", {}))

    # 3. Extrakce statických hodnot
    vo2_kg_measured = get_info_val("V'O2/kg", 11)
    tep_kyslik = get_info_val("V'O2/HR", 11)
    if units_switch:
        wr_measured = get_info_val("v", 14) # Index 14 odpovídá sloupci 15 v R
    else:
        wr_measured = get_info_val("WR", 11)
    wr_kg_measured = wr_measured / weight if weight else 0
    fvc_measured = get_info_val("FVC", 4) or get_info_val("VC", 2)
    fev1_measured = get_info_val("FEV1", 4) or get_info_val("FEV1", 2)

    # Výpočet procent nál. hodnoty
    vo2_norm_perc = round((vo2_kg_measured / norms.get("VO2max", 1)) * 100) if norms else 0
    vykon_norm_perc = round((wr_kg_measured / norms.get("PowerVO2", 1)) * 100) if norms else 0
    fvc_perc = round((fvc_measured / norms.get("FVC", 1)) * 100) if norms else 0
    fev1_perc = round((fev1_measured / norms.get("FEV1", 1)) * 100) if norms else 0

    # ANP logika
    tf_row = spiro_info[spiro_info.iloc[:, 0].isin(["TF", "SF"])]
    if not tf_row.empty:
        anp_raw = tf_row.iloc[0, 8] # Sloupec 9
        if pd.isna(anp_raw) or str(anp_raw).strip() == "-":
            anp = float(str(tf_row.iloc[0, 14]).replace(',', '.')) * 0.85 # Sloupec 15
        else:
            anp = float(str(anp_raw).replace(',', '.'))
    else: anp = 0

    # 4. Zpracování časové řady (pod řádkem "t")
    t_mask = raw_df.iloc[:, 0].astype(str).str.strip().str.lower() == "t"
    header_idx = raw_df[t_mask].index[0]
    data_df = raw_df.iloc[header_idx:].copy()
    data_df.columns = data_df.iloc[0].astype(str).str.strip()
    data_df = data_df.iloc[2:].reset_index(drop=True)

    # Mapování sloupců
    rename_map = {}
    for c in data_df.columns:
        c_clean = str(c).upper().replace("'", "").replace(".", "").strip()
        if "/" not in str(c):
            if c_clean == "VO2": rename_map[c] = "VO2"
            elif c_clean == "VE": rename_map[c] = "VE"
            elif c_clean in ["TF", "SF", "HR"]: rename_map[c] = "TF"
            elif c_clean == "VT": rename_map[c] = "VT"
            elif c_clean == "WR": rename_map[c] = "WR"
            elif c_clean == "RER": rename_map[c] = "RER"
            elif c_clean == "BF": rename_map[c] = "BF"
            elif c_clean == "FÁZE": rename_map[c] = "Fáze"

    data_df = data_df.rename(columns=rename_map)
    work_df = data_df[data_df["Fáze"].isin(["Zátěž", "Exercise"])].copy()

    for col in ["VO2", "VE", "TF", "VT", "WR", "RER", "BF"]:
        if col in work_df.columns:
            work_df[col] = pd.to_numeric(work_df[col].astype(str).str.replace(',', '.'), errors='coerce')

    # --- PŘÍPRAVA ČASU A VYHLAZENÍ PRO GRAFY ---
    work_df = prepare_spiro_raw_data(work_df) # Volání vaší nové funkce

    # Výpočet hranic zón (Logika navazujících hodnot jako v R)
    factor = anp / 0.85
    aer_do_val = int(round(factor * 0.75))
    smi_do_val = int(round(factor * 0.84))

    # 5. Výsledný slovník
    return {
        "VO2max": round(work_df["VO2"].max(), 1) if "VO2" in work_df.columns else 0.0,
        "VO2_kg": round(vo2_kg_measured, 1),
        "VO2_norm_perc": vo2_norm_perc,
        "vykon": int(wr_measured),
        "vykon_kg": round(wr_kg_measured, 1),
        "is_speed": units_switch,
        "vykon_norm_perc": vykon_norm_perc,
        "HRmax_Spiro": int(work_df["TF"].max()) if "TF" in work_df.columns else 0,
        "tep_kyslik": round(tep_kyslik, 1) if tep_kyslik else 0.0,
        "anp": int(anp),
        "fvc": round(fvc_measured, 2), 
        "fvc_perc": fvc_perc,
        "fev1": round(fev1_measured, 2), 
        "fev1_perc": fev1_perc,
        "pomer": round(fev1_measured/fvc_measured*100, 1) if fvc_measured else 0,
        "min_ventilace": round(get_info_val("V'E", 11), 1),
        "min_ventilace_opt": int(30 * fvc_measured),
        "dech_frek": int(get_info_val("BF", 11)),
        # Dechový objem vypočten z VT_5s dle R logiky
        "dech_objem": round(work_df["VT_5s"].max(), 2) if "VT_5s" in work_df.columns else 0.0,
        "dech_objem_perc": round((work_df["VT_5s"].max() / fvc_measured * 100)) if fvc_measured and "VT_5s" in work_df.columns else 0,
        "rer": round(work_df["RER"].max(), 2) if "RER" in work_df.columns else 0.0,
        "df": work_df,
        "zones": {
            "aer_od": "",
            "aer_do": aer_do_val,
            "smi_od": aer_do_val + 1, # Navazuje bez mezery
            "smi_do": smi_do_val,
            "ana_od": smi_do_val + 1, # Navazuje bez mezery
            "ana_do": ""
        }
    }

def process_radar_data(athlete, wingate, spiro, norms):
    """Vypočítá procenta pro radar chart dle R logiky"""
    # 1. Anaerobní část (Wingate)
    an_cap = wingate['TotalWork_J'] / athlete['Weight']
    hg_anckg = round((an_cap / norms.get('ANC', 1)) * 100, 1)
    hg_ppkg = round((wingate['PP_th'] / norms.get('Pmax', 1)) * 100, 1)
    
    # 2. Skokanská část (SJ)
    sj = athlete.get('SJ', 0)
    hg_sj = round((sj / norms.get('SJ', 1)) * 100, 1) if sj else None

    # 3. Aerobní část (Spiro) - PŘIDÁNA OCHRANA PROTI CHYBĚJÍCÍM DATŮM
    hg_vo2max = 0
    hg_vo2vykon = 0
    if spiro:
        hg_vo2max = round((spiro.get('VO2_kg', 0) / norms.get('VO2max', 1)) * 100, 1)
        hg_vo2vykon = round((spiro.get('vykon_kg', 0) / norms.get('PowerVO2', 1)) * 100, 1)

    # Sestavení dat pro graf
    radar_data = {
    "labels": [
        r"$\mathbf{VO_2max\ (ml/min/kg)}$", 
        r"$\mathbf{Anaerobní\ kapacita\ (J/kg)}$", 
        r"$\mathbf{Výkon\ Wingate\ (W/kg)}$", 
        r"$\mathbf{Squat\ Jump\ (cm)}$", 
        r"$\mathbf{Výkon\ VO_2max\ (W/kg)}$"
    ],
    "values": [hg_vo2max, hg_anckg, hg_ppkg, hg_sj, hg_vo2vykon]
}
    
    # Odstranění SJ, pokud neexistuje
    if hg_sj is None:
        radar_data["labels"].pop(3)
        radar_data["values"].pop(3)
        
    return radar_data