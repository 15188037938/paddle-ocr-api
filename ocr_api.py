"""
PaddleOCR API 服务 - v2.1.0
启动: uvicorn ocr_api:app --host 0.0.0.0 --port 8000

新功能：
  - API Key 认证（通过环境变量 API_KEY 设置，不设置则不开启）
  - GPU 自动检测加速
  - 批量图片识别接口
"""

import os
import re
import uuid
import base64
import tempfile
import logging

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from paddleocr import PaddleOCR

logger = logging.getLogger("paddle-ocr-api")

# ============================================================
# 配置
# ============================================================
API_KEY = os.environ.get("API_KEY", "")  # 设了就需要 Bearer Token 认证
USE_GPU = os.environ.get("USE_GPU", "").lower() in ("1", "true", "yes")

# ============================================================
# 初始化
# ============================================================
app = FastAPI(title="PaddleOCR API", version="2.1.0", description="飞桨OCR文字识别接口")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ----- 认证 -----
security = HTTPBearer(auto_error=False)

def verify_auth(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    """如果开启了 API_KEY，则检查 Bearer Token。"""
    if not API_KEY:
        return  # 没设 KEY，不开启认证
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少认证信息")
    if credentials.credentials != API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API Key 无效")
    return

# ----- 检测 GPU -----
import paddle

def _detect_gpu() -> bool:
    """检测 GPU 是否可用。优先用环境变量，其次自动检测。"""
    if USE_GPU:
        logger.info("环境变量 USE_GPU 已启用，强制使用 GPU 模式")
        return True
    try:
        if paddle.is_compiled_with_cuda():
            gpu_count = paddle.device.cuda.device_count()
            if gpu_count > 0:
                gpu_name = paddle.device.cuda.get_device_name(0)
                logger.info(f"检测到 GPU: {gpu_name} ({gpu_count} 张)")
                return True
            else:
                logger.info("Paddle 已编译 CUDA 但未检测到 GPU 设备")
        else:
            logger.info("Paddle 未编译 CUDA，使用 CPU 模式")
    except Exception as e:
        logger.warning(f"GPU 检测异常: {e}，回退 CPU")
    return False

has_gpu = _detect_gpu()
logger.info(f"OCR 推理设备: {'GPU' if has_gpu else 'CPU'}")
ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False, use_gpu=has_gpu)

# ============================================================
# 数据模型
# ============================================================
class OCRItem(BaseModel):
    text: str
    confidence: float
    x: float   # 文字左上角 X 坐标
    y: float   # 文字左上角 Y 坐标

class OCRResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: list[OCRItem] = []

class SearchItem(BaseModel):
    text: str
    confidence: float
    x: float   # 文字左上角 X 坐标
    y: float   # 文字左上角 Y 坐标
    match_type: str = "fuzzy"

class SearchResponse(BaseModel):
    code: int = 0
    message: str = "success"
    keyword: str = ""
    total_recognized: int = 0
    matches: list[SearchItem] = []

class BatchItem(BaseModel):
    index: int
    filename: str
    data: list[OCRItem]

class BatchResponse(BaseModel):
    code: int = 0
    message: str = "success"
    total: int = 0
    results: list[BatchItem] = []

# ----- Base64 请求模型 -----
class OCRBase64Request(BaseModel):
    image: str       # 图片 base64（可含 data:image/xxx;base64, 前缀）
    filename: str = "image.png"  # 文件名（用于后缀识别）

class SearchBase64Request(BaseModel):
    image: str       # 图片 base64
    keyword: str     # 要查找的文字
    fuzzy: bool = True  # 是否模糊匹配
    filename: str = "image.png"

# ============================================================
# 核心逻辑
# ============================================================
def _location_to_xy(loc: list) -> dict:
    """将 OCR 返回的 4 点坐标转为左上角 (x, y)。"""
    # loc: [[左上x,左上y], [右上x,右上y], [右下x,右下y], [左下x,左下y]]
    return {
        "x": round(loc[0][0], 1),
        "y": round(loc[0][1], 1),
    }

def _do_ocr(img_path: str) -> list[dict]:
    """执行 OCR 识别，返回精简结果列表。"""
    try:
        result = ocr.ocr(img_path, cls=True)
    except Exception as e:
        logger.error(f"OCR 识别失败: {e}")
        raise
    items = []
    if result is None or result[0] is None:
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
# 接口：根路径
# ============================================================
@app.get("/")
def root():
    return {
        "service": "PaddleOCR API",
        "status": "running",
        "version": "2.1.0",
        "auth_required": bool(API_KEY),
        "gpu_enabled": has_gpu,
    }

