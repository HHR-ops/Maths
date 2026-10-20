"""Offline Windows desktop UI for four linear adjustment models."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np

from adjustment import (AdjustmentError, FORMULAS, MODEL_NAMES, make_report,
                        parse_matrix, solve)
from examples import EXAMPLES
from network_ui import NetworkWorkspace
from ui_theme import BG,SIDEBAR,EDGE,GREEN,INK,MUTED,FONT,SOFT,install
FIELDS = {
    "A": ("A · 条件系数", "每行一个条件，每列对应一个观测值。"),
    "B": ("B · 参数系数", "间接平差：每行一个观测，每列一个参数；条件平差：每行一个条件。"),
    "w": ("w · 条件闭合差", "与 A 行数相同；严格按 A v + B x + w = 0 的符号录入。"),
    "l": ("l · 常数项", "与 B 行数相同；v = B x − l；线性化时 l = L − f(X₀)。"),
    "C": ("C · 限制系数", "每行一个独立限制，每列对应一个参数。限制为确定值。"),
    "d": ("d · 限制常数", "严格按 C x + d = 0 录入，注意常数正负号。"),
    "P": ("P · 观测权阵", "输入权而非方差；对角权填 n 个正数，完整权阵需对称正定。"),
    "observed": ("L · 观测值（可选）", "填写后输出 L̂ = L + v。不能由 L 自动生成系数或闭合差。"),
    "x0": ("X₀ · 参数初值（可选）", "仅当 x 是参数改正数时填写；输出 X̂ = X₀ + x。"),
}
MODEL_FIELDS = {
    "condition": ["A", "w"],
    "condition_parameters": ["A", "B", "w"],
    "indirect": ["B", "l"],
    "indirect_constraints": ["B", "l", "C", "d"],
}


class MatrixEditor(tk.Frame):
    def __init__(self, parent, key, value, callback):
        super().__init__(parent, bg="white", highlightbackground="#dce3e8", highlightthickness=1)
        self.key, self.callback = key, callback
        title, hint = FIELDS[key]
        top = tk.Frame(self, bg="white")
        top.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(top, text=title, font=(FONT, 10, "bold"), bg="white", fg=INK).pack(side="left")
        self.shape_label = tk.Label(top, text="", font=(FONT, 9), bg="white", fg=MUTED)
        self.shape_label.pack(side="right")
        self.text = tk.Text(self, height=4, font=("Consolas", 11), wrap="none", undo=True,
                            bg="#f8fafb", fg=INK, insertbackground=GREEN, relief="flat",
                            padx=8, pady=6, highlightthickness=1, highlightbackground="#e7edf0")
        self.text.pack(fill="both", expand=True, padx=12)
        self.text.insert("1.0", value)
        self.text.edit_modified(False)
        tk.Label(self, text=hint, font=(FONT, 9), bg="white", fg=MUTED,
                 wraplength=430, anchor="w", justify="left").pack(fill="x", padx=12, pady=(5, 9))
        self.text.bind("<<Modified>>", self.on_edit)
        self.text.bind("<Control-a>", self.select_all)
        self.update_shape()

    def get(self):
        return self.text.get("1.0", "end-1c").strip()

    def select_all(self, _event):
        self.text.tag_add("sel", "1.0", "end-1c")
        return "break"

    def on_edit(self, _event):
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self.update_shape()
            self.callback()

    def update_shape(self):
        content = self.get()
        if not content:
            self.shape_label.config(text="未填写", fg=MUTED)
            return
        try:
            a = parse_matrix(content, self.key)
            self.shape_label.config(text=f"{a.shape[0]} × {a.shape[1]}", fg=GREEN)
        except AdjustmentError:
            self.shape_label.config(text="格式待检查", fg="#b65d37")


class AdjustmentApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.model = "condition"
        self.result = None
        self.project_path = None
        self.dirty = False
        self.loading = True
        self.ui_scale = max(1.0, float(root.tk.call("tk", "scaling")) / (96 / 72))
        self.drafts = {key: dict(value) for key, value in EXAMPLES.items()}
        self.editors = {}
        self.root.title("测量平差工作台 v0.3")
        screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
        width = min(int(1280*self.ui_scale), screen_w-80)
        height = min(int(860*self.ui_scale), screen_h-100)
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(min(int(1040*self.ui_scale), screen_w-80), min(int(720*self.ui_scale), screen_h-100))
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.style()
        self.build_shell()
        self.load_fields(self.drafts[self.model])
        self.loading = False
        self.notebook.select(self.network)
        self.on_tab_changed()
        self.status.set("控制网画布已就绪 · 可自由布网、录入观测，或切换到四类矩阵模型。")
        root.bind("<Control-Return>", lambda _e: self.calculate())
        root.bind("<Control-s>", lambda _e: self.save_project())
        root.bind("<Control-o>", lambda _e: self.open_project())

    def style(self):
        self.widget_style=install(self.root,self.ui_scale)

    def build_shell(self):
        u=lambda n:round(n*self.ui_scale)
        side = tk.Frame(self.root, width=u(184), bg=SIDEBAR)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        brand=tk.Frame(side,bg=SIDEBAR);brand.pack(fill="x",padx=u(18),pady=(u(23),u(28)))
        mark=tk.Canvas(brand,width=u(24),height=u(26),bg=SIDEBAR,highlightthickness=0)
        mark.pack(side="left",padx=(0,u(9)))
        mark.create_line(u(3),u(20),u(12),u(5),u(21),u(20),u(3),u(20),fill=GREEN,width=u(1))
        for x,y in ((3,20),(12,5),(21,20)):mark.create_oval(u(x)-u(2),u(y)-u(2),u(x)+u(2),u(y)+u(2),fill=GREEN,outline=SIDEBAR)
        labels=tk.Frame(brand,bg=SIDEBAR);labels.pack(side="left")
        tk.Label(labels,text="测量平差",font=(FONT,12,"bold"),bg=SIDEBAR,fg=INK).pack(anchor="w")
        tk.Label(labels,text="本地工作台",font=(FONT,8),bg=SIDEBAR,fg=MUTED).pack(anchor="w",pady=(u(2),0))
        def nav(text,command):
            button=tk.Button(side,text=text,anchor="w",font=(FONT,10),bg=SIDEBAR,fg=INK,relief="flat",bd=0,highlightthickness=0,padx=u(14),pady=u(10),cursor="hand2",activebackground=SOFT,activeforeground=GREEN,command=command)
            button.pack(fill="x",padx=u(10),pady=u(2));return button
        self.home_button=nav("控制网画布",lambda:self.notebook.select(self.network))
        tk.Label(side,text="矩阵平差",font=(FONT,8),bg=SIDEBAR,fg=MUTED).pack(anchor="w",padx=u(24),pady=(u(25),u(7)))
        self.model_buttons = {}
        for key,name in {"condition":"条件平差","condition_parameters":"附参条件平差","indirect":"间接平差","indirect_constraints":"附限间接平差"}.items():
            self.model_buttons[key]=nav(name,lambda k=key:self.switch_model(k))
        bottom=tk.Frame(side,bg=SIDEBAR);bottom.pack(side="bottom",fill="x",padx=u(23),pady=u(20))
        self.help_button=tk.Button(bottom,text="使用说明",font=(FONT,9),bg=SIDEBAR,fg=MUTED,activebackground=SOFT,activeforeground=GREEN,relief="flat",bd=0,anchor="w",cursor="hand2",command=lambda:self.notebook.select(self.help_tab))
        self.help_button.pack(fill="x",pady=(0,u(10)))
        tk.Label(bottom,text="离线运行  ·  v0.3",font=(FONT,8),bg=SIDEBAR,fg="#9aa5ae").pack(anchor="w")
        tk.Frame(self.root,width=1,bg=EDGE).pack(side="left",fill="y")
        main = ttk.Frame(self.root, padding=(u(20),u(18),u(20),u(10)))
        main.pack(fill="both", expand=True)
        header = ttk.Frame(main)
        header.pack(fill="x",pady=(0,u(14)))
        self.heading = ttk.Label(header, font=(FONT,15,"bold"))
        self.heading.pack(side="left")
        ttk.Button(header,text="计算平差",style="Accent.TButton",command=self.calculate).pack(side="right",padx=(u(12),0))
        for label, action in [("保存项目", self.save_project), ("打开项目", self.open_project)]:
            ttk.Button(header, text=label,style="Ghost.TButton",command=action).pack(side="right",padx=(u(4),0))
        ttk.Separator(main).pack(fill="x",pady=(0,u(14)))
        self.formula = ttk.Label(main, foreground=MUTED, font=("Consolas",11))
        self.formula.pack(anchor="w", pady=(0,u(10)))
        project = ttk.Frame(main)
        self.project_frame=project
        project.pack(fill="x", pady=(0, 14))
        ttk.Label(project, text="计算名称").pack(side="left", padx=(0, 10))
        self.title = tk.StringVar()
        ttk.Entry(project, textvariable=self.title, font=(FONT, 10)).pack(side="left", fill="x", expand=True)
        self.title.trace_add("write", lambda *_: self.mark_dirty())
        self.matrix_nav=ttk.Frame(main)
        self.matrix_nav_buttons={}
        self.notebook = ttk.Notebook(main,style="Shell.TNotebook")
        self.notebook.pack(fill="both", expand=True)
        self.input_tab = ttk.Frame(self.notebook)
        self.result_tab = ttk.Frame(self.notebook, padding=14)
        self.report_tab = ttk.Frame(self.notebook, padding=12)
        self.help_tab = ttk.Frame(self.notebook, padding=14)
        self.network=NetworkWorkspace(self.notebook,on_matrix=self.receive_network_matrix)
        self.notebook.add(self.network,text="控制网画布")
        for frame, name in [(self.input_tab, "数据录入"), (self.result_tab, "平差结果"),
                            (self.report_tab, "计算报告"), (self.help_tab, "使用说明")]:
            self.notebook.add(frame, text=name)
        for frame,name in [(self.input_tab,"数据录入"),(self.result_tab,"平差结果"),(self.report_tab,"计算报告")]:
            button=ttk.Button(self.matrix_nav,text=name,style="Tab.TButton",command=lambda f=frame:self.notebook.select(f))
            button.pack(side="left",padx=(0,u(5)));self.matrix_nav_buttons[str(frame)]=button
        canvas = tk.Canvas(self.input_tab, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.input_tab, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        self.input_body = ttk.Frame(canvas, padding=12)
        window = canvas.create_window((0, 0), window=self.input_body, anchor="nw")
        self.input_body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        def wheel(event):
            if self.notebook.select() == str(self.input_tab) and not isinstance(event.widget, tk.Text):
                canvas.yview_scroll(-int(event.delta / 120), "units")
        self.root.bind("<MouseWheel>", wheel, add=True)
        self.input_canvas = canvas
        self.weight_mode = tk.StringVar(value="对角权")
        self.precision = tk.StringVar(value="后验")
        self.sigma0 = tk.StringVar(value="1")
        self.digits = tk.StringVar(value="8")
        for var in (self.precision, self.sigma0):
            var.trace_add("write", lambda *_: self.mark_dirty())
        self.build_results()
        self.build_report()
        self.build_help()
        self.status = tk.StringVar(value="就绪")
        status_label = ttk.Label(main, textvariable=self.status, font=(FONT,8), foreground=MUTED,
                                 wraplength=int(980*self.ui_scale))
        # Reserve the status line before the expanding notebook consumes height.
        status_label.pack(side="bottom", fill="x", pady=(10, 0), before=self.notebook)
        self.notebook.bind("<<NotebookTabChanged>>",self.on_tab_changed)
        self.network.notice.trace_add("write",self.network_notice_changed)

    def network_notice_changed(self,*_args):
        if self.network_active():self.status.set(self.network.notice.get())

    def network_active(self):
        return hasattr(self,"network") and self.notebook.select()==str(self.network)

    def on_tab_changed(self,_event=None):
        if not hasattr(self,"network"):return
        if self.network_active():
            self.project_frame.pack_forget()
            self.matrix_nav.pack_forget();self.formula.pack_forget()
            self.heading.config(text="控制网画布")
            self.home_button.config(bg=SOFT,fg=GREEN)
            for button in self.model_buttons.values():button.config(bg=SIDEBAR,fg=INK)
            if hasattr(self,"status") and self.network.notice.get():self.status.set(self.network.notice.get())
        elif self.notebook.select()==str(self.help_tab):
            self.project_frame.pack_forget();self.matrix_nav.pack_forget();self.formula.pack_forget()
            self.heading.config(text="使用说明");self.home_button.config(bg=SIDEBAR,fg=INK)
            for button in self.model_buttons.values():button.config(bg=SIDEBAR,fg=INK)
        else:
            self.project_frame.pack(fill="x",pady=(0,14),before=self.notebook)
            self.formula.pack(anchor="w",pady=(0,10),before=self.project_frame)
            self.matrix_nav.pack(fill="x",pady=(0,12),before=self.notebook)
            self.heading.config(text=MODEL_NAMES[self.model]); self.formula.config(text=FORMULAS[self.model]+"     |     min vᵀPv")
            self.home_button.config(bg=SIDEBAR,fg=INK)
            for key,button in self.model_buttons.items():button.config(bg=SOFT if key==self.model else SIDEBAR,fg=GREEN if key==self.model else INK)
        for frame,button in self.matrix_nav_buttons.items():button.configure(style="TabActive.TButton" if self.notebook.select()==frame else "Tab.TButton")

    def receive_network_matrix(self,model,data):
        self.drafts[self.model]=self.snapshot()
        self.model=model; self.load_fields(data); self.clear_results()
        self.notebook.select(self.input_tab); self.dirty=True
        self.status.set("已从控制网提取矩阵；原始布网保留在“控制网画布”中。")

    def load_fields(self, data):
        self.loading = True
        for child in self.input_body.winfo_children():
            child.destroy()
        self.editors = {}
        self.title.set(data.get("title", "未命名计算"))
        self.heading.config(text=MODEL_NAMES[self.model])
        self.formula.config(text=FORMULAS[self.model] + "     |     min vᵀPv")
        for key, button in self.model_buttons.items():
            button.config(bg=SOFT if key==self.model else SIDEBAR,fg=GREEN if key==self.model else INK)
        bar = ttk.Frame(self.input_body)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="从 Excel 复制矩阵后直接粘贴；空格 / Tab 分列，换行或分号分行。",
                  font=(FONT, 9), foreground=MUTED).pack(side="left")
        ttk.Button(bar, text="载入本模型例题", command=self.load_example).pack(side="right")
        note = data.get("note", "")
        if note:
            ttk.Label(self.input_body, text=note, foreground=GREEN, wraplength=920,
                      font=(FONT, 9)).pack(fill="x", pady=(0, 10))
        grid = ttk.Frame(self.input_body)
        grid.pack(fill="both", expand=True)
        grid.columnconfigure(0, weight=1, uniform="edit")
        grid.columnconfigure(1, weight=1, uniform="edit")
        fields = MODEL_FIELDS[self.model]
        for i, key in enumerate(fields):
            editor = MatrixEditor(grid, key, data.get(key, ""), self.mark_dirty)
            editor.grid(row=i // 2, column=i % 2, sticky="nsew", padx=(0, 8) if i % 2 == 0 else (0, 0), pady=(0, 8))
            self.editors[key] = editor
        options = ttk.Frame(self.input_body)
        options.pack(fill="x", pady=(9, 10))
        ttk.Label(options, text="观测权").pack(side="left", padx=(0, 7))
        self.weight_mode.set(data.get("weight_mode", "等权 P = I"))
        weight = ttk.Combobox(options, textvariable=self.weight_mode, state="readonly", width=14,
                             values=["等权 P = I", "对角权", "完整权阵"])
        weight.pack(side="left")
        weight.bind("<<ComboboxSelected>>", lambda _e: self.weight_changed())
        ttk.Label(options, text="精度基准").pack(side="left", padx=(18, 7))
        self.precision.set(data.get("precision", "后验"))
        ttk.Combobox(options, textvariable=self.precision, state="readonly", width=6,
                     values=["后验", "先验"]).pack(side="left")
        ttk.Label(options, text="先验 σ₀").pack(side="left", padx=(18, 7))
        self.sigma0.set(str(data.get("sigma0", "1")))
        ttk.Entry(options, textvariable=self.sigma0, width=10).pack(side="left")
        common = ttk.Frame(self.input_body)
        common.pack(fill="x")
        common.columnconfigure(0, weight=1, uniform="common")
        common.columnconfigure(1, weight=1, uniform="common")
        keys = ["P", "observed"] + (["x0"] if self.model != "condition" else [])
        for i, key in enumerate(keys):
            editor = MatrixEditor(common, key, data.get(key, ""), self.mark_dirty)
            editor.grid(row=i // 2, column=i % 2, sticky="nsew", padx=(0, 8) if i % 2 == 0 else (0, 0), pady=(0, 8))
            self.editors[key] = editor
        self.weight_changed(mark=False)
        self.loading = False
        self.input_canvas.yview_moveto(0)

    def snapshot(self):
        return {"title": self.title.get(), "note": "", "weight_mode": self.weight_mode.get(),
                "precision": self.precision.get(), "sigma0": self.sigma0.get(),
                **{key: editor.get() for key, editor in self.editors.items()}}

    def weight_changed(self, mark=True):
        if "P" in self.editors:
            self.editors["P"].text.config(state="disabled" if self.weight_mode.get() == "等权 P = I" else "normal")
        if mark:
            self.mark_dirty()

    def mark_dirty(self):
        if self.loading:
            return
        self.dirty = True
        if self.result is not None:
            self.clear_results()
        if hasattr(self, "status"):
            self.status.set("数据已修改 · 请重新计算；Ctrl+Enter 计算，Ctrl+S 保存项目。")

    def switch_model(self, model):
        if model == self.model:
            self.notebook.select(self.input_tab)
            return
        self.drafts[self.model] = self.snapshot()
        self.model = model
        self.load_fields(self.drafts[model])
        self.clear_results()
        self.notebook.select(self.input_tab)
        self.status.set("已切换模型 · 各模型输入在本次运行期间分别保留；保存项目可持久保存当前模型。")
        self.dirty = True

    def load_example(self, confirm=True):
        if confirm and self.dirty and not messagebox.askyesno("载入例题", "用本模型例题替换当前输入？其他模型的输入会保留。", parent=self.root):
            return
        self.load_fields(EXAMPLES[self.model])
        self.clear_results()
        self.dirty = True
        self.status.set("例题已载入 · 点击“计算平差”查看结果。")

    def build_results(self):
        self.metrics = tk.StringVar(value="计算后显示观测数、参数数、自由度和精度指标。")
        ttk.Label(self.result_tab, textvariable=self.metrics, font=(FONT, 11, "bold"),
                  wraplength=980, foreground=GREEN).pack(fill="x", pady=(0, 10))
        actions = ttk.Frame(self.result_tab)
        actions.pack(fill="x", pady=(0, 12))
        self.export_buttons = []
        for label, fmt in [("导出 CSV 表格", "csv"), ("导出完整 JSON", "json")]:
            b = ttk.Button(actions, text=label, command=lambda f=fmt: self.export_result(f), state="disabled")
            b.pack(side="left", padx=(0, 8))
            self.export_buttons.append(b)
        panes = ttk.Panedwindow(self.result_tab, orient="vertical")
        panes.pack(fill="both", expand=True)
        self.observation_tree = self.table(panes, "观测值与改正数", ["序号", "观测值 L", "改正数 v", "平差值 L̂", "平差值中误差"], height=9)
        self.parameter_tree = self.table(panes, "参数结果", ["序号", "参数解 x", "初值 X₀", "平差值 X̂", "参数中误差"], height=5)
        self.result_note = tk.StringVar(value="")
        ttk.Label(self.result_tab, textvariable=self.result_note, font=(FONT, 9), foreground=MUTED,
                  wraplength=960).pack(fill="x", pady=(10, 0))

    def table(self, parent, title, columns, height):
        frame = ttk.Frame(parent, padding=(0, 4, 0, 8))
        parent.add(frame, weight=2 if height > 5 else 1)
        ttk.Label(frame, text=title, font=(FONT, 11, "bold")).pack(anchor="w", pady=(0, 6))
        content = ttk.Frame(frame)
        content.pack(fill="both", expand=True)
        tree = ttk.Treeview(content, columns=columns, show="headings", height=height)
        for i, c in enumerate(columns):
            tree.heading(c, text=c)
            tree.column(c, width=60 if i == 0 else 170, minwidth=55 if i == 0 else 115, anchor="center" if i == 0 else "e")
        sb = ttk.Scrollbar(content, orient="vertical", command=tree.yview)
        hs = ttk.Scrollbar(content, orient="horizontal", command=tree.xview)
        tree.config(yscrollcommand=sb.set, xscrollcommand=hs.set)
        sb.pack(side="right", fill="y")
        hs.pack(side="bottom", fill="x")
        tree.pack(fill="both", expand=True)
        return tree

    def build_report(self):
        actions = ttk.Frame(self.report_tab)
        actions.pack(fill="x", pady=(0, 10))
        for text, action in [("保存 TXT 报告", lambda: self.export_result("txt")), ("复制报告", self.copy_report)]:
            b = ttk.Button(actions, text=text, command=action, state="disabled")
            b.pack(side="left", padx=(0, 8))
            self.export_buttons.append(b)
        ttk.Label(actions, text="有效数字").pack(side="left", padx=(16, 8))
        box = ttk.Combobox(actions, textvariable=self.digits, state="readonly", width=5, values=["6", "8", "10", "12"])
        box.pack(side="left")
        box.bind("<<ComboboxSelected>>", lambda _e: self.refresh_results())
        self.report_text = tk.Text(self.report_tab, font=("Consolas", 11), bg="white", fg=INK,
                                   wrap="none", relief="flat", padx=12, pady=12, state="disabled")
        sb = ttk.Scrollbar(self.report_tab, orient="vertical", command=self.report_text.yview)
        hs = ttk.Scrollbar(self.report_tab, orient="horizontal", command=self.report_text.xview)
        self.report_text.config(yscrollcommand=sb.set, xscrollcommand=hs.set)
        sb.pack(side="right", fill="y")
        hs.pack(side="bottom", fill="x")
        self.report_text.pack(fill="both", expand=True)

    def build_help(self):
        text = tk.Text(self.help_tab, wrap="word", font=(FONT, 11), bg="white", fg=INK,
                       relief="flat", padx=22, pady=18, spacing3=9)
        text.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(self.help_tab, orient="vertical", command=text.yview)
        sb.pack(side="right", fill="y")
        text.config(yscrollcommand=sb.set)
        text.insert("1.0", HELP)
        text.config(state="disabled")

    def calculate(self, show_error=True):
        if self.network_active():return self.network.calculate()
        try:
            values = {key: parse_matrix(self.editors[key].get(), key) for key in MODEL_FIELDS[self.model]}
            weight_mode = self.weight_mode.get()
            if weight_mode != "等权 P = I":
                p = parse_matrix(self.editors["P"].get(), "P")
                if weight_mode == "对角权" and 1 not in p.shape:
                    raise AdjustmentError("当前选择“对角权”，请填写一行或一列正权值；完整矩阵请切换为“完整权阵”。")
                if weight_mode == "完整权阵" and p.shape[0] != p.shape[1]:
                    raise AdjustmentError("当前选择“完整权阵”，请填写 n×n 方阵。")
                values["P"] = p
            for key in ("observed", "x0"):
                if key in self.editors and self.editors[key].get():
                    values[key] = parse_matrix(self.editors[key].get(), key)
            self.root.config(cursor="watch")
            self.root.update_idletasks()
            self.result = solve(self.model, **values, sigma0=self.sigma0.get(),
                                precision="prior" if self.precision.get() == "先验" else "posterior")
            self.refresh_results()
            self.notebook.select(self.result_tab)
            self.status.set("计算完成 · 方程校核通过；查看“计算报告”复核中间量与协因数阵。")
            return True
        except (AdjustmentError, np.linalg.LinAlgError) as exc:
            self.clear_results()
            self.status.set("未能计算 · " + str(exc))
            if show_error:
                messagebox.showerror("请检查输入", str(exc), parent=self.root)
            return False
        finally:
            self.root.config(cursor="")

    def number(self, value):
        return "—" if value is None else f"{float(value):.{int(self.digits.get())}g}"

    def refresh_results(self):
        r = self.result
        if r is None:
            return
        self.metrics.set(f"观测 {r.n}  ·  参数 {r.t}  ·  自由度 {r.dof}     |     "
                         f"vᵀPv = {self.number(r.weighted_sum)}     |     后验 σ̂₀ = {self.number(r.posterior_sigma)}")
        for tree in (self.observation_tree, self.parameter_tree):
            tree.delete(*tree.get_children())
        mL, mx = r.std(r.q_adjusted), r.std(r.qxx)
        for i in range(r.n):
            self.observation_tree.insert("", "end", values=(i + 1,
                self.number(r.observed[i] if r.observed is not None else None), self.number(r.v[i]),
                self.number(r.adjusted[i] if r.adjusted is not None else None),
                self.number(mL[i] if mL is not None else None)))
        if r.x is not None:
            for i in range(r.t):
                self.parameter_tree.insert("", "end", values=(i + 1, self.number(r.x[i]),
                    self.number(r.x0[i] if r.x0 is not None else None),
                    self.number(r.parameters[i] if r.parameters is not None else None),
                    self.number(mx[i] if mx is not None else None)))
        self.result_note.set(("；".join(r.warnings) + "\n" if r.warnings else "")
                             + f"中误差采用{'先验' if r.precision_source == 'prior' else '后验'}基准；“—”表示未提供或无法估计。原始单位沿用输入。"
                             + (" 参数表中的 x 为未知量，填写 X₀ 后才显示 X̂。" if r.x is not None else ""))
        self.report_text.config(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", make_report(r, self.title.get(), int(self.digits.get())))
        self.report_text.config(state="disabled")
        for button in self.export_buttons:
            button.config(state="normal")

    def clear_results(self):
        self.result = None
        for tree in (self.observation_tree, self.parameter_tree):
            tree.delete(*tree.get_children())
        self.metrics.set("尚无当前输入的计算结果 · 请计算平差。")
        self.result_note.set("")
        self.report_text.config(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.config(state="disabled")
        for button in self.export_buttons:
            button.config(state="disabled")

    def save_project(self, path=None, matrix_only=False):
        if not matrix_only and self.network_active():return self.network.save_project(path)
        if path is None:
            path = filedialog.asksaveasfilename(parent=self.root, title="保存当前模型项目", defaultextension=".sap.json",
                        filetypes=[("平差项目", "*.sap.json"), ("JSON", "*.json")],
                        initialfile=Path(self.project_path).name if self.project_path else "平差项目.sap.json")
        if not path:
            return False
        try:
            document = {"format": "survey-adjustment-project", "version": 1,
                        "model": self.model, "data": self.snapshot()}
            Path(path).write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
            self.project_path, self.dirty = str(path), False
            self.status.set("项目已保存 · " + str(path))
            return True
        except OSError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self.root)
            return False

    def open_project(self, path=None):
        if self.network_active():return self.network.open_project(path)
        if path is None:
            if self.dirty:
                answer = messagebox.askyesnocancel("保存当前输入", "打开项目之前，是否保存当前模型的输入？", parent=self.root)
                if answer is None or (answer and not self.save_project()):
                    return False
            path = filedialog.askopenfilename(parent=self.root, title="打开平差项目", filetypes=[("平差项目 / JSON", "*.json")])
        if not path:
            return False
        try:
            if Path(path).stat().st_size > 2_000_000:
                raise ValueError("项目文件超过 2 MB，无法载入。")
            doc = json.loads(Path(path).read_text(encoding="utf-8-sig"))
            if not isinstance(doc, dict) or doc.get("format") != "survey-adjustment-project" or doc.get("version") != 1:
                raise ValueError("这不是支持的平差项目文件。结果 JSON 不能作为项目打开。")
            if doc.get("model") not in MODEL_NAMES or not isinstance(doc.get("data"), dict):
                raise ValueError("模型或数据字段无效。")
            data = doc["data"]
            if not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
                raise ValueError("项目中的输入字段必须是文本。")
            for key in MODEL_FIELDS[doc["model"]]:
                if key not in data:
                    raise ValueError(f"项目缺少 {key} 字段。")
            if data.get("weight_mode") not in ("等权 P = I", "对角权", "完整权阵") or data.get("precision") not in ("先验", "后验"):
                raise ValueError("项目的权阵模式或精度基准无效。")
            self.drafts[self.model] = self.snapshot()
            self.model = doc["model"]
            self.load_fields(data)
            self.clear_results()
            self.project_path, self.dirty = str(path), False
            self.notebook.select(self.input_tab)
            self.status.set("项目已打开 · " + str(path))
            return True
        except (OSError, ValueError) as exc:
            messagebox.showerror("打开失败", str(exc), parent=self.root)
            return False

    def export_result(self, fmt, path=None):
        r = self.result
        if r is None:
            return False
        if path is None:
            path = filedialog.asksaveasfilename(parent=self.root, title="导出平差结果", defaultextension="." + fmt,
                                               filetypes=[(fmt.upper(), "*." + fmt)], initialfile="平差结果." + fmt)
        if not path:
            return False
        try:
            if fmt == "txt":
                Path(path).write_text(make_report(r, self.title.get(), int(self.digits.get())), encoding="utf-8-sig")
            elif fmt == "json":
                data = {"format": "survey-adjustment-result", "version": 1, "title": self.title.get(),
                        "input": self.snapshot(), "result": r.to_dict()}
                Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
            elif fmt == "csv":
                with Path(path).open("w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(["模型", MODEL_NAMES[r.model]])
                    writer.writerow(["自由度", r.dof, "vTPv", r.weighted_sum, "后验单位权中误差", r.posterior_sigma])
                    writer.writerow(["中误差精度基准", r.precision_source, "采用sigma0", r.precision_sigma])
                    writer.writerow([])
                    writer.writerow(["序号", "观测值L", "改正数v", "平差值Lhat", "平差值中误差"])
                    mL, mx = r.std(r.q_adjusted), r.std(r.qxx)
                    at = lambda a, i: float(a[i]) if a is not None else ""
                    for i in range(r.n):
                        writer.writerow([i+1, at(r.observed,i), at(r.v,i), at(r.adjusted,i), at(mL,i)])
                    if r.x is not None:
                        writer.writerow([])
                        writer.writerow(["序号", "参数解x", "初值X0", "参数平差值Xhat", "参数中误差"])
                        for i in range(r.t):
                            writer.writerow([i+1, at(r.x,i), at(r.x0,i), at(r.parameters,i), at(mx,i)])
            else:
                raise ValueError("未知导出格式。")
            self.status.set("结果已导出 · " + str(path))
            return True
        except (OSError, ValueError) as exc:
            messagebox.showerror("导出失败", str(exc), parent=self.root)
            return False

    def copy_report(self):
        if self.result is not None:
            self.root.clipboard_clear()
            self.root.clipboard_append(make_report(self.result, self.title.get(), int(self.digits.get())))
            self.status.set("报告已复制到剪贴板。")

    def close(self):
        if self.network.dirty:
            answer=messagebox.askyesnocancel("保存控制网","关闭前是否保存当前控制网？",parent=self.root)
            if answer is None or (answer and not self.network.save_project()):return
        if self.dirty:
            answer = messagebox.askyesnocancel("保存当前输入", "关闭之前，是否保存当前模型的输入？其他模型草稿只在本次运行中保留。", parent=self.root)
            if answer is None or (answer and not self.save_project(matrix_only=True)):
                return
        self.root.destroy()


HELP = """控制网画布（v0.2 新增）

