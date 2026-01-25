import os
os.environ["GIO_USE_VFS"] = "local"
os.environ["G_MESSAGES_DEBUG"] = ""
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
import pandas as pd
from datetime import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from functools import partial
import processor
import graphics_engine
import report_generator
import base64
import sys
import shutil

def get_resource_path(relative_path):
    """ Získá absolutní cestu k prostředkům (logo, atd.) uvnitř EXE i mimo něj. """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def get_base64_img(path):
    """ Převede obrázek na Base64 řetězec pro přímé vložení do HTML/PDF. """
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
            return f"data:image/png;base64,{encoded}"
    except Exception:
        return ""

def process_individual_athlete(athlete_id, report_type, paths, sport, team, units_toggle=False):
    """
    Zpracuje jednoho sportovce a vrátí status a data pro souhrnný excel.
    Všechny grafy a loga jsou převedeny na Base64 pro 100% stabilitu v PDF.
    """
    try:
        # 1. Načtení základních dat
        athlete_info = processor.load_athlete_info(paths.get('antropometrie'), athlete_id)
        if not athlete_info: 
            return f"ID {athlete_id}: Nenalezeno v antropometrii", None
        
        wingate_history = processor.get_wingate_history(paths, athlete_info)
        current_test = None
        spiro_results = None
        
        # 2. Příprava složky pro dočasné grafy (u EXE složky)
        temp_dir = Path("temp_plots") / str(athlete_id)
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        plot_paths = {"wingate": None, "spiro": None, "radar": None}

        # 3. Zpracování Wingate historie
        if wingate_history:
            at = athlete_info
            for w_item in wingate_history:
                w_w = w_item.get("Weight", at["Weight"])
                w_a = w_item.get("ATH", at["ATH"])
                
                w_item.update({
                    "PP_th": round(w_item.get("PP", 0) / w_w, 1) if w_w else 0,
                    "PP_ath": round(w_item.get("PP", 0) / w_a, 1) if w_a else 0,
                    "Pmin_th": round(w_item.get("Pmin", 0) / w_w, 1) if w_w else 0,
                    "Pmin_ath": round(w_item.get("Pmin", 0) / w_a, 1) if w_a else 0,
                    "Drop_th": round(w_item.get("Drop", 0) / w_w, 1) if w_w else 0,
                    "Drop_ath": round(w_item.get("Drop", 0) / w_a, 1) if w_a else 0,
                    "Work_th": int(w_item.get("TotalWork_J", 0) / w_w) if w_w else 0,
                    "Work_ath": int(w_item.get("TotalWork_J", 0) / w_a) if w_a else 0
                })

            current_test = next((t for t in wingate_history if t["Label"] == "Aktuální"), wingate_history[0])
            
            # Generování a převod Wingate grafu
            p1_path = str((temp_dir / "p1.png").absolute())
            graphics_engine.create_wingate_plot(wingate_history, p1_path)
            plot_paths["wingate"] = get_base64_img(p1_path)

        # 4. Zpracování Spirometrie
        if "Spiro" in report_type:
            spiro_dir = paths.get('spiro')
            if spiro_dir:
                spiro_path = Path(spiro_dir) / f"{athlete_id}.xlsx"
                if spiro_path.exists():
                    spiro_results = processor.process_spiro_data(spiro_path, athlete_info['Weight'], sport, units_toggle)
                    
                    # Generování a převod Spiro grafu
                    p2_path = str((temp_dir / "p2.png").absolute())
                    graphics_engine.create_spiro_plot(spiro_results['df'], p2_path)
                    plot_paths["spiro"] = get_base64_img(p2_path)

        # 5. Zpracování Radarového grafu
        if current_test and spiro_results:
            norms = processor.SPORTS_NORMS.get(sport, processor.SPORTS_NORMS.get("Hokej: dospělí", {}))
            radar_data = processor.process_radar_data(athlete_info, current_test, spiro_results, norms)
            
            # Generování a převod Radar grafu
            p3_path = str((temp_dir / "p3.png").absolute())
            graphics_engine.create_radar_plot(radar_data, p3_path)
            plot_paths["radar"] = get_base64_img(p3_path)
            
        # 6. Načtení loga fakulty jako Base64 pro patičku PDF
        logo_base64 = get_base64_img(get_resource_path("logo.png"))

        # 7. Sestavení dat pro report_generator
        report_data = {
            "athlete": athlete_info, 
            "wingate": current_test, 
            "spiro": spiro_results, 
            "history": wingate_history, 
            "plots": plot_paths, 
            "sport": sport, 
            "team": team, 
            "report_type": report_type,
            "logo_base64": logo_base64,
            "current_year": datetime.now().year
        }
        
        # 8. Uložení PDF
        output_folder = Path(paths.get('main_folder')) / "reporty"
        output_folder.mkdir(exist_ok=True)
        report_generator.generate_pdf_report(report_data, output_folder)
        
        # --- NOVÉ: Úklid dočasné složky sportovce ---
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            
        return f"ID {athlete_id}: Hotovo", report_data

    except Exception as e:
        # Úklid i v případě chyby
        if 'temp_dir' in locals() and temp_dir.exists():
            shutil.rmtree(temp_dir)
        return f"ID {athlete_id}: Chyba - {str(e)}", None

