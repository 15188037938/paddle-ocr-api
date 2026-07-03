"""
PaddleOCR API Python 调用示例

使用前提：先启动 OCR 服务
  uvicorn ocr_api:app --host 0.0.0.0 --port 8000 --app-dir /root/.codebuddy/skills/paddle-ocr

依赖：requests（pip install requests）
"""

import requests

API_BASE = "http://localhost:8000"

# ============================================================
# 1. OCR 识别：上传图片，返回所有文字
# ============================================================
def ocr_recognize(image_path: str) -> list[dict]:
    """识别图片中的所有文字。"""
    resp = requests.post(
        f"{API_BASE}/ocr/upload",
        files={"file": open(image_path, "rb")}
    )
    resp.raise_for_status()
    return resp.json()["data"]

# ============================================================
# 2. 查找文字：上传图片 + 关键字，返回匹配项
# ============================================================
def ocr_search(image_path: str, keyword: str, fuzzy: bool = True) -> list[dict]:
    """在图片中查找指定文字。"""
    resp = requests.post(
        f"{API_BASE}/ocr/search",
        files={"file": open(image_path, "rb")},
        data={"keyword": keyword, "fuzzy": str(fuzzy).lower()}
    )
    resp.raise_for_status()
    return resp.json()["matches"]

# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    img = r"/root/uploads/1783008592739026708-1783008581208-6w8szdfr-Clipboard_Screenshot.png"

    # ——— 示例1：OCR 识别 ———
    print("=" * 50)
    print("1. OCR 识别 - 全部文字")
    print("=" * 50)
    items = ocr_recognize(img)
    for item in items:
        print(f"  文字  ：{item['text']}")
        print(f"  精度  ：{item['confidence']}")
        print(f"  左上   ：({item['x']}, {item['y']})")
        print(f"  右上   ：({item['x2']}, {item['y2']})")
        print("-" * 40)

    # ——— 示例2：模糊查找 ———
    keyword = "回归"
    print(f"\n{'=' * 50}")
    print(f"2. 查找文字 - 模糊查找「{keyword}」")
    print("=" * 50)
    matches = ocr_search(img, keyword, fuzzy=True)
    if matches:
        for m in matches:
            print(f"  匹配  ：{m['text']}")
            print(f"  精度  ：{m['confidence']}")
            print(f"  左上   ：({m['x']}, {m['y']})")
            print(f"  右上   ：({m['x2']}, {m['y2']})")
            print(f"  匹配方式：{m['match_type']}")
    else:
        print("  未匹配到任何文字")
    print("-" * 40)

    # ——— 示例3：精确查找 ———
    keyword2 = "线性回归训练效果"
    print(f"\n{'=' * 50}")
    print(f"3. 查找文字 - 精确查找「{keyword2}」")
    print("=" * 50)
    matches2 = ocr_search(img, keyword2, fuzzy=False)
    if matches2:
        for m in matches2:
            print(f"  匹配  ：{m['text']}")
            print(f"  精度  ：{m['confidence']}")
            print(f"  坐标   ：左上({m['x']},{m['y']})  右上({m['x2']},{m['y2']})")
    else:
        print("  未匹配到")
    print("-" * 40)

    # ——— 示例4：查找不存在的文字 ———
    keyword3 = "不存在的文字"
    print(f"\n{'=' * 50}")
    print(f"4. 查找文字 - 查不到「{keyword3}」")
    print("=" * 50)
    matches3 = ocr_search(img, keyword3, fuzzy=True)
    print(f"  matches 数量：{len(matches3)}")
    print(f"  结果：{'未找到' if len(matches3) == 0 else '找到'}")
    print("=" * 50)
