"""
Interfaz gráfica del predictor de fútbol — estilo moderno.
Ejecutar: py -3.11 app_gui.py
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading

import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from ligas_config import (
    LIGAS, TEMPORADAS, EQUIPOS_MUNDIAL_ES, NOMBRE_DISPLAY, EQUIPOS_MUNDIAL
)
from predecir_partido import predecir_partido, cargar_equipos
import proveedores
from tema_oscuro import aplicar_tema
from paleta import (
    BG, PANEL, CARD, CARD2, BORDE, TEXTO, TEXTO_SEC,
    ACENTO, ACENTO_HOVER, CIAN, GRAD1, GRAD2, VERDE, AMARILLO, ROJO, FUENTE,
)


# ── Utilidades de dibujo ─────────────────────────────────────────────────────

def _mezcla(c1, c2, t):
    """Interpola dos colores hex (#rrggbb). t en [0, 1]."""
    a = tuple(int(c1[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(c2[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(a[k] + (b[k] - a[k]) * t) for k in range(3))


def _clamp01(x):
    return max(0.0, min(1.0, x))


def _cuota(p):
    return f"Cuota {1 / p:.2f}" if p and p > 0 else "—"


def _rect_redondo(cv, x1, y1, x2, y2, r, **kw):
    """Dibuja un rectángulo de esquinas redondeadas en un Canvas."""
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return cv.create_polygon(pts, smooth=True, **kw)


class Cabecera(tk.Canvas):
    """Banner superior con degradado y título."""

    def __init__(self, parent):
        super().__init__(parent, height=78, bg=BG, highlightthickness=0, bd=0)
        self.bind("<Configure>", self._dibujar)

    def _dibujar(self, _=None):
        self.delete("all")
        w = max(self.winfo_width(), 1)
        h = self.winfo_height()
        # Degradado horizontal
        pasos = max(w, 1)
        for x in range(pasos):
            self.create_line(x, 0, x, h, fill=_mezcla(GRAD1, GRAD2, x / pasos))
        # Capa oscura redondeada para dar profundidad al texto
        self.create_text(28, h / 2 - 9, anchor="w", text="⚽  Predictor de Fútbol",
                         fill="#ffffff", font=(FUENTE, 20, "bold"))
        self.create_text(30, h / 2 + 16, anchor="w",
                         text="Mundial 2026 · modelo Poisson · Dixon-Coles · Elo",
                         fill="#e7e3ff", font=(FUENTE, 10))
        self.create_text(w - 24, h / 2, anchor="e", text="⚡ en vivo",
                         fill="#ffffff", font=(FUENTE, 10, "bold"))


class Tarjeta(tk.Canvas):
    """Tarjeta redondeada con título, valor grande y subtítulo opcional."""

    def __init__(self, parent, titulo, valor, color, sub="", alto=132, bg=CARD):
        super().__init__(parent, height=alto, bg=bg, highlightthickness=0, bd=0)
        self.titulo, self.valor, self.color, self.sub = titulo, valor, color, sub
        self.bind("<Configure>", self._dibujar)

    def actualizar(self, valor=None, sub=None):
        if valor is not None:
            self.valor = valor
        if sub is not None:
            self.sub = sub
        self._dibujar()

    def _dibujar(self, _=None):
        self.delete("all")
        w = max(self.winfo_width(), 2)
        h = self.winfo_height()
        _rect_redondo(self, 3, 3, w - 3, h - 3, 18, fill=CARD2, outline=BORDE)
        # Indicador de acento (pastilla superior)
        cx = w / 2
        _rect_redondo(self, cx - 22, 14, cx + 22, 20, 3, fill=self.color, outline=self.color)
        self.create_text(cx, h * 0.36, text=self.titulo, fill=TEXTO_SEC,
                         font=(FUENTE, 10), width=w - 24, justify="center")
        self.create_text(cx, h * 0.62, text=self.valor, fill=self.color,
                         font=(FUENTE, 27, "bold"))
        if self.sub:
            self.create_text(cx, h * 0.86, text=self.sub, fill=TEXTO_SEC,
                             font=(FUENTE, 9))


class BarraProbabilidad(tk.Canvas):
    """Barra horizontal segmentada que visualiza el reparto 1-X-2."""

    def __init__(self, parent, p1, px, p2):
        super().__init__(parent, height=34, bg=CARD, highlightthickness=0, bd=0)
        self.p1, self.px, self.p2 = p1, px, p2
        self.bind("<Configure>", self._dibujar)

    def _dibujar(self, _=None):
        self.delete("all")
        w = max(self.winfo_width(), 2)
        h = self.winfo_height()
        gap = 4
        total = self.p1 + self.px + self.p2 or 1
        anchos = [self.p1 / total * (w - 2 * gap),
                  self.px / total * (w - 2 * gap),
                  self.p2 / total * (w - 2 * gap)]
        colores = [VERDE, AMARILLO, ROJO]
        valores = [self.p1, self.px, self.p2]
        x = 0
        for ancho, color, val in zip(anchos, colores, valores):
            if ancho <= 1:
                x += ancho + gap
                continue
            _rect_redondo(self, x, 4, x + ancho, h - 4, 8, fill=color, outline=color)
            if ancho > 38:
                self.create_text(x + ancho / 2, h / 2, text=f"{val * 100:.0f}%",
                                 fill="#0b1120", font=(FUENTE, 10, "bold"))
            x += ancho + gap


class PredictorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Predictor de Fútbol · Mundial 2026")
        self.geometry("1180x840")
        self.minsize(1000, 720)
        self.configure(bg=BG)
        aplicar_tema(self)
        self.resizable(True, True)

        self._resultado = None
        self._df_liga_cache = {}
        self._equipos_cache = {}

        self._construir_ui()
        self._on_liga_change()

    # ── Construcción de la UI ──────────────────────────────────────────────

    def _construir_ui(self):
        Cabecera(self).pack(fill="x")

        contenedor = tk.Frame(self, bg=BG)
        contenedor.pack(fill="both", expand=True, padx=20, pady=18)
        contenedor.columnconfigure(0, weight=0)
        contenedor.columnconfigure(1, weight=1)
        contenedor.rowconfigure(0, weight=1)

        self._panel_izq(contenedor)
        self._panel_der(contenedor)

    def _panel_izq(self, parent):
        frame = tk.Frame(parent, bg=PANEL, width=326)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        frame.pack_propagate(False)

        def seccion(titulo, dot=ACENTO, pady=(20, 8)):
            fila = tk.Frame(frame, bg=PANEL)
            fila.pack(fill="x", padx=20, pady=pady)
            tk.Canvas(fila, width=8, height=8, bg=PANEL, highlightthickness=0).pack(
                side="left", pady=2)  # placeholder para alinear
            cv = fila.winfo_children()[-1]
            cv.create_oval(0, 1, 7, 8, fill=dot, outline=dot)
            tk.Label(fila, text=titulo.upper(), font=(FUENTE, 9, "bold"),
                     fg=TEXTO_SEC, bg=PANEL).pack(side="left", padx=8)

        # ── Liga ──
        seccion("Liga", ACENTO, pady=(22, 8))
        self.var_liga = tk.StringVar(value="Mundial 2026")
        cb_liga = ttk.Combobox(frame, textvariable=self.var_liga,
                               values=list(LIGAS.keys()), state="readonly",
                               style="Moderno.TCombobox", font=(FUENTE, 10))
        cb_liga.pack(fill="x", padx=20)
        cb_liga.bind("<<ComboboxSelected>>", lambda e: self._on_liga_change())

        # ── Equipos ──
        seccion("Equipo 1", VERDE)
        self.var_eq1 = tk.StringVar()
        self.cb_eq1 = ttk.Combobox(frame, textvariable=self.var_eq1,
                                   state="readonly", style="Moderno.TCombobox",
                                   font=(FUENTE, 10))
        self.cb_eq1.pack(fill="x", padx=20)

        seccion("Equipo 2", ROJO)
        self.var_eq2 = tk.StringVar()
        self.cb_eq2 = ttk.Combobox(frame, textvariable=self.var_eq2,
                                   state="readonly", style="Moderno.TCombobox",
                                   font=(FUENTE, 10))
        self.cb_eq2.pack(fill="x", padx=20)

        # ── Forma reciente (se llena tras predecir) ──
        self.frame_forma = tk.Frame(frame, bg=PANEL)
        self.frame_forma.pack(fill="x", padx=20, pady=(10, 0))

        # ── Parámetros avanzados ──
        seccion("Ajustes avanzados", CIAN)

        self._slider(frame, "Rho (Dixon-Coles)", -0.3, 0.0, -0.05, "rho", "{:.2f}")
        self._slider(frame, "Shrinkage k", 1, 15, 5, "k", "{:.0f}")

        self.var_cache = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="  Usar caché local (recomendado)",
                        variable=self.var_cache,
                        style="Moderno.TCheckbutton").pack(anchor="w", padx=20, pady=(14, 0))

        self.var_actualizar = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="  Actualizar datos antes de predecir",
                        variable=self.var_actualizar,
                        style="Moderno.TCheckbutton").pack(anchor="w", padx=20, pady=(6, 0))

        # ── Botón principal (CTA) ──
        self.btn_predecir = tk.Button(
            frame, text="⚡  Predecir partido",
            font=(FUENTE, 13, "bold"),
            bg=ACENTO, fg="#ffffff", activebackground=ACENTO_HOVER,
            activeforeground="#ffffff", relief="flat", cursor="hand2",
            bd=0, pady=13, command=self._iniciar_prediccion,
        )
        self.btn_predecir.pack(fill="x", padx=20, pady=(20, 8))
        self.btn_predecir.bind("<Enter>", lambda e: self._hover_btn(True))
        self.btn_predecir.bind("<Leave>", lambda e: self._hover_btn(False))

        self.progreso = ttk.Progressbar(frame, mode="indeterminate",
                                         style="Moderno.Horizontal.TProgressbar")
        self.progreso.pack(fill="x", padx=20, pady=(4, 0))

        self.lbl_estado = tk.Label(frame, text="Listo para predecir.", fg=TEXTO_SEC,
                                   bg=PANEL, font=(FUENTE, 9),
                                   wraplength=280, justify="left")
        self.lbl_estado.pack(padx=20, pady=10, anchor="w")

    def _hover_btn(self, dentro):
        if str(self.btn_predecir["state"]) != "disabled":
            self.btn_predecir.config(bg=ACENTO_HOVER if dentro else ACENTO)

    def _slider(self, frame, etiqueta, desde, hasta, ini, clave, fmt):
        fila = tk.Frame(frame, bg=PANEL)
        fila.pack(fill="x", padx=20, pady=(8, 0))
        tk.Label(fila, text=etiqueta, fg=TEXTO_SEC, bg=PANEL,
                 font=(FUENTE, 9)).pack(side="left")
        var = tk.DoubleVar(value=ini) if clave == "rho" else tk.IntVar(value=ini)
        lbl_val = tk.Label(fila, text=fmt.format(ini), fg=TEXTO, bg=PANEL,
                           font=(FUENTE, 9, "bold"))
        lbl_val.pack(side="right")
        ttk.Scale(frame, from_=desde, to=hasta, variable=var, orient="horizontal",
                  style="Moderno.Horizontal.TScale").pack(fill="x", padx=20, pady=(2, 0))
        var.trace_add("write", lambda *_: lbl_val.config(text=fmt.format(var.get())))
        setattr(self, f"var_{clave}", var)

    def _panel_der(self, parent):
        self.frame_der = tk.Frame(parent, bg=CARD)
        self.frame_der.grid(row=0, column=1, sticky="nsew")
        self._mostrar_bienvenida()

    def _mostrar_bienvenida(self):
        for w in self.frame_der.winfo_children():
            w.destroy()
        cont = tk.Frame(self.frame_der, bg=CARD)
        cont.pack(expand=True)
        tk.Label(cont, text="⚽", font=(FUENTE, 56), fg=ACENTO, bg=CARD).pack()
        tk.Label(cont, text="Elige dos equipos para empezar",
                 font=(FUENTE, 17, "bold"), fg=TEXTO, bg=CARD).pack(pady=(10, 2))
        tk.Label(cont, text="Pulsa «Predecir partido» y verás probabilidades,\n"
                            "mercados y el mapa de calor de marcadores.",
                 font=(FUENTE, 11), fg=TEXTO_SEC, bg=CARD, justify="center").pack()

    # ── Lógica de liga / desplegables ─────────────────────────────────────

    def _on_liga_change(self):
        liga_nombre = self.var_liga.get()
        if liga_nombre == "Mundial 2026":
            equipos_es = EQUIPOS_MUNDIAL_ES
            self.cb_eq1.config(values=equipos_es)
            self.cb_eq2.config(values=equipos_es)
            self.var_eq1.set("España")
            self.var_eq2.set("Arabia Saudita")
        else:
            self._cargar_equipos_liga(liga_nombre)

    def _cargar_equipos_liga(self, liga_nombre):
        liga_id = LIGAS[liga_nombre]
        temporada = TEMPORADAS[liga_nombre]
        clave = f"{liga_id}_{temporada}"

        if clave in self._equipos_cache:
            self._actualizar_desplegables(self._equipos_cache[clave])
            return

        self.lbl_estado.config(text="Cargando equipos de la liga...")
        self.progreso.start(10)
        self.btn_predecir.config(state="disabled")

        def tarea():
            try:
                equipos, df = cargar_equipos(liga_id, temporada)
                self._equipos_cache[clave] = equipos
                self._df_liga_cache[clave] = df
                self.after(0, lambda: self._actualizar_desplegables(equipos))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda: messagebox.showerror(
                    "Error al cargar equipos", err_msg))
            finally:
                self.after(0, self._parar_progreso)

        threading.Thread(target=tarea, daemon=True).start()

    def _actualizar_desplegables(self, equipos):
        self.cb_eq1.config(values=equipos)
        self.cb_eq2.config(values=equipos)
        if equipos:
            self.var_eq1.set(equipos[0])
            self.var_eq2.set(equipos[1] if len(equipos) > 1 else equipos[0])
        self._parar_progreso()
        self.lbl_estado.config(text="Equipos cargados.")

    # ── Predicción ────────────────────────────────────────────────────────

    def _iniciar_prediccion(self):
        liga_nombre = self.var_liga.get()
        eq1_display = self.var_eq1.get()
        eq2_display = self.var_eq2.get()

        if not eq1_display or not eq2_display:
            messagebox.showwarning("Faltan datos", "Selecciona ambos equipos.")
            return
        if eq1_display == eq2_display:
            messagebox.showwarning("Equipos iguales", "Elige equipos diferentes.")
            return

        if liga_nombre == "Mundial 2026":
            eq1_fbref = NOMBRE_DISPLAY.get(eq1_display, eq1_display)
            eq2_fbref = NOMBRE_DISPLAY.get(eq2_display, eq2_display)
        else:
            eq1_fbref = eq1_display
            eq2_fbref = eq2_display

        liga_id = LIGAS[liga_nombre]
        temporada = TEMPORADAS[liga_nombre]
        rho = round(self.var_rho.get(), 3)
        k = int(self.var_k.get())
        no_cache = not self.var_cache.get()
        actualizar = self.var_actualizar.get()

        self.btn_predecir.config(state="disabled", bg=BORDE)
        self.progreso.start(10)
        self.lbl_estado.config(text="Calculando predicción…")

        def estado(texto):
            self.after(0, lambda: self.lbl_estado.config(text=texto))

        def tarea():
            try:
                # Actualización incremental opcional (solo aplica al Mundial).
                # Solo los 2 equipos del partido y solo fuentes rápidas (API REST,
                # p. ej. football-data.org) → segundos, no minutos.
                if actualizar and liga_id == "INT-World Cup":
                    def avance(i, total, equipo):
                        estado(f"Actualizando datos ({i}/{total}): {equipo}…")
                    try:
                        resumen = proveedores.actualizar_csv(
                            equipos=[eq1_fbref, eq2_fbref],
                            solo_rapidas=True, callback=avance)
                        fuentes = ", ".join(resumen.get("fuentes", [])) or "ninguna"
                        estado(f"Datos al día (+{resumen['partidos_nuevos']} "
                               f"partidos · {fuentes}). Calculando…")
                    except Exception as e:
                        err = str(e)
                        estado("No se pudo actualizar; uso los datos locales.")
                        self.after(0, lambda: messagebox.showwarning(
                            "Actualización fallida",
                            "No se pudieron traer partidos nuevos "
                            f"(se usarán los datos locales):\n\n{err}"))

                resultado = predecir_partido(
                    eq1_fbref, eq2_fbref, liga_id, temporada,
                    rho=rho, k_shrinkage=k, no_cache=no_cache
                )
                self.after(0, lambda: self._mostrar_resultado(
                    resultado, eq1_display, eq2_display))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda: messagebox.showerror("Error", err_msg))
            finally:
                self.after(0, self._parar_progreso)

        threading.Thread(target=tarea, daemon=True).start()

    def _parar_progreso(self):
        self.progreso.stop()
        self.btn_predecir.config(state="normal", bg=ACENTO)

    # ── Panel de resultados ───────────────────────────────────────────────

    def _mostrar_resultado(self, resultado, nombre_eq1, nombre_eq2):
        self.lbl_estado.config(text="¡Listo!")
        for w in self.frame_der.winfo_children():
            w.destroy()

        # Forma reciente en el panel lateral
        self._render_forma_sidebar(resultado, nombre_eq1, nombre_eq2)

        # Pestañas: Predicción / Análisis
        nb = ttk.Notebook(self.frame_der, style="Moderno.TNotebook")
        nb.pack(fill="both", expand=True, padx=12, pady=12)
        tab_pred = tk.Frame(nb, bg=CARD)
        tab_anal = tk.Frame(nb, bg=CARD)
        nb.add(tab_pred, text="  Predicción  ")
        nb.add(tab_anal, text="  Análisis  ")
        self._tab_prediccion(tab_pred, resultado, nombre_eq1, nombre_eq2)
        self._tab_analisis(tab_anal, resultado, nombre_eq1, nombre_eq2)

    def _tab_prediccion(self, parent, r, n1, n2):
        cont = tk.Frame(parent, bg=CARD)
        cont.pack(fill="both", expand=True, padx=18, pady=14)
        p1, px, p2 = r['prob_local'], r['prob_empate'], r['prob_visitante']

        titulo = tk.Frame(cont, bg=CARD)
        titulo.pack(fill="x")
        tk.Label(titulo, text=n1, font=(FUENTE, 15, "bold"), fg=VERDE, bg=CARD).pack(side="left")
        tk.Label(titulo, text="  vs  ", font=(FUENTE, 12), fg=TEXTO_SEC, bg=CARD).pack(side="left")
        tk.Label(titulo, text=n2, font=(FUENTE, 15, "bold"), fg=ROJO, bg=CARD).pack(side="left")

        # 1-X-2 con cuota justa (1/prob)
        fila = tk.Frame(cont, bg=CARD)
        fila.pack(fill="x", pady=(12, 4))
        datos = [(f"Victoria {n1}", p1, VERDE), ("Empate", px, AMARILLO),
                 (f"Victoria {n2}", p2, ROJO)]
        for col, (tit, val, color) in enumerate(datos):
            fila.columnconfigure(col, weight=1, uniform="prob")
            Tarjeta(fila, tit, f"{val * 100:.1f}%", color, sub=_cuota(val), alto=126).grid(
                row=0, column=col, sticky="nsew", padx=5)

        BarraProbabilidad(cont, p1, px, p2).pack(fill="x", pady=(4, 4))
        tk.Label(cont, text=f"Goles esperados (λ)  ·  {n1} {r['lambda_local']:.2f}    "
                            f"{n2} {r['lambda_visitante']:.2f}",
                 font=(FUENTE, 9), fg=TEXTO_SEC, bg=CARD).pack(pady=(4, 8))

        g = lambda k: r.get(k, 0.0)
        # Mercados principales
        f1 = tk.Frame(cont, bg=CARD)
        f1.pack(fill="x", pady=(0, 4))
        m1 = [("Ambos anotan", f"{g('prob_btts') * 100:.0f}%", CIAN, "BTTS"),
              ("Más de 2.5 goles", f"{g('prob_over25') * 100:.0f}%", AMARILLO, _cuota(g('prob_over25'))),
              ("Portería a 0", f"{g('prob_cs_local') * 100:.0f}% / {g('prob_cs_visitante') * 100:.0f}%",
               VERDE, f"{n1[:7]} / {n2[:7]}")]
        # Mercados asiáticos
        f2 = tk.Frame(cont, bg=CARD)
        m2 = [("Más de 1.5 goles", f"{g('prob_over15') * 100:.0f}%", VERDE, _cuota(g('prob_over15'))),
              ("Más de 3.5 goles", f"{g('prob_over35') * 100:.0f}%", ROJO, _cuota(g('prob_over35'))),
              ("Menos de 2.5", f"{g('prob_under25') * 100:.0f}%", CIAN, _cuota(g('prob_under25')))]
        for f, ms, tag in [(f1, m1, "m1"), (f2, m2, "m2")]:
            for col, (t, v, c, s) in enumerate(ms):
                f.columnconfigure(col, weight=1, uniform=tag)
                Tarjeta(f, t, v, c, sub=s, alto=94).grid(row=0, column=col, sticky="nsew", padx=5)
        f2.pack(fill="x", pady=(0, 4))

        self._render_top5(cont, r['matriz'])

    def _render_top5(self, parent, mat):
        n = mat.shape[0]
        idx = np.dstack(np.unravel_index(np.argsort(mat.ravel())[::-1], mat.shape))[0][:5]
        tk.Label(parent, text="MARCADORES MÁS PROBABLES  ·  con cuota justa",
                 font=(FUENTE, 9, "bold"), fg=TEXTO_SEC, bg=CARD).pack(anchor="w", pady=(10, 4))
        fila = tk.Frame(parent, bg=CARD)
        fila.pack(fill="x")
        for i, j in idx:
            prob = float(mat[i, j])
            f = tk.Frame(fila, bg=CARD2, highlightbackground=BORDE, highlightthickness=1)
            f.pack(side="left", expand=True, fill="both", padx=4)
            tk.Label(f, text=f"{i}–{j}", font=(FUENTE, 15, "bold"), fg=TEXTO, bg=CARD2).pack(pady=(8, 0))
            tk.Label(f, text=f"{prob * 100:.1f}%", font=(FUENTE, 10), fg=ACENTO, bg=CARD2).pack()
            tk.Label(f, text=f"@ {1 / prob:.1f}" if prob > 0 else "—",
                     font=(FUENTE, 9), fg=TEXTO_SEC, bg=CARD2).pack(pady=(0, 8))

    def _tab_analisis(self, parent, r, n1, n2):
        cont = tk.Frame(parent, bg=CARD)
        cont.pack(fill="both", expand=True, padx=14, pady=10)
        tk.Label(cont, text="RADAR DE DOMINIO", font=(FUENTE, 9, "bold"),
                 fg=TEXTO_SEC, bg=CARD).pack(anchor="w")
        self._dibujar_radar(cont, r.get('metricas_local', {}), r.get('metricas_visitante', {}), n1, n2)
        tk.Label(cont, text="MAPA DE CALOR · marcadores exactos", font=(FUENTE, 9, "bold"),
                 fg=TEXTO_SEC, bg=CARD).pack(anchor="w", pady=(8, 2))
        self._dibujar_heatmap(cont, r['matriz'], n1, n2)

    def _dibujar_radar(self, parent, m_loc, m_vis, n1, n2):
        ejes = ["Ataque", "Posesión", "Tiros", "Defensa", "Disciplina"]

        def norm(m):
            return [
                _clamp01(m.get("ataque", 0) / 3.0),
                _clamp01(m.get("posesion", 0) / 65.0),
                _clamp01(m.get("tiros", 0) / 12.0),
                _clamp01(1 - m.get("defensa", 0) / 3.0),     # menos goles en contra = mejor
                _clamp01(1 - m.get("disciplina", 0) / 30.0),  # menos faltas/tarjetas = mejor
            ]

        vloc, vvis = norm(m_loc), norm(m_vis)
        ang = np.linspace(0, 2 * np.pi, len(ejes), endpoint=False).tolist()
        ang += ang[:1]
        vloc += vloc[:1]
        vvis += vvis[:1]

        fig = plt.figure(figsize=(4.4, 3.6))
        fig.patch.set_facecolor(CARD)
        ax = fig.add_subplot(111, polar=True)
        ax.set_facecolor(CARD)
        ax.plot(ang, vloc, color=VERDE, linewidth=2)
        ax.fill(ang, vloc, color=VERDE, alpha=0.25)
        ax.plot(ang, vvis, color=ROJO, linewidth=2)
        ax.fill(ang, vvis, color=ROJO, alpha=0.25)
        ax.set_xticks(ang[:-1])
        ax.set_xticklabels(ejes, color=TEXTO_SEC, fontsize=9)
        ax.set_yticklabels([])
        ax.set_ylim(0, 1)
        ax.spines['polar'].set_color(BORDE)
        ax.grid(color=BORDE)
        ax.set_title(f"{n1} (verde)  vs  {n2} (rojo)", color=TEXTO, fontsize=9, pad=14)

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        plt.close(fig)

    def _render_forma_sidebar(self, r, n1, n2):
        for w in self.frame_forma.winfo_children():
            w.destroy()
        tk.Label(self.frame_forma, text="FORMA (últimos 5)", font=(FUENTE, 8, "bold"),
                 fg=TEXTO_SEC, bg=PANEL).pack(anchor="w")
        self._fila_forma(n1, r.get("forma_local", []), r.get("descanso_local", 0))
        self._fila_forma(n2, r.get("forma_visitante", []), r.get("descanso_visitante", 0))

    def _fila_forma(self, nombre, forma, descanso):
        fila = tk.Frame(self.frame_forma, bg=PANEL)
        fila.pack(fill="x", pady=3)
        tk.Label(fila, text=nombre[:11], font=(FUENTE, 9), fg=TEXTO, bg=PANEL,
                 width=11, anchor="w").pack(side="left")
        cv = tk.Canvas(fila, width=96, height=16, bg=PANEL, highlightthickness=0)
        cv.pack(side="left")
        col = {"W": VERDE, "D": TEXTO_SEC, "L": ROJO}
        for i, res in enumerate(forma[-5:]):
            x = i * 19 + 2
            cv.create_oval(x, 2, x + 13, 15, fill=col.get(res, BORDE), outline="")
        tk.Label(fila, text=f"· {int(descanso)}d", font=(FUENTE, 8),
                 fg=TEXTO_SEC, bg=PANEL).pack(side="right")

    def _dibujar_heatmap(self, parent, mat, nombre_eq1, nombre_eq2):
        fig, ax = plt.subplots(figsize=(6.0, 3.6))
        fig.patch.set_facecolor(CARD)
        ax.set_facecolor(CARD)

        cmap = mcolors.LinearSegmentedColormap.from_list(
            "moderno", [CARD, "#312e81", ACENTO, CIAN])
        ax.imshow(mat * 100, cmap=cmap, aspect="auto", vmin=0)

        n = mat.shape[0]
        umbral = mat.max() * 100 * 0.45
        for i in range(n):
            for j in range(n):
                val = mat[i, j] * 100
                ax.text(j, i, f"{val:.0f}", ha="center", va="center", fontsize=8,
                        color="#ffffff" if val < umbral else "#0b1120",
                        fontweight="bold")

        ax.set_xticks(range(n)); ax.set_yticks(range(n))
        ax.set_xticklabels(range(n), color=TEXTO_SEC, fontsize=9)
        ax.set_yticklabels(range(n), color=TEXTO_SEC, fontsize=9)
        ax.set_xlabel(f"Goles {nombre_eq2}", color=TEXTO_SEC, fontsize=10)
        ax.set_ylabel(f"Goles {nombre_eq1}", color=TEXTO_SEC, fontsize=10)
        for spine in ax.spines.values():
            spine.set_edgecolor(BORDE)
        ax.tick_params(colors=BORDE)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        plt.close(fig)


# ── Punto de entrada ──────────────────────────────────────────────────────

if __name__ == "__main__":
    app = PredictorApp()
    app.mainloop()