首页可布设水准、导线、GNSS、测边、测角、边角、坐标观测网。选择布点工具后单击空白处添加点，右侧修改近似坐标和固定分量；再选择观测类型并点击相关点。
高差、距离、方位角、GNSS 基线依次选起点和终点；水平角依次选后视点、测站、前视点；坐标观测只选一个点。双击观测表录入实测值及标准差。
长度及坐标单位 m；角度值为十进制度或度分秒 123:45:56.7，角度标准差为角秒。GNSS 与坐标观测可以录入相关协方差阵（m²）。
设计模式按输入标准差自动计算先验精度；实测模式要求每条启用观测有实测值，并自动线性化、迭代。
右侧 n 按标量观测分量计数，三维基线计 3；u 为未固定参数数，c 为显式独立限制数；t=限制消元后的观测系数秩，r=n−t，基准亏损=u−c−t。
限制可写 P1.H:1 P2.H:1 = 203，针对坐标本身；程序自动化为改正数限制。固定坐标是精确值，有误差的控制坐标应设为坐标观测。
下方自动矩阵页可查看和导出 B、P、N 及协因数；精度页有点位中误差、相对精度和放大显示的 1σ 椭圆。设计时不把模拟值的零残差视为零误差。
平面网 X 北 / Y 东，H 为高程；GNSS 坐标、三维基线和协方差须在同一 XYZ 直角框架，可为地心框架。GNSS 画布及椭圆显示 XY 投影，另提供三维点位中误差，不自动转为 ENU 或进行投影转换。不同观测块按不相关处理。
控制网保存为 .net.json，矩阵工作台保存为 .sap.json。详细说明见程序目录 README.md。

