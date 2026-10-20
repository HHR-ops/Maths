"""Interactive Tk canvas and automatic-model workspace; all computation is offline."""
from __future__ import annotations

from copy import deepcopy
import csv
import json
import math
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np

from adjustment import AdjustmentError, MODEL_NAMES, format_array
from network import (Network, FAMILIES, KINDS, ARCSEC, ANGLES, finite, linearize,
                     adjust_network, automatic_matrices, example_network, network_report, parse_constraints)

from ui_theme import FONT,INK,MUTED,GREEN,BG,EDGE,PANEL,SOFT,WARNING
COLORS={"height":"#6993a0","distance":"#8095a5","angle":"#b39a73","azimuth":"#9c8cab",
        "gnss":"#8791b6","coordinate":"#6c9d8f"}
TOOLS={"select":"选择 / 移动","point":"布点","height":"高差","distance":"距离",
       "angle":"水平角","azimuth":"方位角","gnss":"GNSS基线","coordinate":"坐标观测","delete":"删除"}


class NetworkWorkspace(ttk.Frame):
    def __init__(self,parent,on_matrix=None):
        super().__init__(parent,padding=0)
        self.ui_scale=max(1.,float(self.tk.call("tk","scaling"))/(96/72))
        self.net=example_network()
        self.on_matrix=on_matrix
        self.solution=None; self.compiled=None; self.matrices={}
        self.dirty=False; self.project_path=None
        self.pending=[]; self.tool="select"; self.selection=None; self.drag=None; self.pan=None
        self.origin=[400.,300.]; self.zoom=3.; self.refresh_job=None
        self.undo_stack=[]; self.redo_stack=[]
        self.family=tk.StringVar(value=self.net.family)
        self.project_name=tk.StringVar(value=self.net.name)
        self.method=tk.StringVar(value=MODEL_NAMES[self.net.method])
        self.mode=tk.StringVar(value="布网设计")
        self.precision=tk.StringVar(value="先验")
        self.show_ellipses=tk.BooleanVar(value=True)
        self.show_labels=tk.BooleanVar(value=True)
        self.notice=tk.StringVar(value="")
        self.stat_vars={key:tk.StringVar(value="—") for key in ("n","t","r","parameters","constraints","defect")}
        self.matrix_choice=tk.StringVar()
        self.build()
        self.project_name.trace_add("write",self.name_changed)
        self.set_tool("select")
        self.after(80,self.fit_view)
        self.request_refresh()

    def build(self):
        u=lambda n:round(n*self.ui_scale)
        top=ttk.Frame(self); top.pack(fill="x",pady=(0,u(10)))
        ttk.Label(top,text="项目",style="Muted.TLabel").pack(side="left",padx=(0,u(8)))
        ttk.Entry(top,textvariable=self.project_name,width=16).pack(side="left",padx=(0,u(18)))
        ttk.Label(top,text="网型",style="Muted.TLabel").pack(side="left",padx=(0,u(8)))
        combo=ttk.Combobox(top,textvariable=self.family,values=FAMILIES,state="readonly",width=10)
        combo.pack(side="left"); combo.bind("<<ComboboxSelected>>",self.family_changed)
        ttk.Label(top,text="方法",style="Muted.TLabel").pack(side="left",padx=(u(18),u(8)))
        methods=ttk.Combobox(top,textvariable=self.method,values=list(MODEL_NAMES.values()),state="readonly",width=24)
        methods.pack(side="left"); methods.bind("<<ComboboxSelected>>",self.options_changed)
        for text,action in [("新建空网",self.new_network),("示例网",self.load_example)]:
            ttk.Button(top,text=text,style="Ghost.TButton",command=action).pack(side="right",padx=(u(5),0))
        options=ttk.Frame(self); options.pack(fill="x",pady=(0,u(14)))
        ttk.Label(options,text="模式",style="Muted.TLabel").pack(side="left",padx=(0,u(8)))
        mode=ttk.Combobox(options,textvariable=self.mode,values=["布网设计","实测平差"],state="readonly",width=10)
        mode.pack(side="left"); mode.bind("<<ComboboxSelected>>",self.options_changed)
        ttk.Label(options,text="精度基准",style="Muted.TLabel").pack(side="left",padx=(u(18),u(8)))
        self.precision_box=ttk.Combobox(options,textvariable=self.precision,values=["先验","后验"],state="disabled",width=6)
        self.precision_box.pack(side="left"); self.precision_box.bind("<<ComboboxSelected>>",self.options_changed)
        ttk.Button(options,text="限制条件",style="Ghost.TButton",command=self.constraints_dialog).pack(side="left",padx=(u(16),u(4)))
        ttk.Button(options,text="提取矩阵",style="Ghost.TButton",command=self.send_matrix).pack(side="left",padx=u(4))
        ttk.Checkbutton(options,text="图示精度",variable=self.show_ellipses,command=self.redraw).pack(side="right")
        ttk.Checkbutton(options,text="观测标注",variable=self.show_labels,command=self.redraw).pack(side="right",padx=(0,10))
        body=ttk.Frame(self); body.pack(fill="both",expand=True)
        body.columnconfigure(0,weight=1);body.columnconfigure(1,weight=0,minsize=u(278));body.rowconfigure(0,weight=1)
        left=ttk.Frame(body);left.grid(row=0,column=0,sticky="nsew")
        right=ttk.Frame(body,width=u(278),padding=(u(20),0,0,0));right.grid(row=0,column=1,sticky="nsew")
        right.pack_propagate(False)
        self.tools=ttk.Frame(left); self.tools.pack(fill="x",pady=(0,u(6))); self.tool_buttons={}
        self.rebuild_tools()
        self.tool_hint=tk.StringVar()
        hint=ttk.Label(left,textvariable=self.tool_hint,foreground=MUTED,font=(FONT,8))
        hint.pack(fill="x",pady=(0,u(8)))
        hint.bind("<Configure>",lambda e:hint.configure(wraplength=max(100,e.width)))
        panes=ttk.Panedwindow(left,orient="vertical"); panes.pack(fill="both",expand=True)
        drawing=ttk.Frame(panes); panes.add(drawing,weight=3)
        footer=ttk.Frame(drawing);footer.pack(side="bottom",fill="x",pady=(u(4),0))
        self.viewport_info=tk.StringVar(value="")
        self.precision_scale=tk.StringVar(value="")
        ttk.Label(footer,textvariable=self.viewport_info,font=(FONT,8),foreground=MUTED).pack(side="left")
        ttk.Label(footer,textvariable=self.precision_scale,font=(FONT,8),foreground=GREEN).pack(side="right")
        self.canvas=tk.Canvas(drawing,bg=BG,highlightthickness=1,highlightbackground=EDGE,height=u(310))
        self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<Configure>",lambda _e:self.redraw())
        self.canvas.bind("<Button-1>",self.on_click)
        self.canvas.bind("<B1-Motion>",self.on_drag)
        self.canvas.bind("<ButtonRelease-1>",self.on_release)
        self.canvas.bind("<Double-Button-1>",self.double_click)
        self.canvas.bind("<MouseWheel>",self.on_zoom)
        for b in (2,3):
            self.canvas.bind(f"<Button-{b}>",self.start_pan)
            self.canvas.bind(f"<B{b}-Motion>",self.do_pan)
        self.canvas.bind("<Escape>",lambda _e:self.set_tool("select"))
        self.canvas.bind("<Delete>",lambda _e:self.delete_selected())
        self.canvas.bind("<Control-z>",lambda _e:self.undo())
        self.canvas.bind("<Control-y>",lambda _e:self.redo())
        self.canvas.bind("<Control-s>",lambda _e:(self.save_project(),"break")[1])
        bottom=ttk.Frame(panes,padding=(0,u(10),0,0)); panes.add(bottom,weight=2)
        self.outputs=ttk.Notebook(bottom); self.outputs.pack(fill="both",expand=True)
        obs_frame=ttk.Frame(self.outputs); matrix_frame=ttk.Frame(self.outputs); precision_frame=ttk.Frame(self.outputs); point_frame=ttk.Frame(self.outputs)
        for frame,label in [(obs_frame,"观测数据"),(matrix_frame,"自动矩阵"),(precision_frame,"精度评估"),(point_frame,"点坐标")]:self.outputs.add(frame,text=label)
        self.obs_tree=self.make_tree(obs_frame,["编号","类型","点序 / 端点","观测值","标准差 / 协方差","状态"])
        self.obs_tree.bind("<<TreeviewSelect>>",self.tree_selected)
        self.obs_tree.bind("<Double-Button-1>",lambda _e:self.edit_observation())
        self.point_tree=self.make_tree(point_frame,["点名","X（北）","Y（东）","H / Z","固定分量"])
        self.point_tree.bind("<<TreeviewSelect>>",self.point_tree_selected)
        mb=ttk.Frame(matrix_frame,padding=6); mb.pack(fill="x")
        self.matrix_combo=ttk.Combobox(mb,textvariable=self.matrix_choice,values=[],state="readonly",width=36)
        self.matrix_combo.pack(side="left",fill="x",expand=True)
        self.matrix_combo.bind("<<ComboboxSelected>>",lambda _e:self.show_matrix())
        ttk.Button(mb,text="导出矩阵 CSV",command=self.export_matrix).pack(side="left",padx=(8,0))
        self.matrix_text=self.make_text(matrix_frame)
        self.precision_text=self.make_text(precision_frame)
        title=ttk.Frame(right);title.pack(fill="x",pady=(u(4),u(13)))
        ttk.Label(title,text="网络概况",font=(FONT,10,"bold")).pack(side="left")
        self.readiness=tk.StringVar(value="自动更新")
        self.readiness_label=ttk.Label(title,textvariable=self.readiness,font=(FONT,8),foreground=MUTED)
        self.readiness_label.pack(side="right")
        counts=ttk.Frame(right);counts.pack(fill="x",pady=(0,u(12)))
        self.stat_value_labels={}
        for i,(key,label) in enumerate([("n","总观测 n"),("t","必要 t"),("r","多余 r")]):
            cell=ttk.Frame(counts);cell.grid(row=0,column=i,sticky="ew",padx=(0,u(9)))
            ttk.Label(cell,text=label,font=(FONT,8),foreground=MUTED).pack(anchor="w")
            value=ttk.Label(cell,textvariable=self.stat_vars[key],font=(FONT,19),foreground=INK)
            value.pack(anchor="w",pady=(u(4),0));self.stat_value_labels[key]=value
            counts.columnconfigure(i,weight=1,uniform="summary")
        for key,label in [("parameters","待估参数 u"),("constraints","独立限制 c"),("defect","基准 / 几何亏损")]:
            row=ttk.Frame(right);row.pack(fill="x",pady=u(3))
            ttk.Label(row,text=label,font=(FONT,9),foreground=MUTED).pack(side="left")
            value=ttk.Label(row,textvariable=self.stat_vars[key],font=(FONT,10),foreground=INK)
            value.pack(side="right");self.stat_value_labels[key]=value
        ttk.Label(right,text="n 按标量计数；r = n − t。",font=(FONT,8),foreground="#96a1aa").pack(anchor="w",pady=(u(9),u(16)))
        ttk.Separator(right).pack(fill="x",pady=(0,u(16)))
        actions=ttk.Frame(right);actions.pack(side="bottom",fill="x",pady=(u(12),0))
        ttk.Separator(actions).pack(fill="x",pady=(0,u(10)))
        ttk.Button(actions,text="导出结果与报告",command=self.export_dialog).pack(fill="x")
        self.inspector=ttk.Frame(right); self.inspector.pack(fill="both",expand=True)
        self.inspect()

    def make_tree(self,parent,columns):
        tree=ttk.Treeview(parent,columns=columns,show="headings",height=5)
        vs=ttk.Scrollbar(parent,orient="vertical",command=tree.yview); hs=ttk.Scrollbar(parent,orient="horizontal",command=tree.xview)
        tree.config(yscrollcommand=vs.set,xscrollcommand=hs.set)
        vs.pack(side="right",fill="y"); hs.pack(side="bottom",fill="x"); tree.pack(fill="both",expand=True)
        widths=[64,92,155,180,145,55] if len(columns)==6 else [64,145,145,145,100]
        for i,c in enumerate(columns):
            tree.heading(c,text=c,anchor="w")
            tree.column(c,width=round(widths[i]*self.ui_scale),minwidth=round((44 if i==0 else 65)*self.ui_scale),anchor="e" if len(columns)==5 and i in (1,2,3) else "w")
        return tree

    def name_changed(self,*_args):
        self.net.name=self.project_name.get(); self.dirty=True

    def make_text(self,parent):
        frame=ttk.Frame(parent); frame.pack(fill="both",expand=True)
        text=tk.Text(frame,font=("Consolas",10),bg="white",fg=INK,wrap="none",relief="flat",padx=12,pady=10,state="disabled",height=7)
        vs=ttk.Scrollbar(frame,orient="vertical",command=text.yview); hs=ttk.Scrollbar(frame,orient="horizontal",command=text.xview)
        text.config(yscrollcommand=vs.set,xscrollcommand=hs.set)
        vs.pack(side="right",fill="y"); hs.pack(side="bottom",fill="x"); text.pack(fill="both",expand=True)
        return text

    @staticmethod
    def set_text(widget,text):
        widget.config(state="normal"); widget.delete("1.0","end"); widget.insert("1.0",text); widget.config(state="disabled")

    def rebuild_tools(self):
        for child in self.tools.winfo_children():child.destroy()
        self.tool_buttons={}
        for key in ["select","point"]+self.net.allowed_kinds+["delete"]:
            button=ttk.Button(self.tools,text=TOOLS[key],style="Tool.TButton",command=lambda k=key:self.set_tool(k))
            self.tool_buttons[key]=button
        self.toolbar_extras=[ttk.Button(self.tools,text="撤销",style="Tool.TButton",command=self.undo),ttk.Button(self.tools,text="重做",style="Tool.TButton",command=self.redo)]
        self.fit_button=ttk.Button(self.tools,text="适合窗口",style="Tool.TButton",command=self.fit_view)
        self.tools.pack_propagate(False)
        self._toolbar_layout_signature=None
        self.tools.bind("<Configure>",self.layout_tools)
        self.layout_tools()

    def layout_tools(self,_event=None):
        main_items=list(self.tool_buttons.values())
        items=main_items+self.toolbar_extras
        available=max(100,self.tools.winfo_width())
        signature=(available,tuple((item.winfo_reqwidth(),item.winfo_reqheight()) for item in items),self.fit_button.winfo_reqwidth())
        if signature==self._toolbar_layout_signature:return
        self._toolbar_layout_signature=signature
        gap=max(2,round(3*self.ui_scale))
        height=max(item.winfo_reqheight() for item in items)
        x=y=0
        for item in main_items:
            width=item.winfo_reqwidth()
            if x and x+width>available:x=0;y+=height+gap
            item.place(x=x,y=y,width=min(width,available),height=height);x+=width+gap
        actions_width=sum(item.winfo_reqwidth()+gap for item in self.toolbar_extras)+self.fit_button.winfo_reqwidth()
        if x+actions_width>available:x=0;y+=height+gap
        for item in self.toolbar_extras:
            width=item.winfo_reqwidth()
            item.place(x=x,y=y,width=min(width,available),height=height);x+=width+gap
        width=self.fit_button.winfo_reqwidth()
        if x+width>available:y+=height+gap
        self.fit_button.place(x=max(0,available-width),y=y,width=min(width,available),height=height)
        self.tools.configure(height=y+height)

    def set_tool(self,tool):
        self.tool=tool; self.pending=[]
        for key,button in self.tool_buttons.items():button.configure(style="ToolActive.TButton" if key==tool else "Tool.TButton")
        self.layout_tools()
        hints={"select":"拖动点调整近似坐标；滚轮缩放；右键拖动平移；双击观测编辑实测值。",
               "point":"单击空白处布设点。水准网的 X/Y 仅作图上位置，H 才参与计算。",
               "angle":"依次点击：后视点 → 测站 → 前视点；角度按顺时针方位差计算。",
               "coordinate":"点击一个点添加坐标观测；它有标准差，与精确固定坐标不同。",
               "delete":"点击点或观测删除；删点会一并删除其观测和限制。"}
        self.tool_hint.set(hints.get(tool,"依次点击起点 → 终点；观测值和标准差可在下方观测表中双击编辑。"))
        if hasattr(self,"canvas"):self.canvas.config(cursor="crosshair" if tool!="select" else "arrow"); self.redraw()

    def checkpoint(self):
        self.undo_stack.append(deepcopy(self.net)); self.undo_stack=self.undo_stack[-40:]; self.redo_stack=[]

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(deepcopy(self.net)); self.restore(self.undo_stack.pop(),dirty=True)

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(deepcopy(self.net)); self.restore(self.redo_stack.pop(),dirty=True)

    def changed(self):
        self.dirty=True; self.solution=None; self.compiled=None; self.matrices={}
        self.set_text(self.precision_text,"输入已改变，正在更新矩阵与精度…")
        self.set_text(self.matrix_text,"输入已改变，正在更新…")
        self.request_refresh(); self.redraw()

    def request_refresh(self):
        if self.refresh_job:self.after_cancel(self.refresh_job)
        self.refresh_job=self.after(180,self.update_analysis)

    def update_analysis(self,show_error=False):
        self.refresh_job=None
        self.solution=None; self.compiled=None; self.matrices={}
        try:
            self.net.method=next(k for k,v in MODEL_NAMES.items() if v==self.method.get())
            design=self.mode.get()=="布网设计"
            self.compiled=linearize(self.net,design=design)
            for key,var in self.stat_vars.items():var.set(str(self.compiled.stats[key]))
            defect=self.compiled.stats["defect"]
            self.stat_value_labels["defect"].configure(foreground=WARNING if defect else INK)
            self.readiness.set("待补充基准" if defect else ("网形可解算" if self.compiled.stats["n"] else "等待布网"))
            self.readiness_label.configure(foreground=WARNING if defect else GREEN)
            self.matrices=automatic_matrices(self.compiled)
            self.fill_tables()
            if not self.compiled.stats["n"]:
                self.notice.set("先布点并添加观测；固定坐标在右侧点属性中设置。")
                self.set_text(self.precision_text,"尚无观测。添加观测后自动更新精度。")
            else:
                self.solution=adjust_network(self.net,design,"prior" if self.precision.get()=="先验" else "posterior")
                self.compiled=self.solution.model; self.matrices=self.solution.matrices
                self.set_text(self.precision_text,self.precision_report())
                self.notice.set(("设计精度已更新：采用输入标准差，σ₀=1。" if design else f"实测平差完成，迭代 {self.solution.iterations} 次。")+" 矩阵和协因数已自动生成；精度图示为放大后的 1σ。")
            self.refresh_matrix_choices(); self.redraw()
            return self.solution is not None
        except (AdjustmentError,ValueError,np.linalg.LinAlgError) as exc:
            self.solution=None
            if self.compiled is not None:
                self.refresh_matrix_choices()
            else:
                for var in self.stat_vars.values():var.set("—")
                self.set_text(self.matrix_text,"模型输入待检查："+str(exc))
            self.set_text(self.precision_text,str(exc))
            if self.compiled is None:self.readiness.set("检查输入");self.readiness_label.configure(foreground=WARNING)
            self.notice.set("待完善 · "+str(exc)); self.redraw()
            if show_error:messagebox.showerror("控制网计算",str(exc),parent=self)
            return False

    def calculate(self):
        if self.refresh_job:self.after_cancel(self.refresh_job); self.refresh_job=None
        return self.update_analysis(show_error=True)

    def precision_report(self):
        s=self.solution; r=s.result
        lines=["布网设计 / 先验精度" if s.design else "实测平差 / "+self.precision.get()+"精度",
               "坐标、长度中误差：米。椭圆长短半轴为 1σ；不是联合 68% 置信区间。",
               "固定分量的中误差为 0；精度数值来自完整协因数阵。",""]
        if self.net.family=="GNSS网":lines.append("GNSS 精度在输入 XYZ 框架内：m3D 为三维点位中误差，椭圆为 XY 投影（轴向从 +X 向 +Y），未转换为当地 ENU。")
        if not s.design:lines.append(f"后验单位权中误差：{r.posterior_sigma if r.posterior_sigma is not None else '不可估计（r=0）'}")
        for p in s.point_precision:
            line=p["point"]+"   "+"   ".join(f"m{a}={p['m'+a]:.6g}" for a in self.net.axes)
            if "m3D" in p:line+=f"   三维点位中误差={p['m3D']:.6g}"
            if "mp" in p:line+=f"   {'XY投影中误差' if self.net.family=='GNSS网' else '点位中误差'}={p['mp']:.6g}   椭圆 a/b={p['major']:.6g}/{p['minor']:.6g}   轴向={p['azimuth']:.3f}°"
            lines.append(line)
        if not s.point_precision:lines.append("当前后验精度不可估计，可选择先验基准。")
        lines.extend(["","相对精度（考虑参数间相关性）"])
        for p in s.relative_precision:
            lines.append(f"{p['observation']}   {p['quantity']}中误差={p['sigma']:.6g}"+(f"   相对精度≈1/{p['relative_denominator']:.0f}" if p.get("relative_denominator") else ""))
        if not s.design and r.precision_sigma is not None:
            lines.extend(["","残差诊断（相关观测的单分量指标仅供复核，不自动判定粗差）"])
            std=r.std(r.qvv)
            for i,label in enumerate(s.model.labels):
                residual=r.v[i]/ARCSEC if s.model.angular[i] else r.v[i]
                z=abs(r.v[i])/std[i] if std[i]>1e-15 else None
                lines.append(f"{label}   v={residual:.8g} {'角秒' if s.model.angular[i] else 'm'}   |v|/m_v={z:.4g}" if z is not None else f"{label}   v={residual:.8g}，该分量无残差自由度")
        return "\n".join(lines)

    def refresh_matrix_choices(self):
        names=list(self.matrices); self.matrix_combo.config(values=names)
        if self.matrix_choice.get() not in names:self.matrix_choice.set(names[0] if names else "")
        self.show_matrix()

    def show_matrix(self):
        a=self.matrices.get(self.matrix_choice.get())
        if a is None:return
        a=np.asarray(a); shape=" × ".join(str(i) for i in a.shape)
        order="参数："+", ".join(p+"."+axis for p,axis in self.compiled.keys) if self.compiled else ""
        labels="观测："+", ".join(self.compiled.labels) if self.compiled else ""
        self.set_text(self.matrix_text,self.matrix_choice.get()+f"    [{shape}]\n"+order+"\n"+labels+"\n\n"+format_array(a,10,35)+"\n\n大矩阵可能折叠显示；导出 CSV / JSON 可获得完整矩阵。")

    def fill_tables(self):
        self.point_tree.heading("X（北）",text="X (m)" if self.net.family=="GNSS网" else "X（北）")
        self.point_tree.heading("Y（东）",text="Y (m)" if self.net.family=="GNSS网" else "Y（东）")
        self.obs_tree.delete(*self.obs_tree.get_children())
        for obs in self.net.observations:
            raw=obs["value"]
            value="未录入（设计观测）" if raw is None or raw=="" else str(raw)
            sigma="相关协方差阵" if obs.get("covariance") is not None else str(obs["sigma"])+( " ″" if obs["kind"] in ANGLES else " m")
            self.obs_tree.insert("","end",iid=obs["id"],values=(obs["id"],KINDS[obs["kind"]]," → ".join(obs["points"]),value,sigma,"启用" if obs.get("enabled",True) else "停用"))
        self.point_tree.delete(*self.point_tree.get_children())
        for name,p in self.net.points.items():
            self.point_tree.insert("","end",iid=name,values=(name,f"{p['X']:.5f}",f"{p['Y']:.5f}",f"{p['H'] if self.net.axes==('H',) else p['Z']:.5f}",",".join(a for a in self.net.axes if a in p["fixed"]) or "待估"))

    def world(self,x,y):return ((self.origin[1]-y)/self.zoom,(x-self.origin[0])/self.zoom)
    def screen(self,X,Y):return (self.origin[0]+Y*self.zoom,self.origin[1]-X*self.zoom)

    def fit_view(self):
        self.update_idletasks(); w=max(self.canvas.winfo_width(),300); h=max(self.canvas.winfo_height(),200)
        if self.net.points:
            xs=[p["X"] for p in self.net.points.values()]; ys=[p["Y"] for p in self.net.points.values()]
            self.zoom=max(.0001,min((w-150)/max(max(ys)-min(ys),20),(h-120)/max(max(xs)-min(xs),20)))
            self.origin=[w/2-(max(ys)+min(ys))/2*self.zoom,h/2+(max(xs)+min(xs))/2*self.zoom]
        else:self.zoom=3.; self.origin=[w/2,h/2]
        self.redraw()

    def redraw(self):
        if not hasattr(self,"canvas"):return
        c=self.canvas; c.delete("all"); w,h=c.winfo_width(),c.winfo_height()
        if w<2 or h<2:return
        spacing=60/self.zoom; power=10**math.floor(math.log10(max(spacing,1e-12)))
        step=next((n*power for n in (1,2,5,10) if n*power>=spacing),10*power)
        self.viewport_info.set(("X ↑  Y →" if self.net.family=="GNSS网" else "X 北 ↑  Y 东 →")+f"  ·  网格 {step:g} m")
        self.precision_scale.set("")
        px=step*self.zoom
        for x in np.arange(self.origin[0]%px,w,px):c.create_line(x,0,x,h,fill="#f0f3f5",width=1)
        for y in np.arange(self.origin[1]%px,h,px):c.create_line(0,y,w,y,fill="#f0f3f5",width=1)
        angle_layers={}
        connected={frozenset(o["points"]) for o in self.net.observations if o.get("enabled",True) and o["kind"] in ("distance","height","gnss")}
        for obs in self.net.observations:
            ids=obs["points"]; color=COLORS[obs["kind"]] if obs.get("enabled",True) else "#bdc8cf"
            width=(1.7 if self.selection==("observation",obs["id"]) else 1.05)*self.ui_scale
            coords=[self.screen(self.net.points[p]["X"],self.net.points[p]["Y"]) for p in ids]
            tags=("obs", "obs:"+obs["id"])
            if obs["kind"]=="coordinate":
                x,y=coords[0]; c.create_oval(x-15,y-15,x+15,y+15,outline=color,width=width,dash=(3,3),tags=tags)
                lx,ly=x+18,y+18
            elif obs["kind"]=="angle":
                back,station,fore=ids
                for target,target_id in [(coords[0],back),(coords[2],fore)]:
                    if frozenset((station,target_id)) not in connected:
                        c.create_line(*coords[1],*target,fill="#d5c6ac",width=1,dash=(3,7),tags=tags)
                p=self.net.points; ab=math.atan2(p[back]["Y"]-p[station]["Y"],p[back]["X"]-p[station]["X"])
                af=math.atan2(p[fore]["Y"]-p[station]["Y"],p[fore]["X"]-p[station]["X"])
                beta=(af-ab)%(2*math.pi); layer=angle_layers.get(station,0);angle_layers[station]=layer+1
                radius=22+layer*17; sx,sy=coords[1]
                c.create_arc(sx-radius,sy-radius,sx+radius,sy+radius,start=90-math.degrees(ab),extent=-math.degrees(beta),style="arc",outline=color,width=width,tags=tags)
                mid=ab+beta/2;lx=sx+(radius+24)*math.sin(mid);ly=sy-(radius+24)*math.cos(mid)
            else:
                c.create_line(*coords[0],*coords[1],fill=color,width=width,arrow="last" if obs["kind"] in ("height","gnss","azimuth") else "none",tags=tags)
                lx,ly=(coords[0][0]+coords[1][0])/2,(coords[0][1]+coords[1][1])/2
                vx,vy=coords[1][0]-coords[0][0],coords[1][1]-coords[0][1];length=math.hypot(vx,vy)
                if length:lx+=-vy/length*12;ly+=vx/length*12
            if self.show_labels.get():c.create_text(lx,ly-8,text=obs["id"]+" · "+KINDS[obs["kind"]],font=(FONT,8),fill=color,tags=tags)
        for name,p in self.net.points.items():
            x,y=self.screen(p["X"],p["Y"]); tags=("point","point:"+name)
            selected=self.selection==("point",name) or name in self.pending
            color="#e39a40" if name in self.pending else GREEN
            if selected:c.create_oval(x-15,y-15,x+15,y+15,fill="#dff1e9",outline="",tags=tags)
            if all(a in p["fixed"] for a in self.net.axes):c.create_polygon(x,y-8,x-8,y+6,x+8,y+6,fill=color,outline="white",width=1,tags=tags)
            else:c.create_oval(x-6,y-6,x+6,y+6,fill="white",outline=color,width=2,tags=tags)
            c.create_text(x+12,y-12,text=name,font=(FONT,10,"bold"),fill=INK,anchor="w",tags=tags)
        if self.solution and self.show_ellipses.get():self.draw_precision()
        if not self.net.points:c.create_text(w/2,h/2,text="选择“布点”，在画布上单击开始布网",fill=MUTED,font=(FONT,14))

    def draw_precision(self):
        items=self.solution.point_precision
        if not items:return
        maximum=max((p.get("major",p.get("mH",0)) for p in items),default=0)
        if maximum<=0:return
        factor=28/(maximum*self.zoom)
        for p in items:
            point=self.solution.points[p["point"]]; cx,cy=self.screen(point["X"],point["Y"])
            if "major" not in p:
                dh=p.get("mH",0)*factor*self.zoom
                if dh:c=self.canvas; c.create_line(cx+12,cy-dh,cx+12,cy+dh,fill="#27a085",width=2)
                continue
            coords=[]; az=math.radians(p["azimuth"])
            for t in np.linspace(0,2*math.pi,60):
                dx=p["major"]*math.cos(t)*math.cos(az)-p["minor"]*math.sin(t)*math.sin(az)
                dy=p["major"]*math.cos(t)*math.sin(az)+p["minor"]*math.sin(t)*math.cos(az)
                coords.extend((cx+dy*factor*self.zoom,cy-dx*factor*self.zoom))
            self.canvas.create_line(*coords,fill="#27a085",width=1.3)
        self.precision_scale.set(f"1σ 图示  ·  放大 ×{factor:.0f}")

    def hit(self,x,y):
        items=self.canvas.find_overlapping(x-7,y-7,x+7,y+7)
        for prefix,kind in [("point:","point"),("obs:","observation")]:
            for item in reversed(items):
                for tag in self.canvas.gettags(item):
                    if tag.startswith(prefix):return kind,tag[len(prefix):]
        return None

    def on_click(self,event):
        self.canvas.focus_set(); hit=self.hit(event.x,event.y)
        if self.tool=="point":
            if hit and hit[0]=="point":self.selection=hit; self.inspect(); return
            self.checkpoint(); X,Y=self.world(event.x,event.y)
            name=self.net.add_point(X=round(X,4),Y=round(Y,4)); self.selection=("point",name)
            self.changed(); self.inspect(); return
        if self.tool=="delete":
            self.selection=hit; self.delete_selected(); return
        if self.tool=="select":
            self.selection=hit; self.inspect()
            if hit and hit[0]=="point":self.drag=(hit[1],deepcopy(self.net),False)
            self.redraw(); return
        if not hit or hit[0]!="point":return
        point=hit[1]
        if point in self.pending:return
        self.pending.append(point)
        needed=3 if self.tool=="angle" else (1 if self.tool=="coordinate" else 2)
        if len(self.pending)==needed:
            try:
                self.checkpoint(); oid=self.net.add_observation(self.tool,self.pending)
                self.selection=("observation",oid); self.pending=[]; self.changed(); self.inspect()
            except AdjustmentError as exc:
                self.pending=[]; messagebox.showerror("无法添加观测",str(exc),parent=self)
        self.redraw()

    def on_drag(self,event):
        if self.tool=="select" and self.drag:
            name,before,_=self.drag; X,Y=self.world(event.x,event.y)
            # Dragging a fixed point changes its supplied coordinate only on explicit mouse movement.
            self.net.points[name]["X"],self.net.points[name]["Y"]=round(X,4),round(Y,4)
            self.drag=(name,before,True); self.changed()

    def on_release(self,_event):
        if self.drag:
            name,before,moved=self.drag
            if moved:self.undo_stack.append(before); self.undo_stack=self.undo_stack[-40:]; self.redo_stack=[]; self.inspect()
        self.drag=None

    def double_click(self,event):
        hit=self.hit(event.x,event.y)
        if hit:self.selection=hit; self.inspect()
        if hit and hit[0]=="observation":self.edit_observation()

    def on_zoom(self,event):
        X,Y=self.world(event.x,event.y); factor=1.15 if event.delta>0 else 1/1.15
        self.zoom=max(1e-6,min(1e5,self.zoom*factor))
        self.origin=[event.x-Y*self.zoom,event.y+X*self.zoom]; self.redraw(); return "break"

    def start_pan(self,event):self.pan=(event.x,event.y,self.origin.copy())
    def do_pan(self,event):
        if self.pan:self.origin=[self.pan[2][0]+event.x-self.pan[0],self.pan[2][1]+event.y-self.pan[1]]; self.redraw()

    def tree_selected(self,_event):
        selected=self.obs_tree.selection()
        if selected:self.selection=("observation",selected[0]); self.inspect(); self.redraw()

    def point_tree_selected(self,_event):
        selected=self.point_tree.selection()
        if selected:self.selection=("point",selected[0]); self.inspect(); self.redraw()

    def inspect(self):
        for child in self.inspector.winfo_children():child.destroy()
        u=lambda n:round(n*self.ui_scale)
        if self.selection and self.selection[0]=="point" and self.selection[1] in self.net.points:
            name=self.selection[1]; p=self.net.points[name]
            ttk.Label(self.inspector,text="点属性",font=(FONT,10,"bold")).pack(anchor="w")
            ttk.Label(self.inspector,text=name,font=(FONT,14),foreground=INK).pack(anchor="w",pady=(u(9),u(12)))
            self.point_vars={}; self.fixed_vars={}
            for axis in ("X","Y")+(("H",) if self.net.axes==("H",) else (("Z",) if "Z" in self.net.axes else ())):
                line=ttk.Frame(self.inspector); line.pack(fill="x",pady=u(5))
                ttk.Label(line,text=axis+" / m",font=(FONT,9),foreground=MUTED,width=6).pack(side="left")
                v=tk.StringVar(value=f"{p[axis]:.8g}"); self.point_vars[axis]=v
                entry=ttk.Entry(line,textvariable=v,width=14); entry.pack(side="left",fill="x",expand=True)
                entry.bind("<Return>",lambda _e:self.apply_point())
                if axis in self.net.axes:
                    fixed=tk.BooleanVar(value=axis in p["fixed"]); self.fixed_vars[axis]=fixed
                    ttk.Checkbutton(line,text="固定",variable=fixed,command=self.apply_point).pack(side="left",padx=(5,0))
            actions=ttk.Frame(self.inspector);actions.pack(fill="x",pady=(u(13),u(10)))
            ttk.Button(actions,text="应用修改",command=self.apply_point).pack(side="left",fill="x",expand=True)
            ttk.Button(actions,text="删除点",style="Danger.TButton",command=self.delete_selected).pack(side="right",padx=(u(5),0))
            ttk.Label(self.inspector,text="固定分量视为精确值。\n带误差的控制坐标请添加坐标观测。",
                      foreground=MUTED,wraplength=u(240),font=(FONT,8)).pack(fill="x",pady=u(5))
        elif self.selection and self.selection[0]=="observation":
            obs=next((o for o in self.net.observations if o["id"]==self.selection[1]),None)
            if obs is None:self.selection=None; self.inspect(); return
            ttk.Label(self.inspector,text="观测属性",font=(FONT,10,"bold")).pack(anchor="w")
            ttk.Label(self.inspector,text=obs["id"]+" · "+KINDS[obs["kind"]],font=(FONT,13)).pack(anchor="w",pady=(u(9),u(12)))
            for label,text in [("点序"," → ".join(obs["points"])),("观测值",str(obs["value"]) if obs["value"] is not None else "未录入，仅可用于设计"),
                               ("标准差",str(obs["sigma"])+( " 角秒" if obs["kind"] in ANGLES else " m")),("权信息","完整观测块协方差" if obs.get("covariance") is not None else "独立分量")]:
                ttk.Label(self.inspector,text=label,foreground=MUTED,font=(FONT,8)).pack(anchor="w",pady=(u(7),u(3)))
                ttk.Label(self.inspector,text=text,wraplength=u(240),font=(FONT,10)).pack(anchor="w")
            ttk.Button(self.inspector,text="编辑观测与协方差",command=self.edit_observation).pack(fill="x",pady=(u(14),u(5)))
            actions=ttk.Frame(self.inspector);actions.pack(fill="x")
            ttk.Button(actions,text="停用" if obs.get("enabled",True) else "启用",style="Ghost.TButton",command=self.toggle_observation).pack(side="left")
            ttk.Button(actions,text="删除观测",style="Danger.TButton",command=self.delete_selected).pack(side="right")
        else:
            ttk.Label(self.inspector,text="对象属性",font=(FONT,10,"bold")).pack(anchor="w",pady=(0,u(14)))
            ttk.Label(self.inspector,text="选择一个点或观测",font=(FONT,10),foreground=INK).pack(anchor="w")
            ttk.Label(self.inspector,text="在这里编辑坐标、固定分量\n和观测精度。",foreground=MUTED,font=(FONT,9),wraplength=u(240),justify="left").pack(fill="x",pady=(u(6),u(25)))
            ttk.Label(self.inspector,text="操作提示",font=(FONT,8),foreground="#98a4ad").pack(anchor="w",pady=(0,u(8)))
            ttk.Label(self.inspector,text="滚轮缩放 · 右键平移\n双击观测，录入实测值\nCtrl+Z 撤销 · Delete 删除",foreground=MUTED,font=(FONT,8),wraplength=u(240),justify="left").pack(fill="x")

    def apply_point(self):
        if not self.selection or self.selection[0]!="point":return
        try:
            name=self.selection[1]; new=deepcopy(self.net.points[name])
            for axis,var in self.point_vars.items():new[axis]=finite(var.get(),axis)
            new["fixed"]=[axis for axis,v in self.fixed_vars.items() if v.get()]
            self.checkpoint(); self.net.points[name]=new; self.changed()
        except AdjustmentError as exc:messagebox.showerror("点属性",str(exc),parent=self)

    def delete_selected(self):
        if not self.selection:return
        self.checkpoint(); kind,name=self.selection
        if kind=="point" and name in self.net.points:self.net.remove_point(name)
        elif kind=="observation":self.net.observations=[o for o in self.net.observations if o["id"]!=name]
        self.selection=None; self.changed(); self.inspect()

    def toggle_observation(self):
        if not self.selection:return
        self.checkpoint()
        for obs in self.net.observations:
            if obs["id"]==self.selection[1]:obs["enabled"]=not obs.get("enabled",True)
        self.changed(); self.inspect()

    def dialog(self,title):
        win=tk.Toplevel(self); win.title(title); win.transient(self.winfo_toplevel()); win.configure(bg=BG)
        frame=ttk.Frame(win,padding=20); frame.pack(fill="both",expand=True)
        win.grab_set(); return win,frame

    def edit_observation(self):
        if not self.selection or self.selection[0]!="observation":return
        obs=next((o for o in self.net.observations if o["id"]==self.selection[1]),None)
        if obs is None:return
        win,frame=self.dialog(obs["id"]+" · "+KINDS[obs["kind"]])
        ttk.Label(frame,text=" → ".join(obs["points"]),font=(FONT,12,"bold")).pack(anchor="w",pady=(0,12))
        ttk.Label(frame,text="观测值：角度用十进制度或 123:45:56.7；其他用米，向量分量以空格分隔。\n留空表示仅作设计观测，实测平差前必须补录。",wraplength=620).pack(anchor="w")
        raw=obs["value"]
        value=tk.StringVar(value="" if raw is None else (" ".join(str(v) for v in raw) if isinstance(raw,list) else str(raw)))
        ttk.Entry(frame,textvariable=value,width=60).pack(fill="x",pady=(7,12))
        ttk.Label(frame,text="标准差：角度用角秒，其他用米。向量可填一个共用值或分别填写各分量。").pack(anchor="w")
        sigma=tk.StringVar(value=" ".join(str(v) for v in obs["sigma"]) if isinstance(obs["sigma"],list) else str(obs["sigma"]))
        ttk.Entry(frame,textvariable=sigma).pack(fill="x",pady=(7,12))
        components=tk.StringVar(value=" ".join(obs["components"]))
        if obs["kind"]=="coordinate":
            ttk.Label(frame,text="观测分量（顺序同时用于观测值、标准差和协方差阵）").pack(anchor="w")
            ttk.Combobox(frame,textvariable=components,values=[" ".join(self.net.axes)]+list(self.net.axes),state="readonly").pack(fill="x",pady=(6,12))
        covtext=None
        if obs["kind"] in ("gnss","coordinate"):
            ttk.Label(frame,text="可选完整协方差阵（m²）：填写后覆盖上面的标准差；空白则使用独立分量。").pack(anchor="w")
            covtext=tk.Text(frame,height=4,width=60,font=("Consolas",10),relief="flat",highlightthickness=1,highlightbackground="#dce5e9")
            covtext.pack(fill="x",pady=(6,12))
            if obs.get("covariance") is not None:covtext.insert("1.0",obs["covariance"] if isinstance(obs["covariance"],str) else "\n".join(" ".join(str(v) for v in row) for row in obs["covariance"]))
        def apply():
            candidate=deepcopy(obs); candidate.update(value=value.get().strip() or None,sigma=sigma.get().strip(),components=components.get().split())
            candidate["covariance"]=covtext.get("1.0","end-1c").strip() or None if covtext is not None else None
            try:
                temporary=deepcopy(self.net)
                temporary.observations=[candidate if o["id"]==obs["id"] else o for o in temporary.observations]
                linearize(temporary)
                self.checkpoint(); self.net.observations=[candidate if o["id"]==obs["id"] else o for o in self.net.observations]
                self.changed(); self.inspect(); win.destroy()
            except (AdjustmentError,ValueError) as exc:messagebox.showerror("观测输入",str(exc),parent=win)
        ttk.Button(frame,text="应用观测",style="Accent.TButton",command=apply).pack(anchor="e")

    def constraints_dialog(self):
        win,frame=self.dialog("精确限制条件")
        ttk.Label(frame,text="每行一个线性限制。格式：点名.分量:系数 … = 确定值（米）\n例：P1.X:1 P2.X:1 = 200\n固定分量会自动移至常数项；限制必须独立。无需限制时保持空白。",wraplength=650).pack(anchor="w")
        text=tk.Text(frame,width=65,height=10,font=("Consolas",11),relief="flat",padx=10,pady=10)
        text.pack(fill="both",expand=True,pady=12)
        text.insert("1.0","\n".join(" ".join(f"{k}:{v:g}" for k,v in c["terms"].items())+f" = {c['value']:g}" for c in self.net.constraints))
        def apply():
            try:
                data=parse_constraints(text.get("1.0","end")); candidate=deepcopy(self.net); candidate.constraints=data; linearize(candidate)
                self.checkpoint(); self.net.constraints=data
                if data:self.method.set(MODEL_NAMES["indirect_constraints"])
                self.changed(); win.destroy()
            except AdjustmentError as exc:messagebox.showerror("限制条件",str(exc),parent=win)
        ttk.Button(frame,text="应用限制",style="Accent.TButton",command=apply).pack(anchor="e")

    def options_changed(self,_event=None):
        self.checkpoint(); self.net.method=next(k for k,v in MODEL_NAMES.items() if v==self.method.get())
        if self.mode.get()=="布网设计":self.precision.set("先验"); self.precision_box.config(state="disabled")
        else:self.precision_box.config(state="readonly")
        self.changed()

    def family_changed(self,_event=None):
        new=self.family.get()
        if new==self.net.family:return
        planar=lambda f:f not in ("水准网","GNSS网")
        if planar(new) and planar(self.net.family):self.checkpoint(); self.net.family=new; self.changed(); return
        if self.net.points and not messagebox.askyesno("切换坐标域","此切换会建立一个新的空网。需要保留当前网时，请先取消并保存项目。继续？",parent=self):
            self.family.set(self.net.family); return
        self.checkpoint(); self.restore(Network(new),dirty=True)

    def new_network(self):
        if self.net.points and not messagebox.askyesno("新建空网","清空当前画布？可用撤销恢复；需要持久保留时请先保存项目。",parent=self):return
        self.checkpoint(); self.restore(Network(self.family.get()),dirty=True)

    def load_example(self,confirm=True,measured=False):
        if confirm and self.net.points and not messagebox.askyesno("载入示例网","用当前类型的示例替换画布？可用撤销恢复。",parent=self):return
        self.checkpoint(); self.restore(example_network(self.family.get(),measured),dirty=True)
        self.mode.set("实测平差" if measured else "布网设计")
        self.precision.set("后验" if measured else "先验"); self.precision_box.config(state="readonly" if measured else "disabled")

    def restore(self,net,dirty=False):
        self.net=net; self.family.set(net.family); self.method.set(MODEL_NAMES[net.method]); self.selection=None; self.pending=[]
        self.project_name.set(net.name)
        self.solution=None; self.compiled=None; self.matrices={}; self.dirty=dirty
        self.rebuild_tools(); self.set_tool("select"); self.inspect(); self.fit_view(); self.request_refresh()

    def save_project(self,path=None):
        if path is None:path=filedialog.asksaveasfilename(parent=self,title="保存控制网项目",defaultextension=".net.json",initialfile=Path(self.project_path).name if self.project_path else self.net.family+".net.json",filetypes=[("控制网项目","*.net.json"),("JSON","*.json")])
        if not path:return False
        try:
            doc=self.net.to_dict(); doc.update(mode=self.mode.get(),precision=self.precision.get())
            Path(path).write_text(json.dumps(doc,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
            self.project_path=str(path); self.dirty=False; self.notice.set("控制网项目已保存 · "+str(path)); return True
        except (OSError,ValueError) as exc:messagebox.showerror("保存失败",str(exc),parent=self); return False

    def open_project(self,path=None):
        if path is None:
            if self.dirty:
                response=messagebox.askyesnocancel("保存控制网","打开项目之前是否保存当前控制网？",parent=self)
                if response is None or (response and not self.save_project()):return False
            path=filedialog.askopenfilename(parent=self,title="打开控制网项目",filetypes=[("控制网 JSON","*.json")])
        if not path:return False
        try:
            if Path(path).stat().st_size>4_000_000:raise AdjustmentError("控制网项目超过 4 MB。")
            doc=json.loads(Path(path).read_text(encoding="utf-8-sig")); net=Network.from_dict(doc)
            self.checkpoint(); self.restore(net)
            self.mode.set(doc.get("mode","布网设计") if doc.get("mode") in ("布网设计","实测平差") else "布网设计")
            self.precision.set(doc.get("precision","先验") if doc.get("precision") in ("先验","后验") else "先验")
            if self.mode.get()=="布网设计":self.precision.set("先验")
            self.precision_box.config(state="disabled" if self.mode.get()=="布网设计" else "readonly")
            self.project_path=str(path); self.dirty=False; self.notice.set("项目已打开 · "+str(path)); return True
        except (OSError,ValueError,TypeError,KeyError) as exc:messagebox.showerror("打开失败",str(exc),parent=self); return False

    def export_matrix(self,path=None):
        a=self.matrices.get(self.matrix_choice.get())
        if a is None:return False
        if path is None:path=filedialog.asksaveasfilename(parent=self,title="导出当前矩阵",defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not path:return False
        try:
            a=np.asarray(a)
            with Path(path).open("w",encoding="utf-8-sig",newline="") as f:csv.writer(f).writerows(a.reshape(-1,1) if a.ndim==1 else a)
            self.notice.set("矩阵已导出 · "+str(path)); return True
        except OSError as exc:messagebox.showerror("导出失败",str(exc),parent=self); return False

    def export_dialog(self):
        if self.solution is None:
            if not self.calculate():return
        path=filedialog.asksaveasfilename(parent=self,title="导出控制网结果",defaultextension=".json",initialfile=self.net.family+"结果.json",filetypes=[("完整结果 JSON","*.json"),("计算报告 TXT","*.txt"),("点坐标与精度 CSV","*.csv")])
        if path:self.export_result(path)

    def export_result(self,path):
        if self.solution is None:return False
        try:
            path=Path(path); s=self.solution
            if path.suffix.lower()=="txt":path.write_text(network_report(self.net,s),encoding="utf-8-sig")
            elif path.suffix.lower()=="csv":
                with path.open("w",encoding="utf-8-sig",newline="") as f:
                    writer=csv.writer(f); writer.writerow(["点名"]+list(self.net.axes)+["m"+a for a in self.net.axes]+["三维点位中误差","XY椭圆长半轴1sigma","XY椭圆短半轴1sigma","长轴方向度(+X向+Y)"])
                    precision={p["point"]:p for p in s.point_precision}
                    for name,point in s.points.items():
                        p=precision.get(name,{})
                        writer.writerow([name]+[point[a] for a in self.net.axes]+[p.get("m"+a,"") for a in self.net.axes]+[p.get(k,"") for k in ("m3D","major","minor","azimuth")])
            else:path.write_text(json.dumps({"format":"survey-network-result","version":1,"network":self.net.to_dict(),"solution":s.to_dict()},ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
            self.notice.set("结果已导出 · "+str(path)); return True
        except (OSError,ValueError) as exc:messagebox.showerror("导出失败",str(exc),parent=self); return False

    def send_matrix(self):
        if self.compiled is None:self.update_analysis()
        if self.compiled is None or not self.compiled.stats["n"]:return
        m=self.compiled; method=self.net.method; matrices=automatic_matrices(m)
        encode=lambda a:"\n".join(" ".join(f"{v:.16g}" for v in row) for row in np.atleast_2d(a) if len(row))
        data={"title":self.net.name+" · 自动提取","note":"由控制网自动提取；长度单位 m，角度方程为 rad。可在画布结果 JSON 中查看参数和观测顺序。",
              "P":encode(m.P),"weight_mode":"完整权阵","precision":"先验" if self.mode.get()=="布网设计" else self.precision.get(),"sigma0":"1","observed":encode(m.L.reshape(-1,1))}
        if method=="condition":
            A=matrices["A · 条件系数（零空间基）"]
            if not len(A):messagebox.showinfo("无多余条件","当前没有多余观测，条件系数矩阵为空。可使用间接平差。",parent=self); return
            data.update(A=encode(A),w=encode(matrices["w · 条件闭合差"].reshape(-1,1)))
        elif method=="condition_parameters":
            if not m.Z.shape[1]:messagebox.showinfo("无自由参数","所有参数均已固定或被限制确定，可使用条件平差。",parent=self); return
            data.update(A=encode(np.eye(len(m.L))),B=encode(-m.B@m.Z),w=encode((m.l-m.B@m.xp).reshape(-1,1)))
        else:
            if not m.keys:messagebox.showinfo("无未知参数","所有点分量都已固定。",parent=self); return
            linearization_points=self.solution.points if self.solution is not None else self.net.points
            data.update(B=encode(m.B),l=encode(m.l.reshape(-1,1)),x0=encode(np.array([linearization_points[p][a] for p,a in m.keys]).reshape(-1,1)))
            if len(m.C):method="indirect_constraints"; data.update(C=encode(m.C),d=encode(m.d.reshape(-1,1)))
            else:method="indirect"
        if self.on_matrix:self.on_matrix(method,data)
