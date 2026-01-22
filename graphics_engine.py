
import os
os.environ["GIO_USE_VFS"] = "local"
os.environ["G_MESSAGES_DEBUG"] = ""
import matplotlib# Přepnutí na neinteraktivní backend musí být ÚPLNĚ PRVNÍ
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.nonparametric.smoothers_lowess import lowess 
from matplotlib.ticker import FuncFormatter
import textwrap

# Nastavení stylu
plt.style.use('seaborn-v0_8-whitegrid')

def create_wingate_plot(history_data, output_path):
    # Dynamický výpočet výšky dle počtu srovnávaných testů
    num_rows = len(history_data)
    dynamic_height = 8.5 - (num_rows - 1)
    
    fig, ax = plt.subplots(figsize=(25, dynamic_height)) 
    
    colors = {"Aktuální": "black", "Srovnání 1": "orange", "Srovnání 2": "darkmagenta"}
    
    for test in history_data:
        label = test["Label"]
        df = test["df"]
        p_col = test["p_col"]
        color = colors.get(label, "grey")
        date_str = test.get("Date", label)
        
        # Očištění dat od chybějících hodnot
        df_clean = df.dropna(subset=['sec', p_col])
        
        # --- NOVÉ: LOESS Vyhlazení pro Wingate ---
        # frac=0.1 je ideální pro 30s test, aby zůstal zachován Peak Power
        smoothed = lowess(df_clean[p_col], df_clean['sec'], frac=0.07)
        x_new = smoothed[:, 0]
        y_smooth = smoothed[:, 1]

        if label == "Aktuální":
            ax.plot(df['sec'], df[p_col], color='grey', alpha=0.2, linestyle='--', label='hrubá data')
            ax.axhline(df[p_col].mean(), color='blue', linestyle='--', alpha=0.4, linewidth=2, label='průměr')
            ax.plot(x_new, y_smooth, color='black', linewidth=4, label=f"vyhlazená data, {date_str}")
        else:
            ax.plot(x_new, y_smooth, color=color, linewidth=2.5, label=date_str)

    # Styling os a nadpisů
    ax.set_title("Anaerobní Wingate test - 30 s", fontsize=20, fontweight='bold', pad=20, loc='left', x=-0.07)
    ax.set_xlabel("Čas (s)", fontsize=24, fontweight='bold')
    ax.set_ylabel("Výkon (W)", fontsize=24, fontweight='bold')
    
    ax.spines['bottom'].set_linewidth(3)
    ax.spines['left'].set_linewidth(3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    ax.tick_params(axis='both', which='both', labelsize=18, width=2, length=6, colors='black')
    ax.grid(True, linestyle=':', alpha=0.5, linewidth=1.0)
    ax.set_xlim(0, 31)
    ax.set_xticks(range(0, 35, 5))

    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), fontsize=20, frameon=True, borderpad=1)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', pad_inches=0.05)
    plt.close()

