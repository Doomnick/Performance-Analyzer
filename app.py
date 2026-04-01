import os
os.environ["GIO_USE_VFS"] = "local"
os.environ["G_MESSAGES_DEBUG"] = ""
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
import pandas as pd
import threading
import webview 
import uvicorn
import subprocess
import urllib.request
import time
import json
import time
from pathlib import Path
from shiny import App, render, ui, reactive
import processor      # Výpočty a kontrola dat
import master_engine
import sys
import asyncio 
import socket


def get_resource_path(relative_path):
    """ Získá cestu k souborům pro skript i pro zabalené .exe """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)  # Paralelní generování PD

# Konfigurace pro kontrolu (odpovídá vašemu GitHubu)
APP_VERSION = "1.0.02"
GITHUB_USER = "Doomnick"
GITHUB_REPO = "Performance-Analyzer"
HASH_FILE = "file_hashes.txt"
LAST_CHECK_FILE = "last_check_time.txt"



# --- POMOCNÉ FUNKCE PRO WINDOWS ---
def show_in_explorer(folder_path, id_name, module_type):
    if not folder_path or not os.path.exists(folder_path): return
    target_file = None
    p = Path(folder_path)
    pattern = f"*{id_name}*.xls*" if module_type == "spiro" else f"*{id_name}*.txt"
    files = list(p.glob(pattern))
    if files: target_file = files[0]
    if target_file and target_file.exists():
        subprocess.run(['explorer', '/select,', str(target_file)])

def open_excel_directly(folder_path):
    if not folder_path or not os.path.exists(folder_path): return
    excel_files = list(Path(folder_path).glob("*.xls*"))
    if excel_files: os.startfile(str(excel_files[0]))