def save_aggregate_results(data_list, team, main_folder, is_single=None):
    """Sestaví a uloží souhrnné tabulky do kořenové složky projektu. Pokud je is_single, přidá ID do názvu."""
    timestamp = datetime.now().strftime("%d-%m_%H-%M")
    vysledky_base = Path(main_folder) / "vysledky"
    vysledky_base.mkdir(exist_ok=True)
    
    # Prefix pro jméno souboru při individuálním generování
    file_prefix = f"{is_single}_" if is_single else ""
    
    logs = []

    # 1. HLAVNÍ DATABÁZE (Wingate + Antropo) - ROZŠÍŘENO O HISTORII
    db_rows = []
    for d in data_list:
        if not d['history']: continue 
        at = d['athlete']
        
        # Pro každého sportovce přidáme řádek pro každý dostupný test (Aktuální i Srovnání)
        for w in d['history']:
            db_rows.append({
                "id": at['ID'], 
                "Name": at['Name'], 
                "Test": w.get('Label'), # Odlišení řádků (Aktuální / Srovnání)
                "Date_meas.": w.get('Date'), # Datum konkrétního testu
                "Sport": d['sport'], 
                "Team": d['team'], 
                "Age": at['Age'],
                "Weight": w.get('Weight'), # Historická váha k danému testu
                "Fat (%)": w.get('Fat'), 
                "ATH": w.get('ATH'),
                "Turns": w.get('Turns', 0), 
                "Pmax (W)": w.get('PP', 0),
                "Pmax_kg (W/kg)": w.get('PP_th', 0),
                "Pmax/kgATH (W/kg)": round(w.get('PP', 0) / w.get('ATH', 1), 2) if w.get('ATH') else 0,
                "Pmin (W)": w.get('Pmin', 0), 
                "Avg_power (W)": w.get('AvgP', 0),
                "Pmax_5s (W)": w.get('PP5s', 0), 
                "IU (%)": w.get('IU', 0),
                "Work (kJ)": w.get('TotalWork_kJ', 0), 
                "Work (J/kg)": w.get('Work_th', 0),
                "Anc/kg (J/kg)": w.get('Work_th', 0),
                "HR_max (BPM)": w.get('HRmax', 0), 
                "La_max (mmol/l)": w.get('LA', 0) # Laktát z konkrétního testu
            })
    
    # EXPORT JEN POKUD JSOU DATA WINGATE (aspoň jedna hodnota Pmax > 0)
    if db_rows and any(row["Pmax (W)"] > 0 for row in db_rows):
        try:
            file_db = vysledky_base / f"{file_prefix}vysledek_{team}_{timestamp}.xlsx"
            pd.DataFrame(db_rows).to_excel(file_db, index=False)
            # ZMĚNA: Přidáno "v:" a absolutní cesta pro aktivaci tlačítek v app.py
            logs.append(f"✅ Wingate excel uložen v: {file_db.absolute()}")
        except Exception as e:
            logs.append(f"❌ Chyba při ukládání Wingate excelu: {str(e)}")

    # 2. SPIRO DATABÁZE (Zůstává jeden řádek na sportovce pro aktuální měření)
    spiro_rows = []
    for d in data_list:
        if not d['spiro']: continue
        at, sp = d['athlete'], d['spiro']
        row = {
            "Date meas.": at['Date_measurement'], "Name": at['Name'],
            "Weight": at['Weight'], "Fat": at['Fat'],
            "VO2max (l)": sp.get('VO2max', 0), "VO2max (ml/kg/min)": sp.get('VO2_kg', 0),
        }
        if sp.get('is_speed'): row["Rychlost (km/h)"] = sp.get('vykon', 0)
        else: row["Výkon (W)"] = sp.get('vykon', 0)
        
        row.update({
            "Výkon (l/kg)": sp.get('vykon_kg', 0), "HRmax (BPM)": sp.get('HRmax_Spiro', 0),
            "ANP (BPM)": sp.get('anp', 0), "Tep. kyslík (ml)": sp.get('tep_kyslik', 0),
            "VT (l)": sp.get('dech_objem', 0), "RER": sp.get('rer', 0),
            "LaMax (mmol/l)": at.get('LA', 0), "FEV1 (l)": sp.get('fev1', 0), "FVC (l)": sp.get('fvc', 0),
            "Aerobní Z. do": sp['zones']['aer_do'], "Smíšená Z. od": sp['zones']['smi_od'],
            "Smíšená Z. do": sp['zones']['smi_do'], "Anaerobní Z. od": sp.get('anp', 0)
        })
        spiro_rows.append(row)

    # EXPORT JEN POKUD JSOU DATA SPIRO (aspoň jedna hodnota VO2max > 0)
    if spiro_rows and any(row["VO2max (ml/kg/min)"] > 0 for row in spiro_rows):
        try:
            sp_dir = vysledky_base / "spiro"
            sp_dir.mkdir(parents=True, exist_ok=True)
            file_spiro = sp_dir / f"{file_prefix}spiro_vysledek_{team}_{timestamp}.xlsx"
            df_sp = pd.DataFrame(spiro_rows).sort_values(by="VO2max (ml/kg/min)", ascending=False)
            df_sp.to_excel(file_spiro, index=False)
            # ZMĚNA: Přidáno "v:" a absolutní cesta pro aktivaci tlačítek v app.py
            logs.append(f"✅ Spiro excel uložen v: {file_spiro.absolute()}")
        except Exception as e:
            logs.append(f"❌ Chyba při ukládání spiro excelu: {str(e)}")
            
    return logs