def format_time_axis(x, pos):
    """Formátuje sekundy na MM:SS"""
    m = int(x // 60)
    s = int(x % 60)
    return f"{m:02d}:{s:02d}"


def create_spiro_plot(spiro_df, output_path):
    # Zvětšená figura pro velké fonty a legendy vpravo
    fig, (ax1, ax3) = plt.subplots(1, 2, figsize=(31, 8)) 
    
    time_x = spiro_df["rel_time"]
    
    # --- GRAF 1: VENTILACE A TEPOVÁ FREKVENCE ---
    ax2 = ax1.twinx()
    
    # Hrubá data ventilace (šedá čárkovaná)
    ax1.plot(time_x, spiro_df["VE"], color='black', alpha=0.15, linestyle='--', linewidth=1)
    
    # Vyhlazená Ventilace (LOESS)
    smooth_ve = lowess(spiro_df["VE"], time_x, frac=0.1)
    line1, = ax1.plot(smooth_ve[:, 0], smooth_ve[:, 1], color='black', linewidth=4, label="Ventilace")
    
    # Tepová frekvence (Oranžová)
    line2, = ax2.plot(time_x, spiro_df["TF"], color='orange', linewidth=4, label="TF")
    
    # --- GRAF 2: SPOTŘEBA KYSLÍKU ---
    # Hrubá data VO2
    ax3.plot(time_x, spiro_df["VO2"], color='darkmagenta', alpha=0.15, linestyle='--', linewidth=1)
    
    # Vyhlazené VO2 (LOESS)
    smooth_vo2 = lowess(spiro_df["VO2"], time_x, frac=0.1)
    line3, = ax3.plot(smooth_vo2[:, 0], smooth_vo2[:, 1], color='darkmagenta', linewidth=4, label="V'O2")

    # --- SJEDNOCENÝ STYLING DLE WINGATE ---
    # 1. Popisky a názvy
    ax1.set_title(" ", fontsize=20, fontweight='bold', loc='left', pad=20)
    ax1.set_ylabel("Minutová ventilace (l/min)", fontsize=28, fontweight='bold', labelpad=15)
    ax2.set_ylabel("Tepová frekvence (BPM)", fontsize=28, fontweight='bold', color='orange', labelpad=15)
    
    ax3.set_title(" ", fontsize=20, fontweight='bold', loc='left', pad=20)
    ax3.set_ylabel("Spotřeba O2 (l)", fontsize=28, fontweight='bold', labelpad=15)

    # 2. Nastavení os (Tloušťka a Ticks)
    for ax_item in [ax1, ax2, ax3]:
        ax_item.xaxis.set_major_formatter(FuncFormatter(format_time_axis))
        ax_item.set_xlabel("Čas (min:sek)", fontsize=28, fontweight='bold')
        
        # Tloušťka os (linewidth=3)
        ax_item.spines['bottom'].set_linewidth(3)
        ax_item.spines['left'].set_linewidth(3)
        if ax_item == ax2:
            ax_item.spines['right'].set_linewidth(3) # I pravá osa u TF bude tlustá
        
        ax_item.spines['top'].set_visible(False)
        if ax_item != ax2:
            ax_item.spines['right'].set_visible(False)
            
        # Tick parametry (labelsize=18)
        ax_item.tick_params(axis='both', which='both', labelsize=22, width=3, length=10, colors='black')
        if ax_item in [ax1, ax2]:
            ax_item.grid(False)
        else:
            ax_item.grid(True, linestyle=':', alpha=0.5, linewidth=1.0)

    # 3. Legendy (fontsize=20, vpravo)
    # Sdružená legenda pro první graf
    lines12 = [line1, line2]
    labels12 = [l.get_label() for l in lines12]
   

    # Úprava layoutu pro velké legendy
    plt.tight_layout(w_pad=0.5) 
    fig.subplots_adjust(wspace=0.3) # Toto natvrdo určí šířku mezery mezi ax1 a ax3
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight', pad_inches=0.05)
    plt.close()


def create_radar_plot(radar_data, output_path):
    labels = radar_data['labels']
    values = list(radar_data['values']) 
    num_vars = len(labels)

    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    values.append(values[0])
    angles.append(angles[0])

    fig, ax = plt.subplots(figsize=(14, 14), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)

    # 1. ROZSAH OSY A MŘÍŽKA
    ax.set_ylim(0, 120) 
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels(["25%", "50%", "75%", "100%"], color="grey", size=14)

    # Vykreslení pavouka
    ax.fill(angles, values, color='#2c7c7c', alpha=0.05, zorder=1)
    ax.plot(angles, values, color='#2c7c7c', linewidth=4, zorder=2)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([]) 

    # 2. POPISKY OS (NÁZVY PARAMETRŮ)
    # Odstranění symbolů % a závorek (podle požadavku na duplicitu)
    for i, label in enumerate(labels):
        angle_rad = angles[i]
        ha = 'center' if abs(np.sin(angle_rad)) < 0.1 else ('left' if np.sin(angle_rad) > 0 else 'right')
        va = 'bottom' if abs(np.cos(angle_rad)) > 0.9 and np.cos(angle_rad) > 0 else ('top' if np.cos(angle_rad) < 0 else 'center')
        
        # Čištění: odstraní " (%)" i samostatné " %"
        clean_label = label.replace(" (%)", "").replace(" %", "")
        ax.text(angle_rad, 155, clean_label, size=24, fontweight='normal', 
                ha=ha, va=va, linespacing=1.2)

    # 3. ČÍSELNÉ HODNOTY (DYNAMICKÁ PROCENTA)
    for i in range(num_vars):
        val = values[i]
        angle_rad = angles[i]
        # Barevná logika z obrázku: >= 100 zelená, < 90 červená, zbytek oranžová
        color = "green" if val >= 100 else ("orange" if val >= 90 else "red")
        
        if val >= 100:
            text_radius = val - 20  # Hluboko dovnitř (prostor v pavoukovi)
        else:
            text_radius = val + 15  # Vně bodu (prostor u mřížky)
            
        ax.text(angle_rad, text_radius, f"{val}%", color=color, 
                ha='center', va='center', fontsize=26, fontweight='black', zorder=10)

    # 4. TEXTY Z OBRÁZKU (NADPIS A PODTITUL)
    plt.title("Rozložení parametrů", size=36, fontweight='bold', y=1.45, pad=20)
    
    # Přesný text z image_887f64.png
    subtitle_text = (
        "Síťový graf ukazuje přehled o klíčových výkonnostních parametrech pro interindividuální srovnávání (mezi hráči)."
        "Vzdálenost bodů od středu značí úroveň dosaženého výkonu v procentech náležité hodnoty pro danou kategorii, což umožňuje identifikovat,"
        "ve kterých oblastech hráč vykazuje silné stránky a kde je naopak prostor pro zlepšení."
    )
    
    wrapped_subtitle = "\n".join(textwrap.wrap(subtitle_text, width=85))
    plt.text(0.5, 1.28, wrapped_subtitle, transform=ax.transAxes, 
             ha='center', fontsize=24, style='normal', color='#444')

    # Finální doladění plochy pro PDF
    plt.subplots_adjust(top=0.82, bottom=0.02, left=0.05, right=0.95) 
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()