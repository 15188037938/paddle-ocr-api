# PaddleOCR API

基于飞桨 PaddleOCR 的文字识别 API 服务，支持 HTTP 远程调用。

## 功能

- **OCR 识别**：上传图片，返回文字内容、精度和坐标
- **文字查找**：上传图片并指定关键字，返回匹配结果

## 一键部署（云服务器）

```bash
chmod +x deploy_ocr_server.sh
bash deploy_ocr_server.sh
```

脚本自动安装所有依赖并配置开机自启。

## 本地启动

```bash
# Linux / Mac
pip install paddlepaddle "paddleocr==2.10.0" uvicorn fastapi requests python-multipart
uvicorn ocr_api:app --host 0.0.0.0 --port 8000
```

Windows 直接双击 `start_ocr.bat`。

## API 接口

### POST /ocr/upload — 上传图片识别

```
curl -X POST http://服务器IP:8000/ocr/upload -F "file=@图片.png"
```

### POST /ocr/search — 查找文字

```
curl -X POST http://服务器IP:8000/ocr/search -F "file=@图片.png" -F "keyword=回归" -F "fuzzy=true"
```

| 参数 | 说明 |
|------|------|
| `keyword` | 要查找的文字 |
| `fuzzy` | `true`=模糊匹配，`false`=精确匹配 |

## 返回格式

```json
{
  "code": 0,
  "data": [
    {
      "text": "识别文字",
      "confidence": 0.9991,
      "x": 14.0,
      "y": 24.0,
      "x2": 149.0,
      "y2": 24.0
    }
  ]
}
```

- `x`, `y` — 左上角坐标
- `x2`, `y2` — 右上角坐标

## 文件说明

| 文件 | 用途 |
|------|------|
| `ocr_api.py` | API 服务主程序 |
| `deploy_ocr_server.sh` | 云服务器一键部署脚本（Ubuntu/CentOS） |
| `start_ocr.sh` | Linux 一键启动脚本 |
| `start_ocr.bat` | Windows 一键启动脚本 |
| `调用OCR_API示例.py` | Python 调用示例 |