矩阵工作台：先选模型，再录入矩阵

01  条件平差：A v + w = 0
A 为 r×n，w 为 r 个数。条件相互独立时，自由度 f = r。
w 是按当前观测值代入条件方程得到的闭合差。改正数符号为 v = 平差值 − 观测值。

02  附有参数的条件平差：A v + B x + w = 0
A 为 r×n，B 为 r×t，w 为 r 个数。B 必须列满秩，消去参数后的条件必须独立。自由度 f = r − t。
例如同一距离的重复观测：A = I，B = −1，w = L − X₀，则 x 为距离改正数。

03  间接平差：v = B x − l
B 为 n×t，l 为 n 个数。一般要求 B 列满秩，自由度 f = n − t。
线性化时应先选 X₀，计算 l = L − f(X₀) 和雅可比矩阵 B，再在本程序求 x。

04  附有限制条件的间接平差：v = B x − l，C x + d = 0
C 为 c×t，d 为 c 个数，限制必须独立且视为精确值。自由度 f = n − t + c。
B 允许秩亏，但限制加入后自由参数必须能唯一确定。本程序通过限制的零空间消元求解。
若限制是 X₁ + X₂ = 203，初值为 100、100，则针对改正数的限制是 x₁ + x₂ − 3 = 0，录入 d = −3。

