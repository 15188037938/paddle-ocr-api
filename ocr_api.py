"""
PaddleOCR API 服务
启动: uvicorn ocr_api:app --host 0.0.0.0 --port 8000
"""

import os
import uuid
import tempfile

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from paddleocr import PaddleOCR

# ============================================================
# 初始化
# ============================================================
app = FastAPI(title="PaddleOCR API", version="2.0.0", description="飞桨OCR文字识别接口")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)

# ============================================================
# 数据模型
# ============================================================
class OCRItem(BaseModel):
    text: str
    confidence: float
    x: float   # 左上角 X
    y: float   # 左上角 Y
    x2: float  # 右上角 X
    y2: float  # 右上角 Y

class OCRResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: list[OCRItem] = []

class SearchItem(BaseModel):
    text: str
    confidence: float
    x: float   # 左上角 X
    y: float   # 左上角 Y
    x2: float  # 右上角 X
    y2: float  # 右上角 Y
    match_type: str = "fuzzy"

class SearchResponse(BaseModel):
    code: int = 0
    message: str = "success"
    keyword: str = ""
    total_recognized: int = 0
    matches: list[SearchItem] = []

# ============================================================
# 核心逻辑
# ============================================================
def _location_to_xy(loc: list) -> dict:
    """将 OCR 返回的 4 点坐标转为左上+右上 xy。"""
    # loc: [[左上x,左上y], [右上x,右上y], [右下x,右下y], [左下x,左下y]]
    return {
        "x": round(loc[0][0], 1),
        "y": round(loc[0][1], 1),
        "x2": round(loc[1][0], 1),
        "y2": round(loc[1][1], 1),
    }

def _do_ocr(img_path: str) -> list[dict]:
    """执行 OCR 识别，返回精简结果列表。"""
    result = ocr.ocr(img_path, cls=True)
    items = []
    if result[0] is None:
        return items
    for line in result[0]:
        text = line[1][0]
        conf = round(line[1][1], 4)
        xy = _location_to_xy(line[0])
        items.append({"text": text, "confidence": conf, **xy})
    return items

def _read_image(content: bytes, filename: str = "image.jpg") -> str:
    """保存上传文件到临时路径。"""
    suffix = os.path.splitext(filename)[1] or ".jpg"
    tmp = os.path.join(tempfile.gettempdir(), f"ocr_{uuid.uuid4().hex}{suffix}")
    with open(tmp, "wb") as f:
        f.write(content)
    return tmp

# ============================================================
# 接口：OCR 识别
# ============================================================
@app.get("/")
def root():
    return {"service": "PaddleOCR API", "status": "running", "version": "2.0.0"}

@app.post("/ocr/upload", summary="上传图片识别")
async def ocr_upload(file: UploadFile = File(..., description="图片文件")):
    """上传图片，返回所有识别到的文字（含精度、左上X/Y、右上X2/Y2）。"""
    content = await file.read()
    tmp = _read_image(content, file.filename or "image.jpg")
    try:
        items = _do_ocr(tmp)
        return OCRResponse(data=[OCRItem(**it) for it in items])
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

# ============================================================
# 接口：查找文字
# ============================================================
@app.post("/ocr/search", summary="上传图片并查找指定文字")
async def search_upload(
    file: UploadFile = File(..., description="图片文件"),
    keyword: str = Form(..., description="要查找的文字"),
    fuzzy: bool = Form(True, description="true=模糊匹配(包含即匹配)，false=完全一致")
):
    """上传图片，在识别结果中查找指定文字，返回匹配项的文字、精度和坐标。"""
    content = await file.read()
    tmp = _read_image(content, file.filename or "image.jpg")
    try:
        items = _do_ocr(tmp)
        matches = []
        for item in items:
            if fuzzy:
                if keyword in item["text"]:
                    matches.append(SearchItem(**item, match_type="fuzzy"))
            else:
                if item["text"] == keyword:
                    matches.append(SearchItem(**item, match_type="exact"))
        return SearchResponse(
            keyword=keyword,
            total_recognized=len(items),
            matches=matches
        )
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
