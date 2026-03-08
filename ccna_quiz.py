import json
import os
import random
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox

# ── Palette ────────────────────────────────────────────────────────────────────
BG       = "#0d1117"
BG2      = "#161b22"
BG3      = "#1c2333"
BORDER   = "#30363d"
ACCENT   = "#00d4aa"
ACCENT2  = "#0ea5e9"
PURPLE   = "#a78bfa"
WRONG    = "#f87171"
RIGHT    = "#4ade80"
TEXT     = "#e6edf3"
TEXT_DIM = "#8b949e"
YELLOW   = "#fbbf24"
CARD_BG  = "#1a2233"

# ── Recherche du fichier JSON ──────────────────────────────────────────────────
def find_json():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, "scraped_questions", "ccna_questions_part8.json"),
        os.path.join(script_dir, "ccna_questions_part8.json"),
        "scraped_questions/ccna_questions_part8.json",
        "ccna_questions_part8.json",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def normalize_questions(questions):
    """Compatibilité avec l'ancien format JSON (sans champ 'type')."""
    for q in questions:
        if "type" not in q:
            q["type"] = "multiple_choice"
    return questions

# ══════════════════════════════════════════════════════════════════════════════
class CCNAApp(tk.Tk):
    def __init__(self, questions):
        super().__init__()
        self.all_questions = normalize_questions(questions)
        self.title("CCNA Quiz")
        self.configure(bg=BG)
        self.geometry("960x700")
        self.minsize(820, 600)
        self.resizable(True, True)

        self.f_title = tkfont.Font(family="Courier New", size=22, weight="bold")
        self.f_sub   = tkfont.Font(family="Courier New", size=11)
        self.f_q     = tkfont.Font(family="Segoe UI",    size=12, weight="bold")
        self.f_ans   = tkfont.Font(family="Segoe UI",    size=11)
        self.f_btn   = tkfont.Font(family="Courier New", size=11, weight="bold")
        self.f_small = tkfont.Font(family="Segoe UI",    size=9)
        self.f_score = tkfont.Font(family="Courier New", size=36, weight="bold")
        self.f_label = tkfont.Font(family="Courier New", size=10)

        # State
        self.session_questions   = []
        self.current_index       = 0
        self.score               = 0
        self.wrong_questions     = []
        self.answered            = False
        # MCQ
        self.answer_vars         = []
        self.shuffled_answers    = []
        self.ans_buttons         = []
        # Matching
        self.match_terms         = []
        self.match_definitions   = []
        self.match_selected_term = None
        self.match_term_btns     = []
        self.match_def_btns      = []
        self.match_user_pairs    = {}
        self.match_correct_map   = {}

        self._build_menu()

    # ── UI helpers ────────────────────────────────────────────────────────────
    def _clear(self):
        for w in self.winfo_children():
            w.destroy()

    def _scrollable_frame(self, parent):
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(parent, orient="vertical", command=canvas.yview, bg=BG2)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner  = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _resize(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=canvas.winfo_width())

        inner.bind("<Configure>", _resize)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=canvas.winfo_width()))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        return canvas, inner

    def _btn(self, parent, text, command, color=ACCENT, width=18):
        f = tk.Frame(parent, bg=color, padx=2, pady=2)
        b = tk.Button(f, text=text, command=command, font=self.f_btn,
                      bg=BG2, fg=color, activebackground=color, activeforeground=BG,
                      relief="flat", bd=0, cursor="hand2", padx=20, pady=10, width=width)
        b.pack()
        b.bind("<Enter>", lambda e: b.configure(bg=color, fg=BG))
        b.bind("<Leave>", lambda e: b.configure(bg=BG2,   fg=color))
        return f

    def _separator(self, parent):
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=20, pady=8)

    # ── MENU ─────────────────────────────────────────────────────────────────
    def _build_menu(self):
        self._clear()
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", pady=(30, 0))
        tk.Label(header, text="CCNA  QUIZ", font=self.f_title, bg=BG, fg=ACCENT).pack()
        tk.Label(header, text="Entraînement à l'examen Cisco CCNA",
                 font=self.f_sub, bg=BG, fg=TEXT_DIM).pack(pady=(4, 0))

        total    = len(self.all_questions)
        qcm      = sum(1 for q in self.all_questions if q.get("type") == "multiple_choice")
        matching = sum(1 for q in self.all_questions if q.get("type") == "matching")
        stats    = tk.Frame(self, bg=BG3, padx=30, pady=14)
        stats.pack(pady=20, padx=60)
        tk.Label(stats, text=f"📚  {total} questions  ·  {qcm} QCM  ·  {matching} à relier",
                 font=self.f_ans, bg=BG3, fg=TEXT_DIM).pack()

        self._separator(self)
        modes = tk.Frame(self, bg=BG)
        modes.pack(expand=True, fill="both", padx=30, pady=8)

        self._mode_card(modes, "🎯", "Mode Examen",
                        "60 questions aléatoires\nConditions réelles", ACCENT,
                        self._start_exam_mode).pack(side="left", expand=True, fill="both", padx=6, pady=4)

        self._mode_card(modes, "📖", "Mode Libre",
                        "Choisir le nombre\nde questions", ACCENT2,
                        self._show_free_mode_dialog).pack(side="left", expand=True, fill="both", padx=6, pady=4)

        self._mode_card(modes, "🔗", "Relier seulement",
                        f"{matching} questions à relier\nAssocier termes & définitions", PURPLE,
                        lambda: self._start_session(
                            [q for q in self.all_questions if q.get("type") == "matching"])
                        ).pack(side="left", expand=True, fill="both", padx=6, pady=4)

        self._mode_card(modes, "🔁", "Tout réviser",
                        f"Les {total} questions\nOrdre aléatoire", YELLOW,
                        lambda: self._start_session(self.all_questions)
                        ).pack(side="left", expand=True, fill="both", padx=6, pady=4)

        tk.Label(self, text="CCNA 1 ITNv7", font=self.f_small,
                 bg=BG, fg=TEXT_DIM).pack(side="bottom", pady=10)

    def _mode_card(self, parent, icon, title, desc, color, command):
        card  = tk.Frame(parent, bg=BG2, cursor="hand2")
        tk.Frame(card, bg=color, height=3).pack(fill="x")
        inner = tk.Frame(card, bg=BG2, padx=16, pady=16)
        inner.pack(fill="both", expand=True)
        tk.Label(inner, text=icon, font=tkfont.Font(size=22), bg=BG2).pack(anchor="w")
        tk.Label(inner, text=title, font=self.f_btn, bg=BG2, fg=color).pack(anchor="w", pady=(4,2))
        tk.Label(inner, text=desc, font=self.f_small, bg=BG2, fg=TEXT_DIM, justify="left").pack(anchor="w")
        self._btn(inner, "DÉMARRER", command, color=color, width=12).pack(anchor="w", pady=(12,0))
        for w in (card, inner):
            w.bind("<Enter>", lambda e: (card.configure(bg=BG3), inner.configure(bg=BG3)))
            w.bind("<Leave>", lambda e: (card.configure(bg=BG2), inner.configure(bg=BG2)))
        return card

    # ── Free mode dialog ──────────────────────────────────────────────────────
    def _show_free_mode_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("Mode Libre")
        dlg.configure(bg=BG)
        dlg.geometry("400x280")
        dlg.resizable(False, False)
        dlg.grab_set()

        total = len(self.all_questions)
        tk.Label(dlg, text="Nombre de questions", font=self.f_q, bg=BG, fg=TEXT).pack(pady=(24,8))
        tk.Label(dlg, text=f"(1 – {total})", font=self.f_small, bg=BG, fg=TEXT_DIM).pack()
        var = tk.StringVar(value="20")
        tk.Entry(dlg, textvariable=var, font=self.f_ans, bg=BG3, fg=ACCENT,
                 insertbackground=ACCENT, relief="flat", bd=0,
                 justify="center", width=8).pack(pady=12, ipady=6)

        type_var = tk.StringVar(value="all")
        ff = tk.Frame(dlg, bg=BG)
        ff.pack(pady=4)
        for val, lbl in [("all","Tout"),("multiple_choice","QCM"),("matching","Relier")]:
            tk.Radiobutton(ff, text=lbl, variable=type_var, value=val,
                           bg=BG, fg=TEXT_DIM, selectcolor=BG2,
                           activebackground=BG, font=self.f_small).pack(side="left", padx=10)

        def start():
            pool = [q for q in self.all_questions
                    if type_var.get() == "all" or q.get("type") == type_var.get()]
            if not pool:
                messagebox.showerror("Vide","Aucune question pour ce filtre.",parent=dlg); return
            try:
                n = int(var.get())
                assert 1 <= n <= len(pool)
            except Exception:
                messagebox.showerror("Erreur",f"Nombre entre 1 et {len(pool)}.",parent=dlg); return
            dlg.destroy()
            self._start_session(random.sample(pool, n))

        self._btn(dlg, "DÉMARRER", start, color=ACCENT2, width=14).pack(pady=10)

    # ── Session ───────────────────────────────────────────────────────────────
    def _start_exam_mode(self):
        n = min(60, len(self.all_questions))
        self._start_session(random.sample(self.all_questions, n))

    def _start_session(self, questions):
        if not questions:
            messagebox.showinfo("Vide","Aucune question disponible."); return
        self.session_questions = random.sample(questions, len(questions))
        self.current_index     = 0
        self.score             = 0
        self.wrong_questions   = []
        self._build_quiz()

    def _build_quiz(self):
        q = self.session_questions[self.current_index]
        if q.get("type") == "matching":
            self._build_matching()
        else:
            self._build_mcq()

    # ── Top / Bottom bars (shared) ────────────────────────────────────────────
    def _build_topbar(self, num, total, tag_text, tag_color):
        tb = tk.Frame(self, bg=BG2, pady=10, padx=20)
        tb.pack(fill="x")
        left = tk.Frame(tb, bg=BG2)
        left.pack(side="left")
        tk.Label(left, text=f"Q {num} / {total}", font=self.f_label, bg=BG2, fg=TEXT_DIM).pack(anchor="w")
        tk.Label(left, text=f"✔ {self.score}  ✘ {num-1-self.score}",
                 font=self.f_label, bg=BG2, fg=TEXT_DIM).pack(anchor="w")
        mid = tk.Frame(tb, bg=BG2)
        mid.pack(side="left", expand=True, fill="x", padx=20)
        pb = tk.Frame(mid, bg=BORDER, height=6)
        pb.pack(fill="x", pady=8)
        frac = (num-1)/total
        if frac > 0:
            tk.Frame(pb, bg=ACCENT, height=6).place(relx=0, rely=0, relwidth=frac, relheight=1)
        tk.Label(tb, text=tag_text, font=self.f_label, bg=BG2,
                 fg=tag_color, padx=8, pady=3).pack(side="right")

    def _build_botbar(self, num, total, validate_cmd):
        bb = tk.Frame(self, bg=BG2, pady=12, padx=20)
        bb.pack(fill="x", side="bottom")
        self.feedback_label = tk.Label(bb, text="", font=self.f_label, bg=BG2, fg=TEXT)
        self.feedback_label.pack(side="left", padx=10)
        btn_text     = "VALIDER  →" if num < total else "VALIDER  ✔"
        self.next_btn = self._btn(bb, btn_text, validate_cmd, color=ACCENT, width=16)
        self.next_btn.pack(side="right")
        self._btn(bb, "← MENU", self._build_menu, color=TEXT_DIM, width=10).pack(side="right", padx=8)

    def _update_next_btn(self):
        num, total = self.current_index+1, len(self.session_questions)
        for child in self.next_btn.winfo_children():
            child.configure(text="SUIVANT  →" if num < total else "RÉSULTATS  →")

    def _next_question(self):
        self.current_index += 1
        if self.current_index >= len(self.session_questions):
            self._build_results()
        else:
            self._build_quiz()

    # ════════════════════════════════════════════════════════════════════════
    # MCQ
    # ════════════════════════════════════════════════════════════════════════
    def _build_mcq(self):
        self._clear()
        self.answered = False
        q     = self.session_questions[self.current_index]
        num   = self.current_index + 1
        total = len(self.session_questions)
        multi = sum(1 for a in q.get("answers",[]) if a.get("correct")) > 1

        self._build_topbar(num, total,
                           tag_text="✦ Plusieurs réponses" if multi else "● 1 réponse",
                           tag_color=YELLOW if multi else ACCENT2)

        sc = tk.Frame(self, bg=BG)
        sc.pack(fill="both", expand=True)
        _, body = self._scrollable_frame(sc)

        card = tk.Frame(body, bg=CARD_BG, padx=24, pady=18)
        card.pack(fill="x", padx=20, pady=(16,10))
        tk.Label(card, text="QUESTION", font=self.f_label, bg=CARD_BG, fg=ACCENT).pack(anchor="w")
        if q.get("image_url"):
            tk.Label(card, text=f"🖼  {q['image_url']}", font=self.f_small,
                     bg=CARD_BG, fg=TEXT_DIM, wraplength=840, justify="left").pack(anchor="w", pady=(2,0))
        tk.Label(card, text=q["question"], font=self.f_q,
                 bg=CARD_BG, fg=TEXT, wraplength=840, justify="left").pack(anchor="w", pady=(6,0))

        self.answer_vars      = []
        self.ans_buttons      = []
        self.shuffled_answers = list(enumerate(q.get("answers", [])))
        random.shuffle(self.shuffled_answers)

        af = tk.Frame(body, bg=BG)
        af.pack(fill="x", padx=20, pady=4)
        for idx, (_, a) in enumerate(self.shuffled_answers):
            v = tk.BooleanVar(value=False)
            self.answer_vars.append(v)
            self._answer_row(af, idx, "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[idx], a["answer"], v, multi)

        self._build_botbar(num, total, self._validate_mcq)

    def _answer_row(self, parent, idx, label, text, var, multi):
        row   = tk.Frame(parent, bg=BG3, padx=16, pady=12, cursor="hand2")
        row.pack(fill="x", pady=3)
        badge = tk.Label(row, text=label, font=self.f_btn, bg=BORDER, fg=TEXT, width=2, pady=3)
        badge.pack(side="left", padx=(0,12))
        lbl   = tk.Label(row, text=text, font=self.f_ans, bg=BG3, fg=TEXT,
                         wraplength=720, justify="left", anchor="w")
        lbl.pack(side="left", fill="x", expand=True)
        ind   = tk.Label(row, text="☐" if multi else "○", font=self.f_ans, bg=BG3, fg=TEXT_DIM)
        ind.pack(side="right")
        self.ans_buttons.append((row, badge, lbl, ind))

        def toggle(e=None):
            if self.answered: return
            if not multi:
                for i, v in enumerate(self.answer_vars):
                    if i != idx:
                        v.set(False)
                        r,b,l,i2 = self.ans_buttons[i]
                        r.configure(bg=BG3); b.configure(bg=BORDER)
                        l.configure(bg=BG3); i2.configure(text="○", fg=TEXT_DIM)
            var.set(not var.get())
            if var.get():
                row.configure(bg=BG2); badge.configure(bg=ACCENT2, fg=BG)
                lbl.configure(bg=BG2); ind.configure(text="✔" if multi else "●", fg=ACCENT2)
            else:
                row.configure(bg=BG3); badge.configure(bg=BORDER, fg=TEXT)
                lbl.configure(bg=BG3); ind.configure(text="☐" if multi else "○", fg=TEXT_DIM)

        for w in (row, badge, lbl, ind):
            w.bind("<Button-1>", toggle)
        row.bind("<Enter>", lambda e: row.configure(bg="#222d3d") or lbl.configure(bg="#222d3d")
                 if not self.answered and not var.get() else None)
        row.bind("<Leave>", lambda e: row.configure(bg=BG3) or lbl.configure(bg=BG3)
                 if not self.answered and not var.get() else None)

    def _validate_mcq(self):
        if self.answered:
            self._next_question(); return
        q           = self.session_questions[self.current_index]
        correct_set = {i for i,(_, a) in enumerate(self.shuffled_answers) if a.get("correct")}
        chosen_set  = {i for i,v in enumerate(self.answer_vars) if v.get()}
        if not chosen_set:
            self.feedback_label.configure(text="⚠ Sélectionnez au moins une réponse.", fg=YELLOW); return
        self.answered  = True
        is_correct     = (chosen_set == correct_set)
        if is_correct:
            self.score += 1
            self.feedback_label.configure(text="✔ Correct !", fg=RIGHT)
        else:
            self.wrong_questions.append(q)
            self.feedback_label.configure(text="✘ Incorrect", fg=WRONG)
        for i,(row,badge,lbl,ind) in enumerate(self.ans_buttons):
            if i in correct_set:
                row.configure(bg="#0d2d1a"); badge.configure(bg=RIGHT, fg=BG)
                lbl.configure(bg="#0d2d1a", fg=RIGHT); ind.configure(text="✔", fg=RIGHT)
            elif i in chosen_set:
                row.configure(bg="#2d0d0d"); badge.configure(bg=WRONG, fg=BG)
                lbl.configure(bg="#2d0d0d", fg=WRONG); ind.configure(text="✘", fg=WRONG)
        self._update_next_btn()

    # ════════════════════════════════════════════════════════════════════════
    # MATCHING
    # ════════════════════════════════════════════════════════════════════════
    def _build_matching(self):
        self._clear()
        self.answered            = False
        self.match_selected_term = None
        self.match_user_pairs    = {}
        self.match_term_btns     = []
        self.match_def_btns      = []

        q     = self.session_questions[self.current_index]
        num   = self.current_index + 1
        total = len(self.session_questions)
        pairs = q.get("pairs", [])

        self.match_terms       = [p["term"] for p in pairs]
        defs_shuffled          = [p["definition"] for p in pairs]
        random.shuffle(defs_shuffled)
        self.match_definitions = defs_shuffled

        # correct map
        self.match_correct_map = {}
        for t_idx, term in enumerate(self.match_terms):
            correct_def = next(p["definition"] for p in pairs if p["term"] == term)
            self.match_correct_map[t_idx] = self.match_definitions.index(correct_def)

        self._build_topbar(num, total, tag_text="🔗 Relier", tag_color=PURPLE)

        sc = tk.Frame(self, bg=BG)
        sc.pack(fill="both", expand=True)
        _, body = self._scrollable_frame(sc)

        # Question card
        card = tk.Frame(body, bg=CARD_BG, padx=24, pady=18)
        card.pack(fill="x", padx=20, pady=(16,10))
        tk.Label(card, text="QUESTION À RELIER", font=self.f_label, bg=CARD_BG, fg=PURPLE).pack(anchor="w")
        tk.Label(card, text=q["question"], font=self.f_q,
                 bg=CARD_BG, fg=TEXT, wraplength=840, justify="left").pack(anchor="w", pady=(6,0))
        tk.Label(card, text="① Cliquez un terme  →  ② puis une définition pour les associer.",
                 font=self.f_small, bg=CARD_BG, fg=TEXT_DIM).pack(anchor="w", pady=(6,0))

        # Colonnes
        cols = tk.Frame(body, bg=BG)
        cols.pack(fill="x", padx=20, pady=8)
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(2, weight=1)

        tk.Label(cols, text="TERMES", font=self.f_label, bg=BG, fg=PURPLE).grid(
            row=0, column=0, sticky="w", padx=4, pady=(0,6))
        tk.Label(cols, text="DÉFINITIONS", font=self.f_label, bg=BG, fg=ACCENT2).grid(
            row=0, column=2, sticky="w", padx=4, pady=(0,6))
        tk.Frame(cols, bg=BORDER, width=2).grid(
            row=0, column=1, rowspan=len(self.match_terms)+2, sticky="ns", padx=8)

        for i, term in enumerate(self.match_terms):
            b = tk.Button(cols, text=term, font=self.f_ans, bg=BG3, fg=TEXT,
                          relief="flat", bd=0, cursor="hand2",
                          anchor="w", wraplength=360, justify="left",
                          padx=12, pady=10,
                          command=lambda idx=i: self._match_pick_term(idx))
            b.grid(row=i+1, column=0, sticky="ew", padx=4, pady=3)
            self.match_term_btns.append(b)

        for i, defi in enumerate(self.match_definitions):
            b = tk.Button(cols, text=defi, font=self.f_ans, bg=BG3, fg=TEXT,
                          relief="flat", bd=0, cursor="hand2",
                          anchor="w", wraplength=360, justify="left",
                          padx=12, pady=10,
                          command=lambda idx=i: self._match_pick_def(idx))
            b.grid(row=i+1, column=2, sticky="ew", padx=4, pady=3)
            self.match_def_btns.append(b)

        self._build_botbar(num, total, self._validate_matching)

    def _match_pick_term(self, t_idx):
        if self.answered: return
        for b in self.match_term_btns:
            b.configure(bg=BG3, fg=TEXT)
        # Si déjà apparié, on garde la def colorée en bleu
        for t,d in self.match_user_pairs.items():
            self.match_term_btns[t].configure(bg=ACCENT2, fg=BG)
        self.match_selected_term = t_idx
        self.match_term_btns[t_idx].configure(bg=PURPLE, fg=BG)

    def _match_pick_def(self, d_idx):
        if self.answered: return
        if self.match_selected_term is None:
            self.feedback_label.configure(
                text="⚠ Cliquez d'abord un terme (colonne gauche).", fg=YELLOW); return
        t_idx = self.match_selected_term

        # Effacer les anciens liens conflictuels
        for t, d in list(self.match_user_pairs.items()):
            if t == t_idx or d == d_idx:
                del self.match_user_pairs[t]
                self.match_term_btns[t].configure(bg=BG3, fg=TEXT)
                self.match_def_btns[d].configure(bg=BG3, fg=TEXT)

        self.match_user_pairs[t_idx] = d_idx
        self.match_term_btns[t_idx].configure(bg=ACCENT2, fg=BG)
        self.match_def_btns[d_idx].configure(bg=ACCENT2, fg=BG)
        self.match_selected_term = None
        n = len(self.match_user_pairs)
        tot = len(self.match_terms)
        self.feedback_label.configure(
            text=f"  {n}/{tot} paires reliées{'  — Prêt !' if n == tot else ''}", fg=TEXT_DIM)

    def _validate_matching(self):
        if self.answered:
            self._next_question(); return
        n_pairs = len(self.match_user_pairs)
        n_total = len(self.match_terms)
        if n_pairs < n_total:
            self.feedback_label.configure(
                text=f"⚠ Reliez toutes les paires ({n_pairs}/{n_total})", fg=YELLOW); return

        self.answered = True
        nb_ok = sum(1 for t,d in self.match_user_pairs.items()
                    if d == self.match_correct_map[t])
        perfect = (nb_ok == n_total)

        if perfect:
            self.score += 1
            self.feedback_label.configure(text="✔ Parfait ! Toutes les paires sont correctes.", fg=RIGHT)
        else:
            self.wrong_questions.append(self.session_questions[self.current_index])
            self.feedback_label.configure(
                text=f"✘ {nb_ok}/{n_total} paires correctes", fg=WRONG)

        # Coloriser
        for t_idx, d_idx in self.match_user_pairs.items():
            ok  = (d_idx == self.match_correct_map[t_idx])
            col = RIGHT if ok else WRONG
            bg  = "#0d2d1a" if ok else "#2d0d0d"
            self.match_term_btns[t_idx].configure(bg=bg, fg=col)
            self.match_def_btns[d_idx].configure(bg=bg, fg=col)

        # Surligner les bonnes définitions manquées
        for t_idx in range(n_total):
            correct_d = self.match_correct_map[t_idx]
            if self.match_user_pairs.get(t_idx) != correct_d:
                self.match_def_btns[correct_d].configure(bg="#0d2d1a", fg=RIGHT)

        self._update_next_btn()

    # ── RESULTS ──────────────────────────────────────────────────────────────
    def _build_results(self):
        self._clear()
        total = len(self.session_questions)
        pct   = self.score / total * 100
        if pct >= 70:   grade_color, grade_text = RIGHT,  "RÉUSSI ✔"
        elif pct >= 50: grade_color, grade_text = YELLOW, "MOYEN ⚡"
        else:           grade_color, grade_text = WRONG,  "ÉCHOUÉ ✘"

        hdr = tk.Frame(self, bg=BG2, pady=28)
        hdr.pack(fill="x")
        tk.Label(hdr, text="RÉSULTATS", font=self.f_title, bg=BG2, fg=TEXT).pack()
        tk.Label(hdr, text=grade_text,
                 font=tkfont.Font(family="Courier New", size=14, weight="bold"),
                 bg=BG2, fg=grade_color).pack(pady=4)

        sf = tk.Frame(self, bg=BG)
        sf.pack(pady=12)
        tk.Label(sf, text=f"{self.score}", font=self.f_score, bg=BG, fg=grade_color).pack()
        tk.Label(sf, text=f"sur {total} questions  ·  {pct:.0f}%",
                 font=self.f_sub, bg=BG, fg=TEXT_DIM).pack()

        pb = tk.Frame(self, bg=BORDER, height=12)
        pb.pack(fill="x", padx=60, pady=6)
        tk.Frame(pb, bg=grade_color, height=12).place(relx=0, rely=0, relwidth=pct/100, relheight=1)

        self._separator(self)

        if self.wrong_questions:
            sc = tk.Frame(self, bg=BG)
            sc.pack(fill="both", expand=True)
            _, body = self._scrollable_frame(sc)
            tk.Label(body, text=f"  Questions ratées ({len(self.wrong_questions)})",
                     font=self.f_label, bg=BG, fg=WRONG).pack(anchor="w", padx=20, pady=(8,4))
            for q in self.wrong_questions:
                card = tk.Frame(body, bg=BG3, padx=16, pady=10)
                card.pack(fill="x", padx=20, pady=3)
                tk.Label(card, text=q["question"], font=self.f_small,
                         bg=BG3, fg=TEXT_DIM, wraplength=860, justify="left").pack(anchor="w")
                if q.get("type") == "matching":
                    for p in q.get("pairs", []):
                        tk.Label(card, text=f"  ✔ {p['term']}  →  {p['definition']}",
                                 font=self.f_small, bg=BG3, fg=RIGHT,
                                 wraplength=820, justify="left").pack(anchor="w")
                else:
                    for a in q.get("answers", []):
                        if a.get("correct"):
                            tk.Label(card, text=f"  ✔ {a['answer']}", font=self.f_small,
                                     bg=BG3, fg=RIGHT, wraplength=820, justify="left").pack(anchor="w")

        bb = tk.Frame(self, bg=BG2, pady=14, padx=20)
        bb.pack(fill="x", side="bottom")
        self._btn(bb, "← MENU PRINCIPAL", self._build_menu, color=TEXT_DIM, width=18).pack(side="left")
        self._btn(bb, "↺ REJOUER",
                  lambda: self._start_session(self.session_questions),
                  color=ACCENT, width=14).pack(side="right")
        self._btn(bb, "✘ Réviser ratées",
                  lambda: self._start_session(self.wrong_questions) if self.wrong_questions else None,
                  color=WRONG, width=16).pack(side="right", padx=8)


# ══════════════════════════════════════════════════════════════════════════════
def main():
    filepath = find_json()
    if not filepath:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror(
            "Fichier introuvable",
            "Impossible de trouver le fichier JSON.\n"
            "Lancez d'abord scrap_ccna.py,\n"
            "ou placez ccna_questions_part8.json dans 'scraped_questions/'."
        )
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print(f"✔ {len(questions)} questions chargées depuis {os.path.basename(filepath)}")
    CCNAApp(questions).mainloop()

if __name__ == "__main__":
    main()