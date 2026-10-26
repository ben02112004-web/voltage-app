import os
import datetime
import flet as ft
import pandas as pd

UNIV = "University of Setif 1 – Ferhat Abbas"
FAC = "Faculty of Technology"
PRIMARY = "#0B4F6C"
ACCENT = "#1B6CA8"


# ---------------------------------------------------------------- logique
def load_voltages(path):
    """Lit un CSV et retourne (liste_bus, liste_tensions)."""
    with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
        head = f.read(2048)
    sep = ";" if head.count(";") > head.count(",") else ("\t" if "\t" in head else ",")
    df = pd.read_csv(path, sep=sep, encoding="utf-8-sig", dtype=str)

    # fichier sans en-tête (la 1ère ligne est déjà numérique)
    def is_num(s):
        try:
            float(str(s).strip().replace(",", "."))
            return True
        except ValueError:
            return False

    if all(is_num(c) for c in df.columns):
        df = pd.read_csv(path, sep=sep, encoding="utf-8-sig", header=None, dtype=str)
        df.columns = [f"col{i}" for i in range(len(df.columns))]

    df.columns = [str(c).strip().lower() for c in df.columns]
    # conversion numérique (virgule décimale acceptée)
    num = df.apply(lambda s: pd.to_numeric(
        s.astype(str).str.strip().str.replace(",", ".", regex=False), errors="coerce"))
    num = num.dropna(axis=1, how="all")
    if num.empty:
        raise ValueError("Aucune colonne numérique trouvée")

    bus_words = ("bus", "noeud", "nœud", "node", "n°", "num", "id", "index")
    bus_col = next((c for c in num.columns if any(w in c for w in bus_words)), None)

    volt_words = ("tension", "voltage", "volt", "pu", "p.u", "vm", "u")
    candidates = [c for c in num.columns if c != bus_col]
    col = next((c for c in candidates if any(w in c for w in volt_words[:-1])), None)
    if col is None and candidates:
        col = candidates[-1]
    if col is None:          # un seul colonne numérique
        col = bus_col

    volts = num[col].dropna().astype(float).tolist()
    if bus_col is not None and bus_col != col:
        buses = num.loc[num[col].notna(), bus_col].fillna(0).astype(int).tolist()
    else:
        buses = list(range(1, len(volts) + 1))
    return buses, volts


def compute_stats(v):
    return {
        "Somme": sum(v),
        "Moyenne": sum(v) / len(v),
        "Maximum": max(v),
        "Minimum": min(v),
    }


def export_pdf(buses, volts, stats, out_dir):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, Image)

    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = os.path.join(out_dir, f"rapport_tension_{stamp}.pdf")
    styles = getSampleStyleSheet()
    story = [
        Paragraph(UNIV, styles["Title"]),
        Paragraph(FAC, styles["Heading3"]),
        Spacer(1, 12),
        Paragraph("Rapport – Profil de tension du réseau", styles["Heading2"]),
        Paragraph(datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), styles["Normal"]),
        Spacer(1, 12),
    ]

    # graphique (matplotlib) – ignoré si indisponible
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        png = os.path.join(out_dir, f"profil_{stamp}.png")
        plt.figure(figsize=(7, 3.5))
        plt.plot(buses, volts, "o-", color=ACCENT, markersize=3, label="Tension (p.u.)")
        plt.xlabel("Bus")
        plt.ylabel("Tension (p.u.)")
        plt.title("Profil de tension du réseau")
        plt.grid(alpha=.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(png, dpi=150)
        plt.close()
        story += [Image(png, width=450, height=225), Spacer(1, 12)]
    except Exception:
        pass

    data = [["Indicateur", "Valeur (p.u.)"]] + \
           [[k, f"{val:.3f}"] for k, val in stats.items()]
    t = Table(data, colWidths=[200, 150])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .5, colors.grey),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
    ]))
    story += [Paragraph("Résultats des tensions", styles["Heading3"]), t,
              Spacer(1, 12)]

    rows = [["Bus", "Tension (p.u.)"]] + [[b, f"{v:.4f}"] for b, v in zip(buses, volts)]
    t2 = Table(rows, repeatRows=1)
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), .25, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story += [Paragraph("Données importées", styles["Heading3"]), t2]
    SimpleDocTemplate(pdf_path, pagesize=A4).build(story)
    return pdf_path


def pdf_dir():
    for d in ("/storage/emulated/0/Download",
              os.getenv("FLET_APP_STORAGE_DATA", ""),
              os.path.expanduser("~/Documents"),
              os.getcwd()):
        if d and os.path.isdir(d) and os.access(d, os.W_OK):
            return d
    return os.getcwd()