# --- UI ČÁST ---
app_ui = ui.page_navbar(
    ui.head_content(
        ui.tags.script("""
            Shiny.addCustomMessageHandler('copy_text', function(message) {
                navigator.clipboard.writeText(message);
            });
        """),
    
  ui.tags.style("""
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            
            body { background-color: #f8f9fa; font-family: 'Inter', sans-serif; }
            
            /* ÚPLNÉ ODSTRANĚNÍ DÍRY NAHOŘE (MEZI NAVBARem A OBSAHEM) */
            .container-fluid { padding: 0 !important; max-width: 100% !important; }
            .navbar > .container-fluid {
                max-width: 100% !important; /* Změněno z 1400px pro ukotvení vlevo */
                margin-left: 0 !important;   /* Změněno z 0 auto */
                margin-right: 0 !important;
                display: flex !important;
                justify-content: flex-start !important;
                padding-left: 15px !important;
                padding-right: 20px !important;
                padding-bottom: 0 !important;
            }
                
            .navbar { 
                background-color: #eef6ff !important; 
                border-bottom: 1px solid #d0e3ff; 
                margin-bottom: 0 !important; 
                padding-bottom: 0 !important;
                min-height: 60px;
            }

            /* 2. PŘEPÍNAČE JAKO KARTY (TABS) */
            .navbar-nav {
                align-items: flex-end !important; /* Zarovná karty k dolní lince */
                height: 100%;
                gap: 2px !important;
            }

            .nav-link { 
                color: #666 !important; 
                font-weight: 500 !important;
                padding: 8px 20px !important;
                margin-right: 0px !important;
                border: 1px solid transparent !important;
                border-radius: 8px 8px 0 0 !important; /* Zakulacení nahoře */
                transition: all 0.2s ease !important;
                background-color: rgba(255, 255, 255, 0.3) !important;
            }

            /* Vzhled aktivní karty */
            .nav-link.active { 
                color: #007bff !important; 
                font-weight: 700 !important; 
                background-color: #ffffff !important; /* Bílá karta */
                border: 0px solid #d0e3ff !important;
                border-bottom: 1px solid #ffffff !important; 
                margin-bottom: -5px !important;              
                position: relative;                           
                z-index: 10;                                  
            }

            .nav-link:hover:not(.active) {
                background-color: rgba(255, 255, 255, 0.8) !important;
                color: #007bff !important;
                margin-bottom: -5px !important;    
            }
            
            /* Vynulování mezer u vnitřních panelů a karet */
            .tab-content, .tab-pane { padding-top: 20 !important; margin-top: 0 !important; }
            .card { margin-top: 0 !important; border-top-left-radius: 0; border-top-right-radius: 0; }
            .bslib-sidebar-layout { 
                height: calc(100vh - 60px) !important; 
                margin: 0 !important;
                border: none !important;
            }
            .bslib-sidebar-layout > .main { padding-top:  !important; }

            /* SIDEBAR - KOMPAKTNÍ S VÝRAZNOU BARVOU */
            .sidebar { 
                background-color: #eef6ff !important; 
                border-right: 1px solid #91a1ad !important; 
                padding: 0px 0px !important; 
                font-size: 0.88rem !important; 
                padding-top: 0 !important;
            }

            /* SROVNÁNÍ NADPISŮ DO STEJNÉ VÝŠKY */
            .sidebar-title { 
                margin-top: 0 !important; 
                margin-bottom: 0 !important; 
                line-height: 2px !important; 
                height: 2px;
                display: flex;
                align-items: center;
            }
            .sidebar-header-row { 
                display: flex; justify-content: flex-start; align-items: center; 
                gap: 0px; margin-bottom: 0px; margin-top: 0px; height: 0px;
            }
            .sidebar-title { font-weight: 700; color: #2c3e50; font-size: 0.9rem; }
            
            /* ČERNÉ NADPISY POLÍ */
            .sidebar label { 
                font-size: 0.78rem; font-weight: 700; color: #000000 !important; 
                text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 1px !important;
                margin-top: 4px;
            }

            .sidebar .form-control, .sidebar .form-select { 
                font-size: 0.85rem !important; height: auto !important; padding: 3px 6px !important; 
            }
            
            .sidebar hr { display: none !important; }
            .sidebar .shiny-input-container { margin-bottom: 2px !important; }
            .sidebar .btn { font-size: 0.85rem; padding: 2px 2px; }

            .btn-row { display: flex; gap: 4px; margin-bottom: 5px; }

            /* TABULKA - CENTROVÁNÍ */
            .shiny-data-grid .rt-td, .shiny-data-grid .rt-th { 
                display: flex !important; 
                align-items: center !important; 
                justify-content: center !important; 
            }
            .shiny-data-grid .rt-td:first-child, .shiny-data-grid .rt-th:first-child { 
                justify-content: flex-start !important; 
            }
                    

            @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            .animate-appearance { animation: slideIn 0.6s ease-out; }

            /* SLOŽKY A TLAČÍTKA */
            .folder-row { 
                display: flex; align-items: center; justify-content: space-between; 
                padding: 4px 10px; margin-bottom: 2px; border-radius: 6px;
                background: #ffffff; border: 1px solid #eee; font-size: 0.85rem;
                transition: all 0.1s;
            }
            .folder-row:hover { background: #f0f7ff; border-color: #007bff; }
            .folder-label { font-weight: 600; margin-right: 8px; display: inline-block; }
            .record-count { font-size: 0.78rem; color: #6c757d; font-style: italic; }

            .action-link { 
                display: inline-flex !important; 
                align-items: center !important; 
                justify-content: center !important; 
                height: 24px; 
                padding: 0 8px !important;
                font-size: 0.72rem; 
                font-weight: 600; 
                text-decoration: none; 
                color: #007bff; 
                border-radius: 4px; 
                background: #eef6ff; 
                margin-left: 2px;
                line-height: 1 !important;
            }
            .remove-link { color: #dc3545 !important; background: #fff5f5; }
                      
            .header-tip {
                font-size: 0.75rem;
                font-weight: normal;
                color: #6c757d;
            }

            /* CESTA K PROJEKTU - BOX */
            .project-path-box {
                background: #ffffff; border: 1px solid #d0e3ff; border-radius: 6px;
                padding: 5px 12px; font-size: 0.8rem; color: #444;
                margin-bottom: 8px; display: flex; align-items: center;
                justify-content: space-between; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            }
            .path-text { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 55%; font-family: monospace; }

            /* RADIO BUTTONY NEJSOU BOLD */
            .sidebar .shiny-options-group label { 
                font-weight: 400 !important; 
                text-transform: none !important; 
                letter-spacing: 0px !important;
            }
                      
            /* ODSTRANĚNÍ DÍRY V KONZOLI */
            .card-body { padding-top: 0 !important; }
            .gen-console, .stats-log { 
                background-color: #ffffff; 
                color: #333; 
                padding: 0px !important; 
                border-radius: 1px; 
                font-family: 'Consolas', monospace; 
                font-size: 0.85rem; 
                min-height: 250px;
                border: 1px solid #ddd; 
                border-left: 5px solid #28a745; 
                white-space: pre-wrap;
            }
            .gen-console pre, .stats-log pre {
                margin: 0 !important;
                padding: 10px 12px !important;
            }

            .stats-log { border-left-color: #007bff; min-height: auto; }
            .selection-card { border: 2px solid #007bff; background-color: #f0f7ff; margin-bottom: 8px; position: relative; padding: 10px; border-radius: 8px; }
            .close-btn { position: absolute; top: 4px; right: 8px; cursor: pointer; font-size: 1.1rem; color: #666; text-decoration: none; }
        """)
    ),
    ui.nav_panel(
        "📂 Data a kontrola",
        ui.layout_sidebar(
            ui.sidebar(
                ui.div(ui.h5("Konfigurace", class_="sidebar-title"), class_="sidebar-header-row"),
                
                ui.div(
                    ui.input_action_button("select_folder", "Vybrat složku projektu", class_="btn-primary", style="flex-grow: 1;"),
                    ui.input_action_button("help_btn", "?", class_="btn-outline-info", style="width: 35px; font-weight: bold;"),
                    class_="btn-row"
                ),
                
                ui.output_ui("dynamic_spiro_ui"),
                ui.output_ui("dynamic_config_ui"),
                ui.output_ui("action_buttons_ui"),
                
                ui.output_ui("action_buttons_ui"),
                
                width=292,
            ),
            ui.h6("Stav datových zdrojů:", style="font-weight:700; color:#555; margin-bottom:0px; margin-top:8px; padding-bottom:0px;"),
            ui.output_ui("project_path_ui"),
            ui.output_ui("interactive_folder_status"),
            
            ui.output_ui("selection_actions_ui"),
            ui.output_ui("table_container_ui")
        )
    ),
   ui.nav_panel(
        "📝 Výsledky",
        ui.card(
            ui.card_header("Rychlé akce po exportu"),
            ui.output_ui("dynamic_results_buttons"), # Container pro tlačítka
            style="margin-bottom: 15px;"
        ),
        ui.card(ui.card_header("Souhrnná statistika"), ui.div(ui.output_text_verbatim("category_stats_output"), class_="stats-log")),
        ui.card(ui.card_header("Průběh generování"), ui.div(ui.output_text_verbatim("generation_console_output"), class_="gen-console"))
    ),

    ui.nav_spacer(),  # Vyplní veškeré volné místo uprostřed
    ui.nav_control(
        ui.span(
            f"v{APP_VERSION}", 
            style="color: #6c757d; font-size: 0.8rem; padding-top: 18px; display: inline-block; margin-right: 15px;"
        )
    ),

    title=ui.div(
        ui.tags.img(src="image.png", height="35px", style="margin-right: 12px;"),
        "Performance Analyzer",
        style="display: flex; align-items: center;"
    ),
    id="main_nav",
)

