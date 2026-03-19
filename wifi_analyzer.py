"""
WiFi Analyzer - Windows WiFi 网络分析工具 ,使用 claude code 完成
使用 netsh 扫描WiFi网络，tkinter 显示GUI
"""

import subprocess
import re
import tkinter as tk
from tkinter import ttk
import threading


# ── 颜色常量（浅色清爽风格）──
BG = "#f8f9fa"
BG_CARD = "#ffffff"
BG_HEADER = "#e9ecef"
FG = "#212529"
FG_SECONDARY = "#6c757d"
FG_LIGHT = "#adb5bd"
ACCENT = "#4361ee"
GREEN = "#2ecc71"
YELLOW_GREEN = "#82b541"
ORANGE = "#f0a030"
RED = "#e74c3c"
GRID_LINE = "#e9ecef"


def scan_wifi():
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
        try:
            output = result.stdout.decode("utf-8")
        except UnicodeDecodeError:
            output = result.stdout.decode("gbk", errors="replace")
        return parse_netsh_output(output)
    except Exception as e:
        print(f"扫描失败: {e}")
        return []


def parse_netsh_output(output):
    networks = []
    current = {}

    for line in output.splitlines():
        s = line.strip()
        if not s:
            continue

        if s.startswith("SSID") and "BSSID" not in s:
            if current.get("bssid"):
                networks.append(current)
            ssid = s.split(":", 1)[1].strip() if ":" in s else ""
            current = {"ssid": ssid or "(隐藏)", "auth": "", "encrypt": "",
                       "bssid": "", "signal": 0, "channel": 0, "band": ""}
        elif any(k in s for k in ["身份验证", "Authentication"]):
            current["auth"] = s.split(":", 1)[1].strip() if ":" in s else ""
        elif any(k in s for k in ["加密", "Cipher", "Encryption"]):
            current["encrypt"] = s.split(":", 1)[1].strip() if ":" in s else ""
        elif "BSSID" in s:
            if current.get("bssid"):
                networks.append(current)
                current = {**current, "bssid": "", "signal": 0, "channel": 0, "band": ""}
            mac = re.search(r"([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})", s)
            current["bssid"] = mac.group(1) if mac else s.split(":", 1)[1].strip()
        elif any(k in s for k in ["信号", "Signal"]):
            if "利用率" not in s:
                m = re.search(r"(\d+)%", s)
                if m:
                    current["signal"] = int(m.group(1))
        elif ("频道" in s or "Channel" in s) and "利用率" not in s:
            val = s.split(":", 1)[1].strip() if ":" in s else ""
            m = re.search(r"(\d+)", val)
            if m:
                current["channel"] = int(m.group(1))
        elif any(k in s for k in ["波段", "Band"]):
            if "利用率" not in s and "负载" not in s:
                current["band"] = s.split(":", 1)[1].strip() if ":" in s else ""

    if current.get("bssid"):
        networks.append(current)
    return networks


def signal_to_dbm(pct):
    return -100 if pct == 0 else int(pct / 2 - 100)


def security_label(auth, encrypt):
    for tag in ["WPA3", "WPA2", "WPA"]:
        if tag in auth:
            return tag
    if "Open" in auth or "开放" in auth:
        return "Open"
    return auth[:12] if auth else "?"


def signal_color(pct):
    if pct >= 75: return GREEN
    if pct >= 50: return YELLOW_GREEN
    if pct >= 30: return ORANGE
    return RED


