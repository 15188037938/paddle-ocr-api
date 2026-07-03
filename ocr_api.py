"""
PaddleOCR API 服务 - v2.2.0
启动: uvicorn ocr_api:app --host 0.0.0.0 --port 8000

集成引擎：
  - PaddleOCR:  多行文本识别 / 关键字查找 / 批量识别
  - ddddocr:    单行文本 / 验证码 / 目标检测 / 滑块匹配
"""

import os
# 解决 ddddocr 与 PaddlePaddle 的 protobuf 版本冲突
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

import re
import uuid
import base64
import tempfile
import logging

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
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
app = FastAPI(
    title="PaddleOCR API",
    version="2.2.0",
    description="飞桨OCR + ddddocr 文字识别 / 验证码 / 目标检测 / 滑块匹配",
    docs_url=None,
    redoc_url=None,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ============================================================
# 自定义中文 Swagger UI
# ============================================================
@app.get("/docs", include_in_schema=False)
async def custom_docs():
    html = get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="PaddleOCR API 文档",
        swagger_ui_parameters={
            "displayLang": "zh-cn",
            "tryItOutEnabled": True,
            "defaultModelsExpandDepth": 1,
            "displayRequestDuration": True,
        },
    )
    # get_swagger_ui_html 返回的是 HTMLResponse 对象，需要先取 body
    html_content = html.body.decode() if hasattr(html, 'body') else str(html)
    script = """
    <script>
    (function() {
        const dict = {
            'Parameters': '参数',
            'Responses': '响应',
            'Request body': '请求体',
            'No parameters': '无参数',
            'Try it out': '试用',
            'Cancel': '取消',
            'Execute': '执行',
            'Clear': '清空',
            'Required': '必填',
            'Optional': '选填',
            'Description': '描述',
            'Example': '示例',
            'Value': '值',
            'Schema': '结构',
            'Response body': '响应体',
            'Response headers': '响应头',
            'Authorizations': '认证',
            'Loading': '加载中',
            'Failed to load API definition.': 'API 定义加载失败。',
            'Available authorizations': '可用认证方式',
            'string': '字符串',
            'boolean': '布尔值',
            'integer': '整数',
            'number': '数字',
            'array': '数组',
            'object': '对象',
            'file': '文件',
            'multipart/form-data': '文件上传',
            'application/json': 'JSON',
            'true': '是',
            'false': '否',
        };
        function translate(node) {
            if (node.nodeType === 3) {
                let t = node.textContent.trim();
                if (dict[t]) {
                    node.textContent = node.textContent.replace(t, dict[t]);
                }
            } else if (node.nodeType === 1) {
                if (node.placeholder && dict[node.placeholder]) node.placeholder = dict[node.placeholder];
                if (node.tagName === 'BUTTON' && dict[node.textContent.trim()]) node.textContent = dict[node.textContent.trim()];
                if (node.tagName === 'TH' && dict[node.textContent.trim()]) node.textContent = dict[node.textContent.trim()];
                if (node.tagName === 'SPAN' && node.className && node.className.includes('model') && dict[node.textContent.trim()]) node.textContent = dict[node.textContent.trim()];
                for (let c of node.childNodes) translate(c);
            }
        }
        translate(document.body);
        new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => translate(n))))
            .observe(document.body, { childList: true, subtree: true });
    })();
    </script>
    """
    return HTMLResponse(content=html_content.replace("</body>", script + "</body>"))

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
# ddddocr 引擎（轻量OCR/验证码/目标检测）
# ============================================================
HAS_DDDD = False
dddd_ocr = None
dddd_det = None
dddd_slide = None

try:
    import ddddocr
    dddd_ocr = ddddocr.DdddOcr()
    dddd_det = ddddocr.DdddOcr(det=True, ocr=False)
    dddd_slide = ddddocr.DdddOcr(det=False, ocr=False)
    HAS_DDDD = True
    logger.info("ddddocr 引擎加载成功 ✅（验证码/目标检测/滑块匹配）")
except Exception as e:
    logger.warning(f"ddddocr 加载失败（不影响 PaddleOCR）: {e}")

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
        "version": "2.2.0",
        "auth_required": bool(API_KEY),
        "gpu_enabled": has_gpu,
        "engines": {
            "paddleocr": True,
            "ddddocr": HAS_DDDD,
        },
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