def run_individual_generation(athlete_id, report_type, paths, sport, team, toggle_switch):
    """Proces pro jedno ID - vygeneruje report i Excel."""
    res_msg, report_data = process_individual_athlete(
        athlete_id, report_type, paths, sport, team, units_toggle=(toggle_switch == "True")
    )
    
    if report_data:
        excel_logs = save_aggregate_results([report_data], team, paths.get('main_folder'), is_single=athlete_id)
        return [res_msg] + excel_logs
    return [res_msg]

def run_multisession_generation(df_comparison, paths, sport, team, toggle_switch):
    to_process = df_comparison[~df_comparison["Report"].str.contains("FAILED|Missing")].copy()
    if to_process.empty: return []
    
    # Omezení počtu procesů (max 6, i když máš víc jader) pro stabilitu na Windows
    num_workers = min(6, max(1, os.cpu_count() - 1))
    
    executor = ProcessPoolExecutor(max_workers=num_workers)
    try:
        worker = partial(process_individual_athlete, paths=paths, sport=sport, team=team, units_toggle=(toggle_switch == "True"))
        results_raw = list(executor.map(worker, to_process['ID'], to_process['Report']))
    finally:
        # Vynucené vyčištění procesů (SpawnProcess-X) hned po skončení
        executor.shutdown(wait=True)
    
    status_messages = [res[0] for res in results_raw]
    successful_data = [res[1] for res in results_raw if res[1] is not None]
    
    if successful_data:
        excel_logs = save_aggregate_results(successful_data, team, paths.get('main_folder'))
        status_messages.extend(excel_logs)
        
    return status_messages