class Tooltip:
    """轻量悬浮提示"""
    def __init__(self, canvas):
        self.canvas = canvas
        self.tip = None

    def show(self, x, y, text):
        self.hide()
        self.tip = tk.Toplevel(self.canvas)
        self.tip.wm_overrideredirect(True)
        sx = self.canvas.winfo_rootx() + x + 12
        sy = self.canvas.winfo_rooty() + y - 8
        self.tip.wm_geometry(f"+{sx}+{sy}")
        lbl = tk.Label(self.tip, text=text, bg="#333", fg="#fff",
                       font=("Segoe UI", 9), padx=8, pady=4, justify="left")
        lbl.pack()

    def hide(self):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class WifiAnalyzer:
    def __init__(self, root):
        self.root = root
        self.root.title("WiFi Analyzer")
        self.root.geometry("1150x800")
        self.root.configure(bg=BG)
        self.root.minsize(800, 500)
        self.root.overrideredirect(True)  # 去掉系统标题栏
        # 设置图标（兼容 PyInstaller 打包）
        import os, sys
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        ico_path = os.path.join(base, "dragon.ico")
        if os.path.exists(ico_path):
            self.root.iconbitmap(ico_path)
        # 窗口居中
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = (sw - 1150) // 2
        y = (sh - 800) // 2
        self.root.geometry(f"1150x800+{x}+{y}")
        self.networks = []
        self.auto_refresh = tk.BooleanVar(value=False)
        self.refresh_interval = tk.IntVar(value=5)
        self.sort_col = "signal"
        self.sort_reverse = True
        self._channel_rects = []  # (x1,y1,x2,y2, data) for tooltip

        self._build_ui()
        self.scan()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("Status.TLabel", background=BG, foreground=FG_SECONDARY, font=("Segoe UI", 10))
        style.configure("Accent.TButton", background=ACCENT, foreground="#fff", font=("Segoe UI", 10, "bold"), padding=(14, 6))
        style.map("Accent.TButton", background=[("active", "#3a56d4")])
        style.configure("TCheckbutton", background=BG, foreground=FG, font=("Segoe UI", 10))

        # ── 自定义标题栏（含所有控件）──
        TB_BG = "#e9ecef"
        title_bar = tk.Frame(self.root, bg=TB_BG, height=40)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)

        # 左侧：标题
        title_lbl = tk.Label(title_bar, text="  WiFi Analyzer", bg=TB_BG, fg=ACCENT,
                             font=("Segoe UI", 14, "bold"))
        title_lbl.pack(side="left", padx=8)

        # 右侧：关闭按钮
        close_btn = tk.Label(title_bar, text=" X ", bg=TB_BG, fg="#c0392b",
                             font=("Segoe UI", 12, "bold"), cursor="hand2")
        close_btn.pack(side="right", padx=4, pady=4)
        close_btn.bind("<Enter>", lambda e: close_btn.config(bg="#e74c3c", fg="#fff"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(bg=TB_BG, fg="#c0392b"))
        close_btn.bind("<Button-1>", lambda e: self.root.destroy())

        # 右侧：状态
        self.status_label = tk.Label(title_bar, text="就绪", bg=TB_BG, fg=FG_SECONDARY,
                                     font=("Segoe UI", 9))
        self.status_label.pack(side="right", padx=8)

        # 右侧：刷新间隔
        lbl_s = tk.Label(title_bar, text="s", bg=TB_BG, fg=FG_SECONDARY, font=("Segoe UI", 9))
        lbl_s.pack(side="right")
        self.interval_cb = ttk.Combobox(title_bar, textvariable=self.refresh_interval,
                                        values=[1, 3, 5, 10], width=3, state="readonly",
                                        font=("Segoe UI", 9))
        self.interval_cb.pack(side="right", padx=0)

        # 右侧：自动刷新
        auto_cb = tk.Checkbutton(title_bar, text="自动刷新", variable=self.auto_refresh,
                                 command=self._toggle_auto, bg=TB_BG, fg=FG,
                                 activebackground=TB_BG, font=("Segoe UI", 9),
                                 selectcolor=TB_BG)
        auto_cb.pack(side="right", padx=6)

        # 右侧：扫描按钮
        scan_btn = tk.Button(title_bar, text="扫描", command=self.scan,
                             bg=ACCENT, fg="#fff", font=("Segoe UI", 9, "bold"),
                             bd=0, padx=12, pady=2, cursor="hand2",
                             activebackground="#3a56d4", activeforeground="#fff")
        scan_btn.pack(side="right", padx=6, pady=5)

        # 拖动窗口
        self._drag_x = 0
        self._drag_y = 0
        def start_drag(e):
            self._drag_x = e.x
            self._drag_y = e.y
        def do_drag(e):
            x = self.root.winfo_x() + e.x - self._drag_x
            y = self.root.winfo_y() + e.y - self._drag_y
            self.root.geometry(f"+{x}+{y}")
        for widget in (title_bar, title_lbl):
            widget.bind("<Button-1>", start_drag)
            widget.bind("<B1-Motion>", do_drag)

        # ── 选项卡 ──
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG_HEADER, foreground=FG,
                        font=("Segoe UI", 10), padding=(16, 6))
        style.map("TNotebook.Tab", background=[("selected", BG_CARD)],
                  foreground=[("selected", ACCENT)])

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        # ── Tab 1: 网络列表 ──
        tab_list = ttk.Frame(self.notebook)
        self.notebook.add(tab_list, text="  网络列表  ")

        cols = ("ssid", "signal", "dbm", "channel", "band", "security", "bssid")
        col_text = {"ssid": "SSID", "signal": "信号", "dbm": "dBm", "channel": "信道",
                    "band": "频段", "security": "安全", "bssid": "BSSID"}
        col_w = {"ssid": 160, "signal": 70, "dbm": 60, "channel": 60, "band": 80, "security": 80, "bssid": 150}

        style.configure("Treeview", background=BG_CARD, foreground=FG, fieldbackground=BG_CARD,
                        font=("Segoe UI", 10), rowheight=30, borderwidth=0)
        style.configure("Treeview.Heading", background=BG_HEADER, foreground=FG,
                        font=("Segoe UI", 10, "bold"), borderwidth=0, relief="flat")
        style.map("Treeview", background=[("selected", "#dbe4ff")])
        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        tree_frame = ttk.Frame(tab_list)
        tree_frame.pack(fill="both", expand=True, padx=2, pady=2)

        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=col_text[c], command=lambda _c=c: self._sort_by(_c))
            self.tree.column(c, width=col_w[c], anchor="center" if c != "ssid" else "w")
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ── Tab 2: 信号强度（横向柱状图）──
        tab_signal = ttk.Frame(self.notebook)
        self.notebook.add(tab_signal, text="  信号强度  ")
        self.signal_canvas = tk.Canvas(tab_signal, bg=BG_CARD, highlightthickness=0, bd=0)
        self.signal_canvas.pack(fill="both", expand=True, padx=2, pady=2)

        # ── Tab 3: 信道分布 ──
        tab_channel = ttk.Frame(self.notebook)
        self.notebook.add(tab_channel, text="  信道分布  ")
        self.channel_canvas = tk.Canvas(tab_channel, bg=BG_CARD, highlightthickness=0, bd=0)
        self.channel_canvas.pack(fill="both", expand=True, padx=2, pady=2)

        self.signal_canvas.bind("<Configure>", lambda e: self._draw_signal_chart())
        self.channel_canvas.bind("<Configure>", lambda e: self._draw_channel_chart())

        # 信道图悬浮提示
        self._ch_tooltip = Tooltip(self.channel_canvas)
        self.channel_canvas.bind("<Motion>", self._on_channel_hover)
        self.channel_canvas.bind("<Leave>", lambda e: self._ch_tooltip.hide())

    # ── 扫描 ──
    def scan(self):
        self.status_label.config(text="扫描中...")
        self.root.update_idletasks()
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        nets = scan_wifi()
        self.root.after(0, lambda: self._update(nets))

    def _update(self, networks):
        self.networks = networks
        self.status_label.config(text=f"发现 {len(networks)} 个接入点")
        self._refresh_tree()
        self._draw_signal_chart()
        self._draw_channel_chart()

    # ── 表格 ──
    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        nets = sorted(self.networks, key=lambda n: n.get(self.sort_col, 0), reverse=self.sort_reverse)
        for n in nets:
            sec = security_label(n["auth"], n["encrypt"])
            dbm = signal_to_dbm(n["signal"])
            vals = (n["ssid"], f'{n["signal"]}%', str(dbm), str(n["channel"]), n["band"], sec, n["bssid"])
            tag = "g" if n["signal"] >= 60 else ("m" if n["signal"] >= 35 else "w")
            self.tree.insert("", "end", values=vals, tags=(tag,))
        self.tree.tag_configure("g", foreground="#1a8a4a")
        self.tree.tag_configure("m", foreground="#c07000")
        self.tree.tag_configure("w", foreground="#c0392b")

    def _sort_by(self, col):
        if self.sort_col == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_col = col
            self.sort_reverse = col in ("signal", "dbm")
        self._refresh_tree()

    # ── 信号强度图（横向柱状图）──
    def _draw_signal_chart(self):
        c = self.signal_canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 100 or h < 100:
            return
        if not self.networks:
            c.create_text(w // 2, h // 2, text="暂无数据", fill=FG_LIGHT, font=("Segoe UI", 13))
            return

        nets = sorted(self.networks, key=lambda n: n["signal"], reverse=True)[:25]
        n = len(nets)

        margin_l, margin_r, margin_t, margin_b = 140, 50, 24, 16
        chart_w = w - margin_l - margin_r
        chart_h = h - margin_t - margin_b
        bar_h = max(8, min(28, (chart_h - 4) // n - 3))
        gap = max(2, (chart_h - bar_h * n) // max(n + 1, 1))

        # X 轴网格
        for pct in range(0, 101, 25):
            x = margin_l + pct / 100 * chart_w
            c.create_line(x, margin_t, x, margin_t + chart_h, fill=GRID_LINE)
            c.create_text(x, margin_t - 6, text=f"{pct}%", fill=FG_SECONDARY,
                          font=("Segoe UI", 8), anchor="s")

        # 柱状图
        for i, net in enumerate(nets):
            y = margin_t + gap + i * (bar_h + gap)
            bar_w = max(2, net["signal"] / 100 * chart_w)
            color = signal_color(net["signal"])

            # 圆角矩形（用 create_rectangle 模拟）
            c.create_rectangle(margin_l, y, margin_l + bar_w, y + bar_h,
                               fill=color, outline="", width=0)

            # 左侧 SSID 标签
            label = net["ssid"]
            if len(label) > 16:
                label = label[:15] + "…"
            c.create_text(margin_l - 8, y + bar_h // 2, text=label,
                          fill=FG, font=("Segoe UI", 9), anchor="e")

            # 右侧数值
            c.create_text(margin_l + bar_w + 6, y + bar_h // 2,
                          text=f"{net['signal']}%  ({signal_to_dbm(net['signal'])} dBm)",
                          fill=FG_SECONDARY, font=("Segoe UI", 8), anchor="w")

    # ── 信道分布图 ──
    def _draw_channel_chart(self):
        c = self.channel_canvas
        c.delete("all")
        self._channel_rects = []
        w, h = c.winfo_width(), c.winfo_height()
        if w < 100 or h < 100:
            return
        if not self.networks:
            c.create_text(w // 2, h // 2, text="暂无数据", fill=FG_LIGHT, font=("Segoe UI", 13))
            return

        # 按信道分组，保留每个网络的独立信息
        ch_nets = {}
        for net in self.networks:
            ch = net["channel"]
            if ch == 0:
                continue
            ch_nets.setdefault(ch, []).append(net)

        if not ch_nets:
            c.create_text(w // 2, h // 2, text="未检测到信道", fill=FG_LIGHT, font=("Segoe UI", 13))
            return

        ALL_24 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
        ALL_5 = [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112,
                 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165]

        # 一组柔和的颜色用于区分不同 SSID
        PALETTE = ["#4361ee", "#2ecc71", "#e67e22", "#9b59b6", "#e74c3c",
                   "#1abc9c", "#f39c12", "#3498db", "#e84393", "#00b894"]
        # 为每个 SSID 分配固定颜色
        all_ssids = list(dict.fromkeys(n["ssid"] for n in self.networks if n["channel"] > 0))
        ssid_color = {s: PALETTE[i % len(PALETTE)] for i, s in enumerate(all_ssids)}

        margin_l, margin_r, margin_t, margin_b = 50, 30, 20, 20
        usable_w = w - margin_l - margin_r
        usable_h = h - margin_t - margin_b
        half_h = (usable_h - 30) // 2

        def draw_group(all_channels, y_start, title):
            c.create_text(margin_l, y_start, text=title, fill=ACCENT,
                          font=("Segoe UI", 11, "bold"), anchor="nw")

            n_ch = len(all_channels)
            bar_top = y_start + 26
            bar_area_h = half_h - 46

            col_w = max(12, min(40, (usable_w - 10) // n_ch - 2))
            gap = max(1, min(5, (usable_w - col_w * n_ch) // max(n_ch - 1, 1)))
            total_w = n_ch * col_w + (n_ch - 1) * gap
            start_x = margin_l + max(0, (usable_w - total_w) // 2)

            # Y轴：信号强度 0-100%
            for pct in (0, 25, 50, 75, 100):
                y = bar_top + bar_area_h - (pct / 100 * bar_area_h)
                c.create_line(start_x - 4, y, start_x + total_w + 4, y, fill=GRID_LINE)
                if pct > 0:
                    c.create_text(start_x - 8, y, text=f"{pct}%", fill=FG_SECONDARY,
                                  font=("Segoe UI", 7), anchor="e")

            for i, ch in enumerate(all_channels):
                x = start_x + i * (col_w + gap)
                y_bot = bar_top + bar_area_h
                nets_on_ch = ch_nets.get(ch, [])

                if nets_on_ch:
                    # 按信号从高到低排列
                    nets_sorted = sorted(nets_on_ch, key=lambda n: n["signal"], reverse=True)
                    n_nets = len(nets_sorted)
                    # 每个网络一个小柱子，均分列宽
                    sub_w = max(3, col_w // max(n_nets, 1))
                    sub_gap = max(0, (col_w - sub_w * n_nets) // max(n_nets + 1, 1))

                    for j, net in enumerate(nets_sorted):
                        sx = x + sub_gap + j * (sub_w + sub_gap)
                        bar_h = max(3, net["signal"] / 100 * bar_area_h)
                        sy_top = y_bot - bar_h
                        color = ssid_color.get(net["ssid"], PALETTE[0])

                        c.create_rectangle(sx, sy_top, sx + sub_w, y_bot,
                                           fill=color, outline="", width=0)

                        # 柱顶标注 SSID 名称和信号
                        label = net["ssid"]
                        if len(label) > 8:
                            label = label[:7] + "…"
                        c.create_text(sx + sub_w // 2, sy_top - 3,
                                      text=f"{label}\n{net['signal']}%",
                                      fill=color, font=("Segoe UI", 6), anchor="s")

                        # tooltip 区域
                        tip_data = {"count": 1, "ssids": [f'{net["ssid"]} ({net["signal"]}%)']}
                        self._channel_rects.append((sx, sy_top, sx + sub_w, y_bot, tip_data))
                else:
                    c.create_rectangle(x, y_bot - 2, x + col_w, y_bot,
                                       fill="#dee2e6", outline="")

                # 信道号
                active = len(nets_on_ch) > 0
                c.create_text(x + col_w // 2, y_bot + 10, text=str(ch),
                              fill=FG if active else FG_LIGHT,
                              font=("Segoe UI", 8, "bold" if active else "normal"))

        draw_group(ALL_24, margin_t, "2.4 GHz  (CH 1-13)")
        draw_group(ALL_5, margin_t + half_h + 20, "5 GHz  (CH 36-165)")

    def _on_channel_hover(self, event):
        for x1, y1, x2, y2, data in self._channel_rects:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                lines = [f"共 {data['count']} 个网络："]
                for s in data["ssids"]:
                    lines.append(f"  · {s}")
                self._ch_tooltip.show(event.x, event.y, "\n".join(lines))
                return
        self._ch_tooltip.hide()

    def _toggle_auto(self):
        if self.auto_refresh.get():
            self._auto_scan()

    def _auto_scan(self):
        if self.auto_refresh.get():
            self.scan()
            ms = self.refresh_interval.get() * 1000
            self.root.after(ms, self._auto_scan)


def main():
    root = tk.Tk()
    WifiAnalyzer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