# ============================================================
# 接口：OCR 识别单张
# ============================================================
@app.post("/ocr/upload", summary="上传图片识别", dependencies=[Depends(verify_auth)])
async def ocr_upload(file: UploadFile = File(..., description="图片文件")):
    """上传图片，返回所有识别到的文字（含精度、坐标X/Y）。"""
    content = await file.read()
    tmp = _read_image(content, file.filename or "image.jpg")
    try:
        items = _do_ocr(tmp)
        return OCRResponse(data=[OCRItem(**it) for it in items])
    except Exception as e:
        logger.error(f"OCR 接口异常: {e}", exc_info=True)
        return {"code": -1, "message": f"OCR 识别失败: {str(e)}", "data": []}
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except: pass

# ============================================================
# 接口：查找文字
# ============================================================
@app.post("/ocr/search", summary="上传图片并查找指定文字", dependencies=[Depends(verify_auth)])
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
    except Exception as e:
        logger.error(f"搜索接口异常: {e}", exc_info=True)
        return {"code": -1, "message": f"搜索失败: {str(e)}", "keyword": keyword, "total_recognized": 0, "matches": []}
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except: pass

# ============================================================
# 接口：批量 OCR 识别
# ============================================================
@app.post("/ocr/batch", summary="批量上传图片识别", dependencies=[Depends(verify_auth)])
async def ocr_batch(files: list[UploadFile] = File(..., description="多张图片文件")):
    """同时上传多张图片，批量识别，返回每张图片的文字结果。"""
    results = []
    for idx, file in enumerate(files):
        content = await file.read()
        tmp = _read_image(content, file.filename or f"image_{idx}.jpg")
        try:
            items = _do_ocr(tmp)
            results.append(BatchItem(
                index=idx,
                filename=file.filename or f"image_{idx}",
                data=[OCRItem(**it) for it in items]
            ))
        except Exception as e:
            logger.error(f"批量识别第 {idx} 张图片失败: {e}", exc_info=True)
            results.append(BatchItem(index=idx, filename=file.filename or f"image_{idx}", data=[]))
        finally:
            if os.path.exists(tmp):
                try: os.remove(tmp)
                except: pass
    return BatchResponse(total=len(results), results=results)

def _parse_base64_image(image_b64: str) -> bytes:
    """解析 base64 图片，支持带 data:image/xxx;base64, 前缀的格式。"""
    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]
    # 去掉空白字符
    image_b64 = re.sub(r"\s+", "", image_b64)
    return base64.b64decode(image_b64)

# ============================================================
# 接口：Base64 图片识别（易语言友好）
# ============================================================
@app.post("/ocr/base64", summary="Base64图片识别", dependencies=[Depends(verify_auth)])
async def ocr_base64(req: OCRBase64Request):
    """传 base64 图片，返回所有识别到的文字。适合易语言等不方便上传文件的场景。"""
    try:
        content = _parse_base64_image(req.image)
    except Exception as e:
        return {"code": -1, "message": f"Base64 解码失败: {str(e)}", "data": []}

    tmp = _read_image(content, req.filename)
    try:
        items = _do_ocr(tmp)
        return OCRResponse(data=[OCRItem(**it) for it in items])
    except Exception as e:
        logger.error(f"OCR 接口异常: {e}", exc_info=True)
        return {"code": -1, "message": f"OCR 识别失败: {str(e)}", "data": []}
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except: pass

@app.post("/ocr/search/base64", summary="Base64图片查找文字", dependencies=[Depends(verify_auth)])
async def search_base64(req: SearchBase64Request):
    """传 base64 图片，在识别结果中查找指定文字。"""
    try:
        content = _parse_base64_image(req.image)
    except Exception as e:
        return {"code": -1, "message": f"Base64 解码失败: {str(e)}", "keyword": req.keyword, "total_recognized": 0, "matches": []}

    tmp = _read_image(content, req.filename)
    try:
        items = _do_ocr(tmp)
        matches = []
        for item in items:
            if req.fuzzy:
                if req.keyword in item["text"]:
                    matches.append(SearchItem(**item, match_type="fuzzy"))
            else:
                if item["text"] == req.keyword:
                    matches.append(SearchItem(**item, match_type="exact"))
        return SearchResponse(keyword=req.keyword, total_recognized=len(items), matches=matches)
    except Exception as e:
        logger.error(f"搜索接口异常: {e}", exc_info=True)
        return {"code": -1, "message": f"搜索失败: {str(e)}", "keyword": req.keyword, "total_recognized": 0, "matches": []}
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except: pass
if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info(f"API Key 认证: {'已开启' if API_KEY else '未开启（开放访问）'}")
    logger.info(f"GPU 加速: {'已启用' if has_gpu else '未启用（使用 CPU）'}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
