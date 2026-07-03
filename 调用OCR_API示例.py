"""
PaddleOCR API 调用示例 - v2.1.0
GPU + 批量识别 + API Key 认证
"""

import requests

API = "http://127.0.0.1:8000"

# —— 如开启了 API Key 认证，替换下面的密钥 ——
# HEADERS = {"Authorization": "Bearer your_secret_key"}
HEADERS = {}


def demo_ocr_upload():
    """示例1：OCR 识别一张图片"""
    print("=" * 50)
    print("1. OCR 识别")
    print("=" * 50)

    resp = requests.post(
        f"{API}/ocr/upload",
        files={"file": open("图片.png", "rb")},
        headers=HEADERS,
    )
    data = resp.json()["data"]
    for item in data:
        print(f"  文字: {item['text']}")
        print(f"  精度: {item['confidence']}")
        print(f"  坐标: ({item['x']},{item['y']}) → ({item['x2']},{item['y2']})")
        print()


def demo_ocr_search():
    """示例2：在图片中查找指定文字"""
    print("=" * 50)
    print("2. 文字查找")
    print("=" * 50)

    resp = requests.post(
        f"{API}/ocr/search",
        files={"file": open("图片.png", "rb")},
        data={"keyword": "回归", "fuzzy": "true"},
        headers=HEADERS,
    )
    result = resp.json()
    print(f"  关键字: {result['keyword']}")
    print(f"  图片中共识别到: {result['total_recognized']} 个文字")
    print(f"  匹配到: {len(result['matches'])} 个")
    for match in result["matches"]:
        print(f"    → {match['text']} (精度: {match['confidence']}, 匹配方式: {match['match_type']})")


def demo_ocr_batch():
    """示例3：批量识别多张图片"""
    print("=" * 50)
    print("3. 批量识别")
    print("=" * 50)

    files = [
        ("files", open("图片1.png", "rb")),
        ("files", open("图片2.png", "rb")),
    ]
    resp = requests.post(
        f"{API}/ocr/batch",
        files=files,
        headers=HEADERS,
    )
    result = resp.json()
    print(f"  共处理 {result['total']} 张图片")
    for item in result["results"]:
        print(f"\n  [{item['filename']}] 识别到 {len(item['data'])} 个文字:")
        for t in item["data"]:
            print(f"    - {t['text']}")


if __name__ == "__main__":
    # 先检查服务是否在线
    try:
        r = requests.get(f"{API}/", headers=HEADERS, timeout=5)
        print(f"服务状态: {r.json()}\n")
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接服务 {API}，请确认服务已启动")
        exit(1)

    demo_ocr_upload()
    demo_ocr_search()
    demo_ocr_batch()
