import os
import sys
import warnings
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

# Potlačení systémových varování a hlášení WeasyPrintu pro čistší konzoli
os.environ["GIO_USE_VFS"] = "local"
os.environ["G_MESSAGES_DEBUG"] = ""
warnings.filterwarnings("ignore", category=UserWarning)

def get_resource_path(relative_path):
    """ Získá cestu k souborům pro skript i pro zabalené .exe """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller rozbaluje soubory do dočasné složky _MEIPASS
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# Poté upravte definici složky šablon:
script_dir = Path(get_resource_path("."))
templates_dir = script_dir / 'templates'

def generate_pdf_report(data, output_folder):
    """
    Vezme zpracovaná data sportovce a vygeneruje PDF report.
    Optimalizováno pro bezproblémový běh v zabaleném .exe souboru.
    """
    
    # 1. Nastavení cest pro robustnost na Windows
    # V zabaleném .exe ukazuje script_dir do dočasné složky _MEIPASS (kde je logo.png)
    script_dir = Path(__file__).parent.absolute()
    
    # Cesta ke složce se šablonami (musí být přibalena přes PyInstaller)
    templates_dir = script_dir / 'templates'
    
    # 2. Nastavení prostředí šablon Jinja2
    if not templates_dir.exists():
        # Pokud šablona není v podsložce (např. při vývoji), zkusí kořen
        env = Environment(loader=FileSystemLoader(str(script_dir)))
    else:
        env = Environment(loader=FileSystemLoader(str(templates_dir)))
        
    try:
        template = env.get_template('report_template.html')
    except Exception:
        # Záložní plán pro případ, že šablona leží přímo u skriptu
        env = Environment(loader=FileSystemLoader(str(script_dir)))
        template = env.get_template('report_template.html')

    # 3. Příprava dat a výstupní cesty
    # Zajištění, že ID neobsahuje znaky zakázané v názvu souboru Windows
    safe_id = str(data['athlete']['ID']).replace("/", "_").replace("\\", "_")
    report_name = f"{safe_id}.pdf"
    output_path = Path(output_folder) / report_name
    
    # 4. Renderování HTML šablony
    html_out = template.render(
        athlete=data['athlete'],
        wingate=data['wingate'],
        spiro=data['spiro'],
        history=data['history'],
        plots=data['plots'],  # Cesty ke grafům musí být absolutní z master_engine.py
        sport=data['sport'],
        team=data['team'],
        report_type=data['report_type'],
        logo_base64=data.get('logo_base64', ''),
        current_year=datetime.now().year,
    )
    
    # 5. Export do PDF s WeasyPrint
    # base_url je kritický: v EXE režimu ukazuje do _MEIPASS složky, 
    # což umožní najít 'logo.png', které je přibaleno uvnitř programu.
    # Použití .as_uri() převede cestu na file:///C:/... (nutné pro Windows)
    base_url = script_dir.as_uri()
    
    try:
        # presentational_hints=True zajišťuje, že se obrázky v HTML správně roztáhnou
        html_doc = HTML(string=html_out, base_url=base_url)
        html_doc.write_pdf(
            str(output_path), 
            presentational_hints=True
        )
    except Exception as e:
        print(f"Chyba při zápisu PDF: {e}")
        raise e
    
    return output_path