def server(input, output, session):
    last_wingate_path = reactive.Value(None)
    last_spiro_path = reactive.Value(None)
    main_folder_path = reactive.Value(""); detected_paths = reactive.Value({}); comparison_data = reactive.Value(None) 
    last_analysis_inputs = reactive.Value({}); selected_id = reactive.Value(None); gen_log = reactive.Value("Systém připraven...")
   

    @render.ui
    def dynamic_results_buttons():
        # Získání cest z reaktivních proměnných
        w_path = last_wingate_path.get()
        s_path = last_spiro_path.get()
        base = main_folder_path.get()
        
        btns = []
        
        # Pokud byl vygenerován alespoň jeden výsledek, zobrazíme tlačítka
        if w_path or s_path:
            # 1. Tlačítko pro PDF reporty (vždy první)
            btns.append(ui.input_action_button("open_pdf_folder", "📂 Složka PDF reportů", class_="btn-primary"))
            
            # 2. Specifické výsledky (Spiro nebo Wingate)
            if w_path:
                btns.append(ui.input_action_button("open_wingate_res", "📊 Otevřít Wingate (XLS)", class_="btn-success"))
            if s_path:
                btns.append(ui.input_action_button("open_spiro_res", "🫁 Otevřít Spiro (XLS)", class_="btn-success"))
            
            # 3. Složka s XLS výsledky (vždy poslední)
            btns.append(ui.input_action_button("open_res_folder", "📁 Složka XLS výsledků", class_="btn-primary"))
            
            return ui.div(*btns, style="display: flex; gap: 10px; margin-top: 5px; flex-wrap: wrap;")
        
        return ui.p("Tlačítka se zobrazí po dokončení exportu.", style="color: gray; font-style: italic;")

    @reactive.effect
    @reactive.event(input.open_pdf_folder)    
    def _open_pdf_fold():
        # Cesta k PDF reportům je definována v master_engine jako složka "reporty"
        base = main_folder_path.get()
        if not base: return
        
        path = os.path.join(base, "reporty")
        
        if os.path.exists(path):
            os.startfile(path)
        else:
            ui.notification_show("Složka s PDF reporty zatím neexistuje.", type="warning")
    
    
    @reactive.effect
    @reactive.event(input.open_wingate_res)
    def _open_w_res():
        path = last_wingate_path.get()
        if path and os.path.exists(path): os.startfile(path)

    @reactive.effect
    @reactive.event(input.open_spiro_res)
    def _open_s_res():
        path = last_spiro_path.get()
        if path and os.path.exists(path): os.startfile(path)

    @reactive.effect
    @reactive.event(input.open_res_folder)
    def _open_r_fold():
        # Získáme cestu k vybranému projektu
        base = main_folder_path.get()
        if not base: return
        
        # Sestavíme cestu ke složce výsledků v rámci projektu
        path = os.path.join(base, "vysledky")
        
        if os.path.exists(path):
            os.startfile(path)
        else:
            ui.notification_show("Složka s výsledky zatím neexistuje.", type="warning")

    @reactive.effect
    def check_updates_at_startup():
        print("\n[INFO] Kontrola aktualizace podle GitHub Release...")
        
        # 1. Časový zámek (3 minuty) zůstává stejný
        current_time = time.time()
        if os.path.exists(LAST_CHECK_FILE):
            try:
                with open(LAST_CHECK_FILE, "r") as f:
                    if (current_time - float(f.read().strip())) < 180: return 
            except: pass 

        try:
            # 2. Dotaz na NEJNOVĚJŠÍ RELEASE
            url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                remote_version = data['tag_name'].strip().lstrip('v') # Odstraní případné 'v' před číslem
                
                with open(LAST_CHECK_FILE, "w") as f:
                    f.write(str(current_time))

            print(f"[VERZE] Server: {remote_version} | Lokální: {APP_VERSION}")

            # 3. Porovnání verze
            if remote_version != APP_VERSION:
                print("[UPDATE] Nalezena nová verze Release!")
                m = ui.modal(
                    ui.tags.div(
                        ui.h4(f"🚀 Nová verze {remote_version} je připravena!"),
                        ui.p(f"Vaše aktuální verze je {APP_VERSION}. Chcete aktualizovat?"),
                        style="padding: 10px;"
                    ),
                    title="Nalezena aktualizace",
                    footer=ui.tags.div(
                        ui.input_action_button("confirm_update", "Aktualizovat", class_="btn-primary"),
                        ui.modal_button("Zrušit"),
                    ),
                    easy_close=False
                )
                ui.modal_show(m)

        except Exception as e:
            print(f"[CHYBA] Kontrola Release selhala: {e}")

    # Reakce na kliknutí na "Aktualizovat nyní"
    @reactive.effect
    @reactive.event(input.confirm_update)
    def run_update_process():
        import shutil
        ui.modal_remove()
        
        try:
            # 1. Cesta k updateru uvnitř _internal
            source_bat = get_resource_path("update.bat")
            # 2. Cesta do kořene (vedle .exe)
            target_bat = os.path.join(os.getcwd(), "update.bat")
            
            # 3. Zkopírujeme ho ven
            shutil.copy2(source_bat, target_bat)
            
            # 4. Spustíme ho z kořene
            subprocess.Popen(["cmd", "/c", "start", "update.bat"], shell=True)
            os._exit(0)
        except Exception as e:
            print(f"[CHYBA] Příprava aktualizace selhala: {e}")

    def trigger_analysis():
        paths = detected_paths.get()
        if not paths: return
        
        # Resetujeme výběr, ale bez spinnerů a oken
        selected_id.set(None)
        
        cur_in = {"wingate": paths["wingate"] is not None, "spirometrie": paths["spiro"] is not None, "srovnani": paths["srovnani"] is not None, "srovnani2": paths["srovnani2"] is not None}
        last_analysis_inputs.set(cur_in)
        try:
            #build_comparison_df běží synchronně, jak jste chtěl
            df = processor.build_comparison_df(paths, cur_in)
            comparison_data.set(df)
        except Exception as e: 
            ui.notification_show(f"Chyba při skenování: {e}", type="error")

    def perform_full_scan():
        base_path = main_folder_path.get()
        if not base_path or not os.path.exists(base_path): return
        try:
            all_dirs = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
            
            # Upravená detekce pro Antropometrii (přidáno 'antropo')
            som_p = next((os.path.join(base_path, d) for d in all_dirs if d.lower().startswith(("somato", "antropo"))), None)
            
            win_p = next((os.path.join(base_path, d) for d in all_dirs if d.lower().startswith("wingate")), None)
            
            # Upravená detekce pro Spirometrii (přidáno 'vo2')
            spi_p = next((os.path.join(base_path, d) for d in all_dirs if d.lower().startswith(("spiro", "vo2"))), None)
            
            sr_p, sr2_p = None, None
            if win_p:
                subs = [d for d in os.listdir(win_p) if os.path.isdir(os.path.join(win_p, d))]
                if "srovnani" in subs: sr_p = os.path.join(win_p, "srovnani")
                if "srovnani2" in subs: sr2_p = os.path.join(win_p, "srovnani2")
            
            detected_paths.set({"antropometrie": som_p, "wingate": win_p, "spiro": spi_p, "srovnani": sr_p, "srovnani2": sr2_p})
            trigger_analysis()
        except: pass

    @render.ui
    def dynamic_config_ui():
        if not main_folder_path.get():
            return None
            
        return ui.div(
            ui.input_select("sport", "Kategorie:", 
                            choices=["Hokej: dospělí", "Hokej: junioři", "Hokej: dorost", "Gymnastika"]),
            ui.input_text("team", "Název týmu:", ""),
            style="margin-top: 10px;"
        )
    
    @render.ui
    def action_buttons_ui():
        if not main_folder_path.get(): return None
        return ui.div(
            ui.input_action_button("check", "Obnovit data", class_="btn-outline-primary w-100", style="margin-bottom: 2px;"),
            ui.input_action_button("generate_pdf", "Generovat PDF reporty", class_="btn-success w-100", style="font-weight:600"),
            style="margin-top: 3px;"
        )

    @render.ui
    def project_path_ui():
        path = main_folder_path.get()
        if not path: return None
        return ui.div(
            ui.div(
                ui.span("📁 ", style="font-size: 0.9rem; display: flex; align-items: center;"), 
                ui.span(path, class_="path-text"), 
                style="display: flex; align-items: center; gap: 5px; width: 55%;"
            ),
            ui.div(
                ui.input_action_link("open_main_dir", "Otevřít", class_="action-link"),
                ui.input_action_link("copy_path", "Kopírovat", class_="action-link"),
                ui.input_action_link("reset_app", "×", class_="action-link remove-link", style="font-size: 1rem; height: 24px; padding: 0 8px; display: flex; align-items: center;"),
                style="display: flex; gap: 3px; align-items: center;"
            ), class_="project-path-box", style="align-items: center;"
        )

    @reactive.effect
    @reactive.event(input.open_main_dir)
    def _open_folder():
        path = main_folder_path.get()
        if path and os.path.exists(path):
            os.startfile(path)

    @reactive.effect
    @reactive.event(input.copy_path)
    async def _copy():
        await session.send_custom_message('copy_text', main_folder_path.get())
        ui.notification_show("Cesta zkopírována do schránky", duration=2)

    @reactive.effect
    @reactive.event(input.reset_app)
    def _reset():
        main_folder_path.set(""); detected_paths.set({}); comparison_data.set(None)

    @reactive.effect
    @reactive.event(input.help_btn)
    def _help():
        m = ui.modal(
            ui.h6("Pravidla automatické detekce:"),
            ui.p("Pro úspěšnou detekci stačí, aby názvy podsložek v hlavní složce začínaly těmito slovy. Nezáleží na velikosti písmen:"),
            ui.tags.ul(
                ui.tags.li(ui.tags.b("Somato.../Antropo..."), " : Pro antropometrii. Musí obsahovat Excel s listem 'Data_Sheet'."),
                ui.tags.li(ui.tags.b("Wingate..."), " : Pro wingate testy. Obsahuje .txt soubory pojmenované dle ID."),
                ui.tags.li(ui.tags.b("Spiro.../Vo2..."), " : Pro spirometrii. Obsahuje .xlsx soubory pojmenované dle ID."),
                ui.tags.li(ui.tags.b("srovnani / srovnani2"), " : Volitelné podsložky (musí se jmenovat přesně takto) umístěné uvnitř složky Wingate.")
            ),
            ui.hr(),
            title="Nápověda", size="l", easy_close=True, footer=ui.modal_button("Zavřít")
        )
        ui.modal_show(m)
    @render.ui
    def dynamic_spiro_ui():
        paths = detected_paths.get(); spiro_dir = paths.get("spiro")
        if not spiro_dir or not os.path.exists(spiro_dir): return None
        initial_val = "False"
        files = list(Path(spiro_dir).glob("*.xls*"))
        if files:
            try:
                # Načtení do paměti, aby se soubor hned uvolnil
                import io
                with open(files[0], "rb") as f:
                    file_data = io.BytesIO(f.read())
                df_check = pd.read_excel(file_data, header=None, nrows=150)
                if any(df_check.iloc[:, 0].astype(str).str.strip().str.lower() == "v"): initial_val = "True"
            except: pass
        return ui.div(ui.input_radio_buttons("toggle_switch", "Metrika Spirometrie:", {"False": "Výkon (W)", "True": "Rychlost (km/h)"}, selected=initial_val, inline=True), style="margin-bottom: 2px;")

    @render.ui
    def table_container_ui():
        df = comparison_data.get()
        if df is None or df.empty: 
            return None
        
        return ui.div(
            ui.card(
                ui.card_header(
                    ui.div(
                        ui.span("🔍 Srovnávací tabulka ID"), 
                        ui.span("💡 Klikněte na řádek pro akce", class_="header-tip"),
                        style="display: flex; justify-content: space-between; align-items: center; width: 100%;"
                    )
                ),
                ui.output_data_frame("data_preview"),
            ),
            class_="animate-appearance"
        )

    @reactive.effect
    @reactive.event(main_folder_path)
    def _auto_scan(): perform_full_scan()

    @reactive.effect
    @reactive.event(input.check)
    def _manual_refresh(): trigger_analysis()

 
    is_generating = reactive.Value(False)  # add once in server scope

    
    @reactive.effect
    @reactive.event(input.generate_pdf)
    async def _generate():
        df = comparison_data.get()
        if df is None or df.empty:
            return

        # Sběr dat
        paths_local = detected_paths.get().copy() if detected_paths.get() else {}
        paths_local['main_folder'] = main_folder_path.get()
        sport_local = input.sport()
        team_local = input.team()
        t_switch_local = input.toggle_switch() if "toggle_switch" in input else "False"

        # 1. AKTIVNÍ ZOBRAZENÍ MODÁLU DO POPŘEDÍ
        ui.modal_show(ui.modal(
            ui.div(
                ui.tags.img(
                    src="loading.gif", 
                    style="width: 100%; height: auto; display: block; border-radius: 4px;"
                ),
                # Negativní margin vyruší výchozí padding (15px) těla modálu
                style="margin: -16px; border: none; overflow: hidden;" 
            ),
            title=None,
            easy_close=False,
            footer=None,
            size="s"  # Velikost "s" (small) je pro samotný GIF nejvhodnější
        ))
        
        is_generating.set(True)
        gen_id = ui.notification_show("⏳ Generuji reporty...", duration=None, type="message")

        try:
            # Výpočet v pozadí
            results = await asyncio.to_thread(
                master_engine.run_multisession_generation,
                df, paths_local, sport_local, team_local, t_switch_local,
            )

            # Zpracování výsledků
            log_entries = []
            last_w, last_s = None, None
            results_list = results if isinstance(results, list) else str(results).splitlines()
            for r in results_list:
                log_entries.append(r)
                r_low = r.lower()
                if "✅" in r and ("vysledky" in r_low or "výsledky" in r_low) and "v:" in r:
                    path = os.path.abspath(r.split("v:")[1].strip())
                    if os.path.exists(path):
                        if "wingate" in r_low: last_w = path
                        elif "spiro" in r_low: last_s = path

            # Aktualizace UI
            ui.update_navset("main_nav", selected="📝 Výsledky")
            gen_log.set("\n".join(log_entries))
            if last_w: last_wingate_path.set(last_w)
            if last_s: last_spiro_path.set(last_s)
            
            ui.notification_show("Generování dokončeno.", type="default", duration=7)

        except Exception as e:
            ui.notification_show(f"Chyba při generování: {e}", type="error")
            gen_log.set(f"[KRITICKÁ CHYBA] {e}\n\n" + gen_log.get())

        finally:
            # 2. AUTOMATICKÉ ODSTRANĚNÍ MODÁLU A NOTIFIKACE
            ui.modal_remove()
            ui.notification_remove(gen_id)
            is_generating.set(False)

    @reactive.effect
    @reactive.event(input.go_single_report)
    def _single_report():
        ix = input.data_preview_selected_rows()
        if not ix: return
        df = comparison_data.get()
        athlete_id = df.iloc[ix[0]]["ID"]
        report_type = df.iloc[ix[0]]["Report"]

        # Resetování tlačítek pro konkrétního sportovce
        last_wingate_path.set(None)
        last_spiro_path.set(None)

        ui.update_navset("main_nav", selected="📝 Výsledky")
        gen_id = ui.notification_show(f"Generuji report pro {athlete_id}...", duration=None, type="message")

        try:
            with ui.Progress(min=0, max=1) as p:
                p.set(message=f"Zpracovávám {athlete_id}...")
                
                paths = detected_paths.get()
                paths['main_folder'] = main_folder_path.get()
                t_switch = input.toggle_switch() if "toggle_switch" in input else "False"
                
                # Volání engine pro jednotlivce
                results = master_engine.run_individual_generation(athlete_id, report_type, paths, input.sport(), input.team(), t_switch)

                # --- JEDNOTNÉ A ROBUSTNÍ ZPRACOVÁNÍ CEST ---
                log_entries = []
                results_list = results if isinstance(results, list) else str(results).splitlines()

                for r in results_list:
                    log_entries.append(r)
                    r_low = r.lower()

                    if "✅" in r and ("vysledky" in r_low or "výsledky" in r_low):
                        try:
                            if "v:" in r:
                                path = os.path.abspath(r.split("v:")[1].strip())
                                if os.path.exists(path):
                                    if "wingate" in r_low: 
                                        last_wingate_path.set(path)
                                    elif "spiro" in r_low: 
                                        last_spiro_path.set(path)
                        except Exception as e:
                            print(f"[ERROR] Selhalo parsování cesty: {e}")
                
                current_log = gen_log.get()
                gen_log.set("\n".join(log_entries) + "\n\n" + current_log)
                p.set(1, message="Dokončeno")

            ui.notification_remove(gen_id)
            ui.notification_show(f"Hotovo pro {athlete_id}.", type="default", duration=5)
        except Exception as e:
            ui.notification_remove(gen_id)
            ui.notification_show(f"Chyba: {str(e)}", type="error")
            old_log = gen_log.get()
            gen_log.set(f"[CHYBA] {str(e)}\n\n" + old_log)
            
    @render.text
    def category_stats_output(): return processor.check_errors(comparison_data.get(), last_analysis_inputs.get())

    @render.text
    def generation_console_output(): return gen_log.get()

    @render.ui
    def interactive_folder_status():
        paths = detected_paths.get()
        if not paths: return ui.p("Složka nebyla vybrána.", style="font-style:italic; color:#999; padding-left:5px; margin-top: -25px; padding-top: 0px;")
        labels = {"antropometrie": ("Antropometrie", "*.xls*"), "wingate": ("Wingate", "*.txt"), "spiro": ("Spirometrie", "*.xls*"), "srovnani": ("Srovnání 1", "*.txt"), "srovnani2": ("Srovnání 2", "*.txt")}
        rows = []
        for key, (label, pattern) in labels.items():
            path = paths.get(key); exists = path is not None and os.path.exists(path); count_str = ""
            if exists:
                if key == "antropometrie":
                    try:
                        xl_f = list(Path(path).glob("*.xls*"))
                        if xl_f:
                            # Načtení do paměti pro okamžité uvolnění souboru
                            import io
                            with open(xl_f[0], "rb") as f:
                                file_data = io.BytesIO(f.read())
                            tmp = pd.read_excel(file_data, sheet_name="Data_Sheet")
                            u_ids = tmp['ID'].nunique()
                            sj_count = tmp['SJ'].notna().sum() if 'SJ' in tmp.columns else 0
                            count_str = f"({u_ids} unikátních ID, {sj_count}x SJ)" if sj_count > 0 else f"({u_ids} unikátních ID)"
                    except: count_str = "(Chyba)"
                else: count_str = f"({len(processor.get_file_stems(path, pattern))} záznamů)"
            rows.append(ui.div(
                ui.div(ui.span(f"{'✅' if exists else '❌'} {label}", class_="folder-label"), ui.span(count_str, class_="record-count")),
                ui.div(
                    ui.input_action_link(f"open_{key}", "Otevřít", class_="action-link") if exists else None, 
                    ui.input_action_link(f"change_{key}", "Změnit", class_="action-link"), 
                    ui.input_action_link(f"remove_{key}", "×", class_="action-link remove-link") if exists else None
                ), 
                class_="folder-row"
            ))
        return ui.div(*rows, class_="folder-link-container")


    @render.ui
    def selection_actions_ui():
        id_val = selected_id.get(); df = comparison_data.get()
        if not id_val or df is None: return None
        
        row = df[df["ID"] == id_val]
        if row.empty:
            # OPRAVA: Resetování ID děláme izolovaně, aby nevznikla reaktivní smyčka
            with reactive.isolate():
                selected_id.set(None)
            return None
            
        report_status = row["Report"].values[0] 
        
        # Detekce dostupnosti dat pro každou sekci
        ha = row["Antropometrie"].values[0] == "✅"  # Přidána detekce pro Antropo
        hw = row["Wingate"].values[0] == "✅"
        hs = row["Spirometrie"].values[0] == "✅"
        h1 = row["Srovnání 1"].values[0] == "✅"
        h2 = row["Srovnání 2"].values[0] == "✅"
        
        is_failed = "FAILED" in report_status
        btn_style = "font-size: 0.82rem; padding: 3px 10px;"
        
        return ui.div(
            ui.div(
                ui.input_action_link("close_actions", "×", class_="close-btn"),
                ui.div(ui.strong(f"👤 {id_val}:"), 
                    ui.input_action_link("copy_id", "📋 Kopírovat ID", class_="action-link", style="margin-left:10px;")),
                ui.div(
                    # Nyní jsou všechna tlačítka podmíněná
                    ui.input_action_button("go_antro", "Antropometrie", class_="btn-sm btn-outline-primary", style=btn_style) if ha else None,
                    ui.input_action_button("go_win", "Wingate", class_="btn-sm btn-outline-primary", style=btn_style) if hw else None,
                    ui.input_action_button("go_srov1", "Srovnání 1", class_="btn-sm btn-outline-primary", style=btn_style) if h1 else None,
                    ui.input_action_button("go_srov2", "Srovnání 2", class_="btn-sm btn-outline-primary", style=btn_style) if h2 else None,
                    ui.input_action_button("go_spiro", "Spirometrie", class_="btn-sm btn-outline-primary", style=btn_style) if hs else None,
                    
                    ui.input_action_button(
                        "go_single_report", 
                        "📄 Generovat report & Excel", 
                        class_="btn-sm btn-success" if not is_failed else "btn-sm btn-secondary", 
                        style="margin-left: auto; font-size: 0.82rem; padding: 3px 12px;",
                        disabled=is_failed
                    ),
                    style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 5px; align-items: center;"
                ), class_="selection-card"
            ),
            class_="animate-appearance"
        )

    @reactive.effect
    @reactive.event(input.copy_id)
    async def _copy_id():
        await session.send_custom_message('copy_text', str(selected_id.get()))
        ui.notification_show(f"ID {selected_id.get()} zkopírováno", duration=2)

    @reactive.effect
    @reactive.event(input.close_actions)
    def _close_panel(): selected_id.set(None)

    @reactive.effect    
    @reactive.event(input.go_antro)
    def _go_a(): open_excel_directly(detected_paths.get().get("antropometrie"))
    @reactive.effect
    @reactive.event(input.go_win)
    def _go_w(): show_in_explorer(detected_paths.get().get("wingate"), selected_id.get(), "wingate")
    @reactive.effect
    @reactive.event(input.go_spiro)
    def _go_s(): show_in_explorer(detected_paths.get().get("spiro"), selected_id.get(), "spiro")
    @reactive.effect
    @reactive.event(input.go_srov1)
    def _go_s1(): show_in_explorer(detected_paths.get().get("srovnani"), selected_id.get(), "wingate")
    @reactive.effect
    @reactive.event(input.go_srov2)
    def _go_s2(): show_in_explorer(detected_paths.get().get("srovnani2"), selected_id.get(), "wingate")

    @reactive.effect
    @reactive.event(input.select_folder)
    def _sel():
        active_window = webview.active_window()
        if active_window:
            # Změna z webview.FOLDER_DIALOG na webview.FileDialog.FOLDER
            res = active_window.create_file_dialog(webview.FileDialog.FOLDER)
            if res and len(res) > 0:
                main_folder_path.set(res[0])

    @render.data_frame
    def data_preview():
        df = comparison_data.get()
        if df is None: return render.DataGrid(pd.DataFrame(columns=["ID", "Wingate", "Spirometrie", "Report"]))
        return render.DataGrid(df, width="100%", selection_mode="row")

    def setup_folder_actions(key):
        @reactive.effect
        @reactive.event(input[f"open_{key}"])
        def _open():
            p = detected_paths.get().get(key)
            if key == "antropometrie": open_excel_directly(p)
            else: os.startfile(p)

        @reactive.effect
        @reactive.event(input[f"change_{key}"])
        def _change():
            # Nahrazení TK dialogu za pywebview dialog
            if webview.windows:
                res = webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER)
                if res and len(res) > 0:
                    nd = res[0]
                    curr = detected_paths.get().copy(); curr[key] = nd
                    detected_paths.set(curr); trigger_analysis()

        @reactive.effect
        @reactive.event(input[f"remove_{key}"])
        def _remove():
            curr = detected_paths.get().copy(); curr[key] = None
            detected_paths.set(curr); trigger_analysis()

    for k in ["antropometrie", "wingate", "spiro", "srovnani", "srovnani2"]: setup_folder_actions(k)

    @reactive.effect
    def _handle_selection():
        ix = input.data_preview_selected_rows()
        df = comparison_data.get()
        # KLÍČOVÁ OCHRANA: Pokud index ix[0] neexistuje v novém df (po přejmenování), nic nedělej
        if df is not None and not df.empty and ix and ix[0] < len(df):
            try:
                selected_id.set(df.iloc[ix[0]]["ID"])
            except:
                selected_id.set(None)
        else:
            selected_id.set(None)
            
app = App(app_ui, server, static_assets=get_resource_path("."))

def find_free_port(start_port=8080):
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                # Zkusíme se na port "přilepit"
                s.bind(("127.0.0.1", port))
                return port
            except socket.error:
                # Pokud je obsazen, zkusíme o 1 vyšší
                port += 1

def run_shiny(port): 
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")

if __name__ == "__main__":
    import multiprocessing
    import threading
    
    try:
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError:
        pass
        
    multiprocessing.freeze_support()
    
    # --- DYNAMICKÉ HLEDÁNÍ PORTU ---
    selected_port = find_free_port(8080)
    print(f"[INFO] Startuji server na portu: {selected_port}")
    
    # Předáme port do vlákna serveru
    threading.Thread(target=run_shiny, args=(selected_port,), daemon=True).start()
    
    # Použijeme f-string pro dynamickou URL adresu okna
    window = webview.create_window(
        "Performance Analyzer", 
        url=f"http://127.0.0.1:{selected_port}", 
        width=1280, 
        height=920
    )
    
    webview.start(icon=get_resource_path("logo.ico"))