录入与权阵
从 Excel 复制后直接粘贴。空格、Tab、逗号分列；换行、分号分行；支持 1e-3 科学计数法和 # 行尾注释。不要留空单元格。
程序仅解析数值，不执行表达式；不支持直接输入 1/3、三角函数或度分秒字符串。
等权：P = I。对角权：填写 n 个正权。完整权阵：填写 n×n 对称正定矩阵。
P 是权阵，Q = P⁻¹；Cov(L) = σ₀² Q。若手中是协因数阵 Q，须先转换为 P。
不同观测类型可使用不同物理单位，但系数和权阵必须与相应单位一致；同一量的单位应统一。程序不自动换算角度或长度。

观测值、参数值与精度
L 可选，仅用于输出 L̂ = L + v；填写 L 不会自动建立观测方程。l 与 L 可能不同，请按所选方程录入。
X₀ 可选。只有 x 表示改正数时才填写 X₀，程序输出 X̂ = X₀ + x；若 x 已为参数本身，请留空 X₀，直接读取参数解 x。
默认采用后验单位权中误差 σ̂₀ = sqrt(vᵀPv / f)。也可选择先验精度，填写已知的先验 σ₀。
所有中误差均等于所选 σ₀ 乘以协因数对角元的平方根。自由度为 0 时不提供后验中误差；可使用先验精度。
导出的 JSON 含完整协因数阵；Cov = 所选 σ₀² × Q。TXT 对大矩阵可能折叠显示。报告显示的有效数字只影响显示与 TXT，不改变内部精度。

