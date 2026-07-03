"""
PaddleOCR 可视化工具 - v2.2.0
支持 PaddleOCR + ddddocr 双引擎
依赖: pip install Pillow requests
"""

import os
import re
import json
import base64
import threading
import requests
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw

# ============================================================
# 常量
# ============================================================
版本 = "v2.2.0"
默认服务地址 = "http://localhost:8000"

# ============================================================
# 工具函数
# ============================================================
def 图片转base64(路径) -> str:
    with open(路径, "rb") as f:
        return base64.b64encode(f.read()).decode()

def 裁剪预览图(路径, 最大宽=380, 最大高=260) -> ImageTk.PhotoImage:
    img = Image.open(路径)
    w, h = img.size
    比例 = min(最大宽 / w, 最大高 / h, 1.0)
    w2, h2 = int(w * 比例), int(h * 比例)
    img = img.resize((w2, h2), Image.LANCZOS)
    return ImageTk.PhotoImage(img)


# ============================================================
# 主窗口
# ============================================================
class OCR可视工具:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"PaddleOCR + ddddocr 可视化工具 {版本}")
        self.root.geometry("950x680")
        self.root.minsize(850, 550)

        # 状态变量
        self.当前图片路径 = None
        self.滑块图片路径 = None
        self.背景图片路径 = None
        self.服务地址 = tk.StringVar(value=默认服务地址)
        self.API密钥 = tk.StringVar(value="")
        self.关键字 = tk.StringVar(value="")
        self.是否模糊 = tk.BooleanVar(value=True)
        self.状态文本 = tk.StringVar(value="就绪")
        self.引擎选择 = tk.StringVar(value="paddle")  # paddle / dddd

        # 构建界面
        self.构建顶部栏()
        self.构建主体()
        self.构建底部栏()

    # ——————————————— 顶部栏 ———————————————
    def 构建顶部栏(self):
        框架 = ttk.LabelFrame(self.root, text="服务器配置", padding=8)
        框架.pack(fill="x", padx=10, pady=(10, 0))

        ttk.Label(框架, text="地址:").grid(row=0, column=0, sticky="w")
        ttk.Entry(框架, textvariable=self.服务地址, width=28).grid(row=0, column=1, padx=5, sticky="w")
        ttk.Label(框架, text="API Key:").grid(row=0, column=2, padx=(10, 0), sticky="w")
        ttk.Entry(框架, textvariable=self.API密钥, width=20, show="*").grid(row=0, column=3, padx=5, sticky="w")
        ttk.Button(框架, text="测试连接", command=self.测试连接).grid(row=0, column=4, padx=(10, 0))

    # ——————————————— 主体 ———————————————
    def 构建主体(self):
        主体框架 = ttk.Frame(self.root)
        主体框架.pack(fill="both", expand=True, padx=10, pady=6)

        # ===== 左：图片预览 =====
        左栏 = ttk.LabelFrame(主体框架, text="图片预览", padding=5)
        左栏.pack(side="left", fill="both", expand=True)

        self.预览标签 = ttk.Label(左栏, text="选择图片后显示预览", anchor="center",
                              background="#f0f0f0", foreground="#999")
        self.预览标签.pack(fill="both", expand=True)

        # ===== 右：结果 =====
        右栏 = ttk.LabelFrame(主体框架, text="识别结果", padding=5)
        右栏.pack(side="right", fill="both", expand=True, padx=(8, 0))

        列 = ("项目", "内容", "额外信息")
        self.结果表格 = ttk.Treeview(右栏, columns=列, show="headings", height=14)
        for c in 列:
            self.结果表格.heading(c, text=c)
        self.结果表格.column("项目", width=80, anchor="center")
        self.结果表格.column("内容", width=200, anchor="w")
        self.结果表格.column("额外信息", width=120, anchor="center")

        滚动条 = ttk.Scrollbar(右栏, orient="vertical", command=self.结果表格.yview)
        self.结果表格.configure(yscrollcommand=滚动条.set)
        self.结果表格.pack(side="left", fill="both", expand=True)
        滚动条.pack(side="right", fill="y")

        # ===== 功能按钮区 =====
        按钮栏 = ttk.LabelFrame(self.root, text="功能", padding=6)
        按钮栏.pack(fill="x", padx=10, pady=(0, 6))

        # 第一行：基础操作
        ttk.Button(按钮栏, text="📂 选图片", command=self.选择图片).pack(side="left", padx=(0, 3))
        ttk.Button(按钮栏, text="📂 选滑块图", command=self.选择滑块图).pack(side="left", padx=3)
        ttk.Button(按钮栏, text="📂 选背景图", command=self.选择背景图).pack(side="left", padx=3)

        ttk.Separator(按钮栏, orient="vertical").pack(side="left", fill="y", padx=8)

        # 引擎选择
        ttk.Label(按钮栏, text="引擎:").pack(side="left", padx=(0, 2))
        引擎菜单 = ttk.Combobox(按钮栏, textvariable=self.引擎选择, values=["paddle", "dddd"], width=6, state="readonly")
        引擎菜单.pack(side="left", padx=2)
        ttk.Button(按钮栏, text="🔍 识别", command=self.开始识别).pack(side="left", padx=5)

        ttk.Separator(按钮栏, orient="vertical").pack(side="left", fill="y", padx=8)

        # ddddocr 专用按钮
        ttk.Button(按钮栏, text="🎯 目标检测", command=self.目标检测).pack(side="left", padx=3)
        ttk.Button(按钮栏, text="🎮 滑块匹配", command=self.滑块匹配).pack(side="left", padx=3)

        # 第二行：PaddleOCR 查找
        查找栏 = ttk.Frame(self.root)
        查找栏.pack(fill="x", padx=10)

        ttk.Label(查找栏, text="关键字:").pack(side="left", padx=(0, 2))
        ttk.Entry(查找栏, textvariable=self.关键字, width=15).pack(side="left", padx=2)
        ttk.Checkbutton(查找栏, text="模糊匹配", variable=self.是否模糊).pack(side="left", padx=2)
        ttk.Button(查找栏, text="查找文字", command=self.开始查找).pack(side="left", padx=2)

        ttk.Separator(查找栏, orient="vertical").pack(side="left", fill="y", padx=10)

        ttk.Button(查找栏, text="🧹 清空", command=self.清空结果).pack(side="right")
        ttk.Label(查找栏, text=f" | ddddocr {版本} 支持: OCR / 目标检测 / 滑块匹配").pack(side="right", padx=(0, 10))

    # ——————————————— 底部栏 ———————————————
    def 构建底部栏(self):
        底部 = ttk.Frame(self.root, relief="sunken", padding=4)
        底部.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(底部, textvariable=self.状态文本).pack(side="left")

    # ——————————————— 操作 ———————————————
    def 设置状态(self, 文字):
        self.状态文本.set(文字)
        self.root.update_idletasks()

    def 选择图片(self):
        路径 = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp"), ("所有文件", "*.*")]
        )
        if not 路径: return
        self.当前图片路径 = 路径
        try:
            预览 = 裁剪预览图(路径)
            self.预览标签.configure(image=预览, text="")
            self.预览标签.image = 预览
            self.设置状态(f"已选择: {os.path.basename(路径)}")
        except Exception as e:
            messagebox.showerror("错误", f"无法加载图片:\n{e}")

    def 选择滑块图(self):
        路径 = filedialog.askopenfilename(title="选择滑块图片（小图）")
        if 路径:
            self.滑块图片路径 = 路径
            self.设置状态(f"滑块图: {os.path.basename(路径)}")

    def 选择背景图(self):
        路径 = filedialog.askopenfilename(title="选择背景图片（大图）")
        if 路径:
            self.背景图片路径 = 路径
            self.设置状态(f"背景图: {os.path.basename(路径)}")

    def 测试连接(self):
        def _请求():
            try:
                resp = requests.get(self.服务地址.get().rstrip("/") + "/", timeout=5)
                data = resp.json()
                if data.get("status") == "running":
                    v = data.get("version", "?")
                    引擎 = data.get("engines", {})
                    dddd = " ✅" if 引擎.get("ddddocr") else " ❌"
                    gpu = "GPU" if data.get("gpu_enabled") else "CPU"
                    auth = "开" if data.get("auth_required") else "关"
                    信息 = f"v{v} | {gpu} | 认证:{auth} | ddddocr:{dddd}"
                    self.root.after(0, lambda: self.设置状态(f"连接成功 ✅ {信息}"))
                    self.root.after(0, lambda: messagebox.showinfo("连接成功", f"版本: {v}\n推理: {gpu}\nddddocr:{dddd}\n认证: {auth}"))
                else:
                    self.root.after(0, lambda: self.设置状态("连接失败: 服务异常"))
            except Exception as e:
                self.root.after(0, lambda: self.设置状态(f"连接失败: {e}"))

        self.设置状态("正在测试连接...")
        threading.Thread(target=_请求, daemon=True).start()

    def _请求API(self, 接口, 数据):
        地址 = self.服务地址.get().rstrip("/") + 接口
        头 = {"Content-Type": "application/json"}
        if self.API密钥.get():
            头["Authorization"] = f"Bearer {self.API密钥.get()}"
        resp = requests.post(地址, json=数据, headers=头, timeout=30)
        return resp.json()

    def 开始识别(self):
        if not self.当前图片路径:
            messagebox.showwarning("提示", "请先选择一张图片")
            return
        引擎 = self.引擎选择.get()

        def _请求():
            self.root.after(0, lambda: self.设置状态(f"正在识别（{引擎}）..."))
            try:
                b64 = 图片转base64(self.当前图片路径)
                if 引擎 == "paddle":
                    data = self._请求API("/ocr/base64", {"image": b64})
                    self.root.after(0, lambda: self.展示Paddle结果(data))
                else:
                    data = self._请求API("/dddd/ocr", {"image": b64})
                    self.root.after(0, lambda: self.展示Dddd结果(data))
            except Exception as e:
                self.root.after(0, lambda: self.设置状态(f"识别失败: {e}"))

        threading.Thread(target=_请求, daemon=True).start()

    def 开始查找(self):
        if not self.当前图片路径:
            messagebox.showwarning("提示", "请先选择一张图片"); return
        if not self.关键字.get().strip():
            messagebox.showwarning("提示", "请输入关键字"); return

        def _请求():
            self.root.after(0, lambda: self.设置状态(f"查找「{self.关键字.get()}」..."))
            try:
                b64 = 图片转base64(self.当前图片路径)
                data = self._请求API("/ocr/search/base64", {"image": b64, "keyword": self.关键字.get(), "fuzzy": self.是否模糊.get()})
                self.root.after(0, lambda: self.展示Paddle结果(data))
            except Exception as e:
                self.root.after(0, lambda: self.设置状态(f"查找失败: {e}"))

        threading.Thread(target=_请求, daemon=True).start()

    def 目标检测(self):
        if not self.当前图片路径:
            messagebox.showwarning("提示", "请先选择一张图片，用于目标检测"); return

        def _请求():
            self.root.after(0, lambda: self.设置状态("正在目标检测..."))
            try:
                b64 = 图片转base64(self.当前图片路径)
                data = self._请求API("/dddd/det", {"image": b64})
                self.root.after(0, lambda: self.展示检测结果(data))
            except Exception as e:
                self.root.after(0, lambda: self.设置状态(f"检测失败: {e}"))

        threading.Thread(target=_请求, daemon=True).start()

    def 滑块匹配(self):
        if not self.滑块图片路径 or not self.背景图片路径:
            messagebox.showwarning("提示", "请先选择滑块图和背景图（用「选滑块图」「选背景图」按钮）"); return

        def _请求():
            self.root.after(0, lambda: self.设置状态("正在滑块匹配..."))
            try:
                target_b64 = 图片转base64(self.滑块图片路径)
                bg_b64 = 图片转base64(self.背景图片路径)
                data = self._请求API("/dddd/slide", {"target_image": target_b64, "background_image": bg_b64, "algo": "match"})
                self.root.after(0, lambda: self.展示滑块结果(data))
            except Exception as e:
                self.root.after(0, lambda: self.设置状态(f"滑块匹配失败: {e}"))

        threading.Thread(target=_请求, daemon=True).start()

    # ===== 展示结果 =====
    def 清空表格(self):
        for row in self.结果表格.get_children():
            self.结果表格.delete(row)

    def 展示Paddle结果(self, data):
        self.清空表格()
        if data.get("code") != 0:
            self.设置状态(f"失败: {data.get('message', '')}")
            return
        项 = data.get("data", data.get("matches", []))
        for i, item in enumerate(项, 1):
            self.结果表格.insert("", "end", values=(
                f"#{i}",
                item.get("text", ""),
                f"置信:{item.get('confidence', 0):.4f}  X:{item.get('x', '')} Y:{item.get('y', '')}"
            ))
        self.设置状态(f"完成 ✅ 共 {len(项)} 项")

    def 展示Dddd结果(self, data):
        self.清空表格()
        if data.get("code") != 0:
            self.设置状态(f"失败: {data.get('message', '')}")
            return
        text = data.get("text", "")
        self.结果表格.insert("", "end", values=("结果", text, f"引擎: {data.get('engine', 'ddddocr')}"))
        self.设置状态(f"ddddocr 识别完成 ✅ 结果: {text}")

    def 展示检测结果(self, data):
        self.清空表格()
        if data.get("code") != 0:
            self.设置状态(f"失败: {data.get('message', '')}")
            return
        boxes = data.get("boxes", [])
        for i, box in enumerate(boxes, 1):
            self.结果表格.insert("", "end", values=(
                f"🔲 #{i}",
                f"({box.get('x1',0):.0f}, {box.get('y1',0):.0f})",
                f"→ ({box.get('x2',0):.0f}, {box.get('y2',0):.0f})"
            ))
        self.设置状态(f"目标检测完成 ✅ 共 {len(boxes)} 个目标")

    def 展示滑块结果(self, data):
        self.清空表格()
        if data.get("code") != 0:
            self.设置状态(f"失败: {data.get('message', '')}")
            return
        target = data.get("target", [])
        if len(target) >= 4:
            self.结果表格.insert("", "end", values=("缺口坐标", f"({target[0]:.0f}, {target[1]:.0f})", f"→ ({target[2]:.0f}, {target[3]:.0f})"))
        elif len(target) >= 2:
            self.结果表格.insert("", "end", values=("缺口中心", f"X: {target[0]:.0f}", f"Y: {target[1]:.0f}"))
        self.设置状态(f"滑块匹配完成 ✅")

    def 清空结果(self):
        self.清空表格()
        self.关键字.set("")
        self.设置状态("已清空")

    def 运行(self):
        self.root.mainloop()


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    工具 = OCR可视工具()
    工具.运行()