# ---------------------------------------------------------------- interface
def main(page: ft.Page):
    page.title = "Profil de tension"
    page.padding = 0
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#EEF3F8"
    page.scroll = ft.ScrollMode.AUTO

    state = {"buses": [], "volts": []}

    file_label = ft.Text("Aucun fichier sélectionné", size=12, color="#555555",
                         expand=True, overflow=ft.TextOverflow.ELLIPSIS)
    chart_box = ft.Container(height=260, alignment=ft.alignment.center,
                             content=ft.Text("Aucune donnée", color="#888888"))

    def stat_card(title, icon, color):
        val = ft.Text("—", size=18, weight=ft.FontWeight.BOLD)
        card = ft.Container(
            expand=True, padding=8, bgcolor="white", border_radius=12,
            border=ft.border.all(1, "#E0E6ED"),
            content=ft.Column([
                ft.Icon(icon, color=color, size=22),
                ft.Text(title, size=11, weight=ft.FontWeight.W_600),
                val,
                ft.Text("p.u.", size=10, color="#777777"),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2))
        return card, val

    c_sum, v_sum = stat_card("Somme", ft.Icons.FUNCTIONS, "#1B6CA8")
    c_avg, v_avg = stat_card("Moyenne", ft.Icons.SHOW_CHART, "#1E7F5C")
    c_max, v_max = stat_card("Maximum", ft.Icons.ARROW_UPWARD, "#D64545")
    c_min, v_min = stat_card("Minimum", ft.Icons.ARROW_DOWNWARD, "#E0A21B")
    stat_vals = {"Somme": v_sum, "Moyenne": v_avg, "Maximum": v_max, "Minimum": v_min}

    def snack(msg):
        page.open(ft.SnackBar(ft.Text(msg)))

    def draw_chart():
        pts = [ft.LineChartDataPoint(b, v) for b, v in zip(state["buses"], state["volts"])]
        lo = min(state["volts"])
        hi = max(state["volts"])
        chart = ft.LineChart(
            data_series=[ft.LineChartData(
                data_points=pts, stroke_width=2, color=ACCENT, curved=False,
                point=True)],
            min_y=round(lo - 0.02, 2), max_y=round(hi + 0.02, 2),
            min_x=state["buses"][0], max_x=state["buses"][-1],
            border=ft.border.all(1, "#CCCCCC"),
            horizontal_grid_lines=ft.ChartGridLines(color="#E5E5E5", width=1),
            left_axis=ft.ChartAxis(labels_size=40, title=ft.Text("Tension (p.u.)", size=10)),
            bottom_axis=ft.ChartAxis(labels_size=24, labels_interval=4,
                                     title=ft.Text("Bus", size=10)),
            expand=True)
        chart_box.content = chart

    def on_file(e: ft.FilePickerResultEvent):
        if not e.files:
            return
        f = e.files[0]
        try:
            buses, volts = load_voltages(f.path)
            if not volts:
                raise ValueError("Fichier vide")
            state["buses"], state["volts"] = buses, volts
            file_label.value = f.name
            draw_chart()
            for k, v in compute_stats(volts).items():
                stat_vals[k].value = f"{v:.3f}"
            snack(f"{len(volts)} valeurs importées")
        except Exception as ex:
            snack(f"Erreur : {ex}")
        page.update()

    picker = ft.FilePicker(on_result=on_file)
    page.overlay.append(picker)

    def on_export(e):
        if not state["volts"]:
            snack("Importez d'abord un fichier CSV")
            return
        try:
            path = export_pdf(state["buses"], state["volts"],
                              compute_stats(state["volts"]), pdf_dir())
            snack(f"PDF enregistré : {path}")
        except Exception as ex:
            snack(f"Erreur PDF : {ex}")

    def on_reset(e):
        state["buses"], state["volts"] = [], []
        file_label.value = "Aucun fichier sélectionné"
        chart_box.content = ft.Text("Aucune donnée", color="#888888")
        for v in stat_vals.values():
            v.value = "—"
        page.update()

    header = ft.Container(
        padding=ft.padding.only(left=16, right=16, top=36, bottom=18),
        bgcolor=PRIMARY, border_radius=ft.border_radius.only(bottom_left=24, bottom_right=24),
        content=ft.Row([
            ft.Icon(ft.Icons.ACCOUNT_BALANCE, color="white", size=40),
            ft.Column([
                ft.Text("University of Setif 1", size=17, weight=ft.FontWeight.BOLD, color="white"),
                ft.Text("Ferhat Abbas", size=14, color="white"),
                ft.Text(FAC, size=12, color="#B9D3E3"),
            ], spacing=0, expand=True),
            ft.Icon(ft.Icons.SCHOOL, color="white"),
        ], spacing=12))

    def card(content):
        return ft.Container(content=content, padding=12, bgcolor="white", border_radius=14,
                            margin=ft.margin.symmetric(horizontal=12, vertical=6))

    import_card = card(ft.Column([
        ft.Row([ft.Icon(ft.Icons.FOLDER_OPEN, color=PRIMARY),
                ft.Text("Importer un fichier CSV", weight=ft.FontWeight.BOLD)]),
        ft.Text("Sélectionnez le fichier contenant les données de tension.",
                size=11, color="#666666"),
        ft.Row([
            ft.Container(ft.Row([ft.Icon(ft.Icons.DESCRIPTION, size=16), file_label]),
                         expand=True, padding=8, bgcolor="#F2F5F8", border_radius=8),
            ft.ElevatedButton("Choisir un fichier", bgcolor=PRIMARY, color="white",
                              icon=ft.Icons.FOLDER,
                              on_click=lambda _: picker.pick_files(
                                  allowed_extensions=["csv"], dialog_title="CSV")),
        ]),
    ]))

    chart_card = card(ft.Column([
        ft.Row([ft.Icon(ft.Icons.BAR_CHART, color=PRIMARY),
                ft.Text("Profil de tension – IEEE 33 Bus", weight=ft.FontWeight.BOLD)]),
        chart_box,
    ]))

    results_card = card(ft.Column([
        ft.Row([ft.Icon(ft.Icons.BAR_CHART, color=PRIMARY),
                ft.Text("Résultats des tensions", weight=ft.FontWeight.BOLD)]),
        ft.Row([c_sum, c_avg], spacing=8),
        ft.Row([c_max, c_min], spacing=8),
        ft.Row([
            ft.ElevatedButton("Exporter les résultats (PDF)", icon=ft.Icons.PICTURE_AS_PDF,
                              bgcolor="#0F6B5B", color="white", expand=True, on_click=on_export),
        ]),
        ft.Row([
            ft.OutlinedButton("Réinitialiser", icon=ft.Icons.REFRESH, expand=True, on_click=on_reset),
        ]),
    ]))

    page.add(header, import_card, chart_card, results_card)


ft.app(target=main)