# ============================================================
# ddddocr 接口（验证码 / 单行文字 / 目标检测 / 滑块）
# ============================================================
@app.get("/dddd/status", summary="ddddocr 引擎状态", dependencies=[Depends(verify_auth)])
def dddd_status():
    """查询 ddddocr 引擎是否可用。"""
    return {
        "code": 0,
        "available": HAS_DDDD,
        "features": ["ocr", "detection", "slide_match"] if HAS_DDDD else [],
    }

class DdddOCRRequest(BaseModel):
    image: str  # base64

class DdddOCRResponse(BaseModel):
    code: int = 0
    message: str = "success"
    text: str = ""
    engine: str = "ddddocr"

class DdddDetRequest(BaseModel):
    image: str  # base64

class DdddDetItem(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

class DdddDetResponse(BaseModel):
    code: int = 0
    message: str = "success"
    boxes: list[DdddDetItem] = []
    engine: str = "ddddocr"

class DdddSlideRequest(BaseModel):
    target_image: str  # 滑块图 base64
    background_image: str  # 背景图 base64
    algo: str = "match"  # "match" 或 "comparison"

class DdddSlideResponse(BaseModel):
    code: int = 0
    message: str = "success"
    target: list[float] = []  # [x1,y1,x2,y2] 或 [x,y]
    engine: str = "ddddocr"


@app.post("/dddd/ocr", summary="ddddocr 文字识别", dependencies=[Depends(verify_auth)])
async def dddd_ocr_api(req: DdddOCRRequest):
    """用 ddddocr 识别单行文字 / 验证码。适合短文本、验证码场景。"""
    if not HAS_DDDD:
        return {"code": -1, "message": "ddddocr 未安装，请执行: pip install ddddocr", "text": ""}
    try:
        img_bytes = _parse_base64_image(req.image)
    except Exception as e:
        return {"code": -1, "message": f"Base64 解码失败: {e}", "text": ""}
    try:
        text = dddd_ocr.classification(img_bytes)
        return DdddOCRResponse(text=text)
    except Exception as e:
        logger.error(f"ddddocr 识别异常: {e}", exc_info=True)
        return {"code": -1, "message": f"识别失败: {e}", "text": ""}


@app.post("/dddd/det", summary="ddddocr 目标检测", dependencies=[Depends(verify_auth)])
async def dddd_det_api(req: DdddDetRequest):
    """检测图片中的目标位置，返回边界框坐标。"""
    if not HAS_DDDD:
        return {"code": -1, "message": "ddddocr 未安装"}
    try:
        img_bytes = _parse_base64_image(req.image)
    except Exception as e:
        return {"code": -1, "message": f"Base64 解码失败: {e}", "boxes": []}
    try:
        boxes = dddd_det.detection(img_bytes)
        items = [DdddDetItem(x1=b[0], y1=b[1], x2=b[2], y2=b[3]) for b in boxes]
        return DdddDetResponse(boxes=items)
    except Exception as e:
        logger.error(f"ddddocr 检测异常: {e}", exc_info=True)
        return {"code": -1, "message": f"检测失败: {e}", "boxes": []}


@app.post("/dddd/slide", summary="ddddocr 滑块匹配", dependencies=[Depends(verify_auth)])
async def dddd_slide_api(req: DdddSlideRequest):
    """滑块验证码匹配。支持两种算法:
    - match: 边缘匹配（适用于有透明背景的滑块图）
    - comparison: 图像差异比较
    """
    if not HAS_DDDD:
        return {"code": -1, "message": "ddddocr 未安装", "target": []}
    try:
        target_bytes = _parse_base64_image(req.target_image)
        bg_bytes = _parse_base64_image(req.background_image)
    except Exception as e:
        return {"code": -1, "message": f"Base64 解码失败: {e}", "target": []}
    try:
        if req.algo == "comparison":
            result = dddd_slide.slide_comparison(target_bytes, bg_bytes)
        else:
            result = dddd_slide.slide_match(target_bytes, bg_bytes)
        return DdddSlideResponse(target=result.get("target", []))
    except Exception as e:
        logger.error(f"ddddocr 滑块异常: {e}", exc_info=True)
        return {"code": -1, "message": f"滑块匹配失败: {e}", "target": []}

if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info(f"API Key 认证: {'已开启' if API_KEY else '未开启（开放访问）'}")
    logger.info(f"GPU 加速: {'已启用' if has_gpu else '未启用（使用 CPU）'}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
