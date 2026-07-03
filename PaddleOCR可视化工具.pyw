"""
PaddleOCR 可视化工具 - v2.1.0
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
from PIL import Image, ImageTk, ImageDraw, ImageFont

# ============================================================
# 常量
# ============================================================
版本 = "v2.1.0"
默认服务地址 = "http://localhost:8000"


# ============================================================
# 工具函数
# ============================================================
def 图片转base64(路径) -> str:
    """读取图片文件并转为 base64。"""
    with open(路径, "rb") as f:
        return base64.b64encode(f.read()).decode()


def 裁剪预览图(路径, 最大宽=400, 最大高=300) -> ImageTk.PhotoImage:
    """按比例缩放图片到预览尺寸。"""
    img = Image.open(路径)
    w, h = img.size
    # 按比例缩放
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
        self.root.title(f"PaddleOCR 可视化工具 {版本}")
        self.root.geometry("900x620")
        self.root.minsize(800, 500)

        # 状态变量
        self.当前图片路径 = None
        self.服务地址 = tk.StringVar(value=默认服务地址)
        self.API密钥 = tk.StringVar(value="")
        self.关键字 = tk.StringVar(value="")
        self.是否模糊 = tk.BooleanVar(value=True)
        self.状态文本 = tk.StringVar(value="就绪 ✅")

        # 构建界面
        self.构建顶部栏()
        self.构建主体()
        self.构建底部栏()

    # ——————————————— 顶部栏 ———————————————
    def 构建顶部栏(self):
        框架 = ttk.LabelFrame(self.root, text="服务器配置", padding=8)
        框架.pack(fill="x", padx=10, pady=(10, 0))

        ttk.Label(框架, text="地址:").grid(row=0, column=0, sticky="w")
        ttk.Entry(框架, textvariable=self.服务地址, width=30).grid(row=0, column=1, padx=5, sticky="w")

        ttk.Label(框架, text="API Key:").grid(row=0, column=2, padx=(15, 0), sticky="w")
        ttk.Entry(框架, textvariable=self.API密钥, width=25, show="*").grid(row=0, column=3, padx=5, sticky="w")

        ttk.Button(框架, text="测试连接", command=self.测试连接).grid(row=0, column=4, padx=(10, 0))

    # ——————————————— 主体 ———————————————
    def 构建主体(self):
        主体框架 = ttk.Frame(self.root)
        主体框架.pack(fill="both", expand=True, padx=10, pady=8)

        # 左半：图片预览
        左栏 = ttk.LabelFrame(主体框架, text="图片预览", padding=5)
        左栏.pack(side="left", fill="both", expand=True)

        self.预览标签 = ttk.Label(左栏, text="点击「选择图片」\n或拖拽图片到此处", anchor="center",
                              background="#f0f0f0", foreground="#999")
        self.预览标签.pack(fill="both", expand=True)

        # 右半：结果表格
        右栏 = ttk.LabelFrame(主体框架, text="识别结果", padding=5)
        右栏.pack(side="right", fill="both", expand=True, padx=(8, 0))

        # 表格
        列 = ("序号", "文字", "置信度", "X", "Y")
        self.结果表格 = ttk.Treeview(右栏, columns=列, show="headings", height=12)
        for c in 列:
            self.结果表格.heading(c, text=c)
            self.结果表格.column(c, width=60, anchor="center")
        self.结果表格.column("文字", width=200, anchor="w")
        self.结果表格.column("置信度", width=80)
        self.结果表格.column("X", width=60)
        self.结果表格.column("Y", width=60)

        滚动条 = ttk.Scrollbar(右栏, orient="vertical", command=self.结果表格.yview)
        self.结果表格.configure(yscrollcommand=滚动条.set)
        self.结果表格.pack(side="left", fill="both", expand=True)
        滚动条.pack(side="right", fill="y")

        # 按钮区
        按钮框架 = ttk.Frame(self.root)
        按钮框架.pack(fill="x", padx=10)

        ttk.Button(按钮框架, text="📂 选择图片", command=self.选择图片).pack(side="left", padx=(0, 5))
        ttk.Button(按钮框架, text="🔍 OCR识别", command=self.开始识别).pack(side="left", padx=5)

        # 查找栏
        ttk.Label(按钮框架, text="关键字:").pack(side="left", padx=(15, 2))
        ttk.Entry(按钮框架, textvariable=self.关键字, width=15).pack(side="left", padx=2)
        ttk.Checkbutton(按钮框架, text="模糊", variable=self.是否模糊).pack(side="left", padx=2)
        ttk.Button(按钮框架, text="查找", command=self.开始查找).pack(side="left", padx=2)

        ttk.Button(按钮框架, text="🗑 清空", command=self.清空结果).pack(side="right")

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
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.gif"), ("所有文件", "*.*")]
        )
        if not 路径:
            return
        self.当前图片路径 = 路径
        try:
            预览 = 裁剪预览图(路径)
            self.预览标签.configure(image=预览, text="")
            self.预览标签.image = 预览  # 保持引用
            self.设置状态(f"已选择: {os.path.basename(路径)}")
        except Exception as e:
            messagebox.showerror("错误", f"无法加载图片:\n{e}")

    def 测试连接(self):
        def _请求():
            try:
                resp = requests.get(self.服务地址.get().rstrip("/") + "/", timeout=5)
                data = resp.json()
                if data.get("status") == "running":
                    gpu = "GPU" if data.get("gpu_enabled") else "CPU"
                    auth = "已开启" if data.get("auth_required") else "未开启"
                    self.root.after(0, lambda: self.设置状态(f"连接成功 | 版本: {data['version']} | 推理: {gpu} | 认证: {auth}"))
                    self.root.after(0, lambda: messagebox.showinfo("连接成功", f"服务正常!\n版本: {data['version']}\n推理设备: {gpu}\n认证: {auth}"))
                else:
                    self.root.after(0, lambda: self.设置状态("连接失败: 服务返回异常"))
            except Exception as e:
                self.root.after(0, lambda: self.设置状态(f"连接失败: {e}"))
                self.root.after(0, lambda: messagebox.showerror("连接失败", str(e)))

        self.设置状态("正在测试连接...")
        threading.Thread(target=_请求, daemon=True).start()

    def 开始识别(self):
        if not self.当前图片路径:
            messagebox.showwarning("提示", "请先选择一张图片")
            return

        def _请求():
            self.root.after(0, lambda: self.设置状态("正在识别中..."))
            try:
                b64 = 图片转base64(self.当前图片路径)
                地址 = self.服务地址.get().rstrip("/") + "/ocr/base64"
                头 = {}
                if self.API密钥.get():
                    头["Authorization"] = f"Bearer {self.API密钥.get()}"

                resp = requests.post(地址, json={"image": b64}, headers=头, timeout=30)
                data = resp.json()

                self.root.after(0, lambda: self.展示结果(data))
            except Exception as e:
                self.root.after(0, lambda: self.设置状态(f"识别失败: {e}"))

        threading.Thread(target=_请求, daemon=True).start()

    def 开始查找(self):
        if not self.当前图片路径:
            messagebox.showwarning("提示", "请先选择一张图片")
            return
        if not self.关键字.get().strip():
            messagebox.showwarning("提示", "请输入要查找的关键字")
            return

        def _请求():
            self.root.after(0, lambda: self.设置状态(f"正在查找「{self.关键字.get()}」..."))
            try:
                b64 = 图片转base64(self.当前图片路径)
                地址 = self.服务地址.get().rstrip("/") + "/ocr/search/base64"
                头 = {}
                if self.API密钥.get():
                    头["Authorization"] = f"Bearer {self.API密钥.get()}"

                resp = requests.post(地址, json={
                    "image": b64,
                    "keyword": self.关键字.get(),
                    "fuzzy": self.是否模糊.get()
                }, headers=头, timeout=30)
                data = resp.json()

                self.root.after(0, lambda: self.展示匹配(data))
            except Exception as e:
                self.root.after(0, lambda: self.设置状态(f"查找失败: {e}"))

        threading.Thread(target=_请求, daemon=True).start()

    def 展示结果(self, data):
        """展示 OCR 识别结果。"""
        self.清空表格()
        if data.get("code") != 0:
            self.设置状态(f"识别失败: {data.get('message', '未知错误')}")
            return

        项 = data.get("data", [])
        for i, item in enumerate(项, 1):
            self.结果表格.insert("", "end", values=(
                i,
                item.get("text", ""),
                f"{item.get('confidence', 0):.4f}",
                item.get("x", ""),
                item.get("y", ""),
            ))
        self.设置状态(f"识别完成 ✅ 共 {len(项)} 个文字")

    def 展示匹配(self, data):
        """展示查找结果。"""
        self.清空表格()
        if data.get("code") != 0:
            self.设置状态(f"查找失败: {data.get('message', '未知错误')}")
            return

        匹配 = data.get("matches", [])
        总计 = data.get("total_recognized", 0)
        for i, item in enumerate(匹配, 1):
            self.结果表格.insert("", "end", values=(
                i,
                f"[匹配] {item.get('text', '')}",
                f"{item.get('confidence', 0):.4f}",
                item.get("x", ""),
                item.get("y", ""),
            ))

        模式 = "模糊" if self.是否模糊.get() else "精确"
        self.设置状态(f"查找完成 ✅ {模式}匹配「{self.关键字.get()}」| 共识别 {总计} 个文字，匹配 {len(匹配)} 个")

    def 清空表格(self):
        for row in self.结果表格.get_children():
            self.结果表格.delete(row)

    def 清空结果(self):
        self.清空表格()
        self.关键字.set("")
        self.设置状态("已清空 ✅")

    def 运行(self):
        self.root.mainloop()


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    工具 = OCR可视工具()
    工具.运行()