保存、导出与范围
保存项目为 .sap.json，可再次打开继续计算；保存的是当前模型。切换模型会在本次运行期间保留各模型草稿。
CSV 用于 Excel 核对结果；TXT 包含计算报告；结果 JSON 包含输入、结果及完整协因数阵。
本程序处理线性或已经线性化的矩阵模型，不自动列测量方程、不做非线性迭代；不提供秩亏自由网的任意广义逆解。
当前每个矩阵维度上限为 500，采用稠密矩阵，适合教学与中小型计算。
快捷键：Ctrl+Enter 计算；Ctrl+S 保存；Ctrl+O 打开。

计算参考
Ohio State University, Notes on Adjustment Computations (2019), chapters 3–5 and 9:
https://earthsciences.osu.edu/sites/default/files/OSU_Adjustment_Notes_Part_1_0.pdf
GNU Gama, Network adjustment with gama-local:
https://www.gnu.org/s/gama/manual/html_node/Network-adjustment-with-gama_002dlocal.html
本程序采用上文所列符号约定，参考资料中的 A、B 命名与残差符号可能不同。
"""


def main():
    if "--self-test" in sys.argv:
        from gui_check import run
        output = sys.argv[sys.argv.index("--self-test") + 1]
        run(output)
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    AdjustmentApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
