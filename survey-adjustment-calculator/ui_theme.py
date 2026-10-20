"""Shared desktop palette, typography and widget geometry."""
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

FONT = "Microsoft YaHei UI"
BG = "#ffffff"
SIDEBAR = "#f5f7f9"
PANEL = "#f7f9fb"
EDGE = "#e3e9ee"
INK = "#293b48"
MUTED = "#7a8792"
GREEN = "#287b70"
SOFT = "#e7f1ed"
WARNING = "#ad774b"


def install(root, scale):
    u=lambda n:max(1,round(n*scale))
    for name in ("TkDefaultFont","TkTextFont","TkMenuFont","TkHeadingFont","TkCaptionFont","TkSmallCaptionFont","TkTooltipFont"):
        tkfont.nametofont(name).configure(family=FONT,size=10,weight="normal")
    tkfont.nametofont("TkFixedFont").configure(family="Consolas",size=10)
    root.option_add("*TCombobox*Listbox.font",(FONT,10))
    root.option_add("*TEntry.font",(FONT,10))
    root.option_add("*TCombobox.font",(FONT,10))
    s=ttk.Style(root);s.theme_use("clam")
    s.configure(".",font=(FONT,10),background=BG,foreground=INK)
    s.configure("TFrame",background=BG)
    s.configure("TLabel",background=BG,foreground=INK,font=(FONT,10))
    s.configure("Muted.TLabel",foreground=MUTED,font=(FONT,9))
    s.layout("TButton",[("Button.padding",{"sticky":"nswe","children":[("Button.label",{"sticky":"nswe"})]})])
    s.configure("TButton",font=(FONT,10),padding=(u(12),u(7)),width=0,background="#f0f4f6",foreground=INK,borderwidth=0,relief="flat",anchor="center")
    s.map("TButton",background=[("disabled",PANEL),("pressed","#e1e9ed"),("active","#e8eef1"),("focus","#e8eef1")],foreground=[("disabled","#a7b0b7")])
    s.configure("Accent.TButton",background=GREEN,foreground="white",font=(FONT,10,"bold"),padding=(u(16),u(7)))
    s.map("Accent.TButton",background=[("disabled","#b6cbc4"),("pressed","#1e5f56"),("active","#226c62"),("focus","#226c62")],foreground=[("disabled","white"),("active","white")])
    s.configure("Ghost.TButton",background=BG,foreground=MUTED,font=(FONT,9),padding=(u(10),u(7)))
    s.map("Ghost.TButton",background=[("active",PANEL),("focus",PANEL)],foreground=[("active",INK)])
    s.configure("Danger.TButton",background=BG,foreground="#a4736b",font=(FONT,9))
    s.map("Danger.TButton",background=[("active","#fbf1ef"),("focus","#fbf1ef")],foreground=[("active","#a45347")])
    s.configure("Tool.TButton",background=BG,font=(FONT,9),padding=(u(10),u(6)),width=0)
    s.configure("ToolActive.TButton",background=SOFT,foreground=GREEN,font=(FONT,9,"bold"),padding=(u(10),u(6)),width=0)
    s.map("ToolActive.TButton",background=[("active","#dcece5"),("focus","#dcece5")],foreground=[("active",GREEN)])
    s.configure("Tab.TButton",background=BG,foreground=MUTED,font=(FONT,10),padding=(u(12),u(8)))
    s.configure("TabActive.TButton",background=SOFT,foreground=GREEN,font=(FONT,10,"bold"),padding=(u(12),u(8)))
    s.map("TabActive.TButton",background=[("active",SOFT),("focus",SOFT)],foreground=[("active",GREEN)])
    s.configure("TNotebook",background=BG,borderwidth=0,tabmargins=0)
    s.layout("TNotebook.Tab",[("Notebook.padding",{"sticky":"nswe","children":[("Notebook.label",{"sticky":"nswe"})]})])
    s.configure("TNotebook.Tab",padding=(u(13),u(8)),font=(FONT,9),background=BG,borderwidth=0)
    s.map("TNotebook.Tab",background=[("selected",SOFT)],foreground=[("selected",GREEN),("!selected",MUTED)])
    s.configure("Shell.TNotebook",borderwidth=0,tabmargins=0,bordercolor=BG,lightcolor=BG,darkcolor=BG,relief="flat")
    s.configure("TNotebook",bordercolor=BG,lightcolor=BG,darkcolor=BG)
    s.layout("Shell.TNotebook.Tab",[])
    s.configure("Shell.TNotebook.Tab",padding=0,borderwidth=0)
    s.configure("Treeview",background=BG,fieldbackground=BG,foreground=INK,font=(FONT,10),rowheight=u(29),borderwidth=0,lightcolor=BG,darkcolor=BG,bordercolor=BG)
    s.map("Treeview",background=[("selected",SOFT)],foreground=[("selected",INK)])
    s.configure("Treeview.Heading",font=(FONT,9),padding=(u(10),u(7)),background=PANEL,foreground=MUTED,relief="flat",borderwidth=0,lightcolor=PANEL,darkcolor=PANEL,bordercolor=PANEL)
    s.map("Treeview.Heading",background=[("active","#edf2f5")])
    for widget in ("TEntry","TCombobox"):
        s.configure(widget,padding=(u(9),u(6)),font=(FONT,10),fieldbackground=BG,foreground=INK,background=BG,bordercolor=EDGE,lightcolor=EDGE,darkcolor=EDGE,borderwidth=1,arrowsize=u(11),arrowcolor=MUTED,selectbackground=SOFT,selectforeground=INK)
        s.map(widget,fieldbackground=[("disabled",PANEL),("readonly",BG)],background=[("disabled",PANEL),("readonly",BG)],bordercolor=[("focus","#86afa6"),("!focus",EDGE)],lightcolor=[("focus","#86afa6"),("!focus",EDGE)],darkcolor=[("focus","#86afa6"),("!focus",EDGE)],foreground=[("disabled","#a0aab2"),("readonly",INK)])
    # A small code-drawn indicator avoids mixing the theme's black cross with
    # the rest of the interface. Retain images for the life of the Tk root.
    size=u(14);gap=u(6)
    def checkbox(fill,border,checked=False):
        img=tk.PhotoImage(master=root,width=size+gap,height=size)
        img.put(border,to=(0,0,size,size));img.put(fill,to=(1,1,size-1,size-1))
        if checked:
            coords=[(.23,.49),(.43,.70),(.79,.29)]
            for (ax,ay),(bx,by) in zip(coords,coords[1:]):
                ax,ay,bx,by=[round(v*(size-1)) for v in (ax,ay,bx,by)]
                steps=max(abs(bx-ax),abs(by-ay),1)
                for i in range(steps+1):
                    x=round(ax+(bx-ax)*i/steps);y=round(ay+(by-ay)*i/steps)
                    for dx in range(max(1,u(1))):
                        for dy in range(max(1,u(1))):
                            if x+dx<size and y+dy<size:img.put("white",to=(x+dx,y+dy))
        return img
    root._theme_images=[checkbox(BG,"#c4cfd7"),checkbox(GREEN,GREEN,True),checkbox(PANEL,EDGE)]
    s.element_create("Clean.Check.indicator","image",root._theme_images[0],("disabled",root._theme_images[2]),("selected",root._theme_images[1]))
    s.layout("TCheckbutton",[("Checkbutton.padding",{"sticky":"nswe","children":[("Clean.Check.indicator",{"side":"left","sticky":""}),("Checkbutton.focus",{"side":"left","sticky":"w","children":[("Checkbutton.label",{"sticky":"nswe"})]})]})])
    s.configure("TCheckbutton",font=(FONT,9),background=BG,foreground=MUTED,padding=(0,u(3)))
    s.map("TCheckbutton",foreground=[("active",INK)],background=[("active",BG)])
    for orient,sticky in (("Vertical","ns"),("Horizontal","we")):
        name=orient+".TScrollbar"
        s.layout(name,[(orient+".Scrollbar.trough",{"sticky":sticky,"children":[(orient+".Scrollbar.thumb",{"sticky":"nswe"})]})])
        s.configure(name,background="#dce4e9",troughcolor=BG,bordercolor=BG,lightcolor=BG,darkcolor=BG,borderwidth=0,width=u(8),arrowsize=u(8),relief="flat")
        s.map(name,background=[("active","#bccbd3"),("pressed","#aebfc8")])
    s.configure("TSeparator",background=EDGE)
    s.configure("TPanedwindow",background=BG,borderwidth=0)
    s.configure("Sash",sashthickness=u(6),background=BG,lightcolor=BG,darkcolor=BG,bordercolor=BG,gripcount=0)
    return s
