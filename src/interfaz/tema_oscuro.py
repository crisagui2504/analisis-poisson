"""
Tema oscuro moderno para los widgets ttk (combos, sliders, progreso, checks).
Se llama automaticamente desde app_gui.py; no necesitas ejecutarlo tu.

La paleta vive en app_gui.py (PALETA); aqui la importamos para no duplicar.
"""
import tkinter.ttk as ttk

from paleta import (
    BG, PANEL, CARD, CARD2, BORDE, TEXTO, TEXTO_SEC, ACENTO, ACENTO_HOVER,
)


def aplicar_tema(root):
    """Configura el estilo oscuro de todos los widgets ttk (combos, sliders,
    barras de progreso, checks, pestanas) acorde a la paleta. Se llama una vez
    al crear la ventana."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # Desplegables (Combobox)
    style.configure(
        "Moderno.TCombobox",
        fieldbackground=CARD2, background=CARD2, foreground=TEXTO,
        selectbackground=ACENTO, selectforeground="#ffffff",
        bordercolor=BORDE, lightcolor=BORDE, darkcolor=BORDE,
        arrowcolor=TEXTO_SEC, arrowsize=14, padding=8, relief="flat",
    )
    style.map(
        "Moderno.TCombobox",
        fieldbackground=[("readonly", CARD2), ("focus", CARD2)],
        foreground=[("readonly", TEXTO)],
        bordercolor=[("focus", ACENTO), ("active", ACENTO)],
        arrowcolor=[("active", TEXTO)],
    )
    # Lista desplegada del combobox
    root.option_add("*TCombobox*Listbox.background", CARD2)
    root.option_add("*TCombobox*Listbox.foreground", TEXTO)
    root.option_add("*TCombobox*Listbox.selectBackground", ACENTO)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.borderWidth", 0)
    root.option_add("*TCombobox*Listbox.font", "{Segoe UI} 10")

    # Sliders (Scale)
    style.configure(
        "Moderno.Horizontal.TScale",
        background=PANEL, troughcolor=BORDE, bordercolor=PANEL,
        lightcolor=ACENTO, darkcolor=ACENTO, sliderrelief="flat",
    )

    # Barra de progreso
    style.configure(
        "Moderno.Horizontal.TProgressbar",
        troughcolor=BORDE, background=ACENTO, bordercolor=PANEL,
        lightcolor=ACENTO, darkcolor=ACENTO, thickness=6,
    )

    # Pestañas (Notebook)
    style.configure("Moderno.TNotebook", background=CARD, borderwidth=0)
    style.configure("Moderno.TNotebook.Tab", background=CARD, foreground=TEXTO_SEC,
                    padding=(16, 8), borderwidth=0, font="{Segoe UI} 10 bold")
    style.map("Moderno.TNotebook.Tab",
              background=[("selected", CARD2)],
              foreground=[("selected", TEXTO)])

    # Checkbutton
    style.configure(
        "Moderno.TCheckbutton",
        background=PANEL, foreground=TEXTO_SEC, focuscolor=PANEL,
        indicatorcolor=CARD2, indicatorrelief="flat",
    )
    style.map(
        "Moderno.TCheckbutton",
        background=[("active", PANEL)],
        foreground=[("active", TEXTO)],
        indicatorcolor=[("selected", ACENTO), ("active", BORDE)],
    )
