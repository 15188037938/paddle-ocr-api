---
name: paddle-ocr
description: PaddleOCR（飞桨OCR）图片文字识别工具。用户上传图片或提供图片路径时，调用飞桨OCR进行文字检测与识别。支持中英文识别、方向检测。触发关键词：OCR、文字识别、图片识别、飞桨OCR、paddleocr、扫描图片文字。
allowed-tools: Read, Write, Bash
---

# PaddleOCR 图片文字识别 Skill

使用飞桨 OCR（PaddleOCR）对图片进行文字检测与识别。

## ⛔ 重要约束

1. **永远不要直接构造模型下载链接或猜测模型文件名** —— 模型由 `PaddleOCR` 库自动下载管理
2. **必须先确认 PaddleOCR 已安装**，未安装则通过 pip 安装 `paddleocr==2.10.0`
3. **调用完成后必须将识别结果返回给用户**

## 使用流程

### 第一步：检查/安装 PaddleOCR

```bash
python3 -c "import paddleocr" 2>/dev/null || pip3 install paddleocr==2.10.0
```

如果尚未安装 `paddlepaddle`，也需要先安装：
```bash
python3 -c "import paddle" 2>/dev/null || pip3 install paddlepaddle
```

### 第二步：执行 OCR 识别

创建 Python 脚本或直接执行：

```python
from paddleocr import PaddleOCR

# 初始化 OCR（自动下载模型）
ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)

# 识别图片
img_path = '图片路径'  # 替换为实际图片路径
result = ocr.ocr(img_path, cls=True)

# 输出结果
for line in result[0]:
    text = line[1][0]
    confidence = line[1][1]
    print(f"文字: {text}")
    print(f"置信度: {confidence:.4f}")
    print()
```

### 第三步：返回识别结果

以表格形式向用户展示识别的文字内容和置信度。

## 参数说明

- `lang`: 语言，`'ch'` 中文，`'en'` 英文，`'ch_eng'` 中英文混合
- `use_angle_cls`: 是否启用文字方向分类（默认 `True`）
- `show_log`: 是否显示下载日志（默认 `False`）

## 输出格式

```
| 识别文字 | 置信度 |
|----------|--------|
| xxx      | 99.91% |
```
