# PaddleOCR API（飞桨文字识别接口）

基于百度飞桨 PaddleOCR 的文字识别 API 服务，支持通过 HTTP 接口远程调用，可部署在云服务器上实现 7×24 小时在线服务。

---

## 一、功能简介

| 功能 | 说明 |
|------|------|
| **OCR 识别** | 上传图片 → 返回图片中所有文字内容、识别精度和坐标位置 |
| **文字查找** | 上传图片 + 指定关键字 → 返回匹配的文字、精度和坐标 |
| **批量识别** 🆕 | 一次上传多张图片，批量返回识别结果 |
| **GPU 加速** 🆕 | 自动检测 GPU（NVIDIA CUDA），优先用 GPU 推理，速度提升 5~10 倍 |
| **API Key 认证** 🆕 | 可选开启 Bearer Token 认证，防止服务被滥用 |

---

## 二、部署方式

### 方式一：云服务器一键部署（推荐）

适用于腾讯云、阿里云、华为云等 Linux 云服务器。

#### 第1步：拉取代码

```bash
git clone https://github.com/15188037938/paddle-ocr-api.git
cd paddle-ocr-api
```

#### 第2步：一键部署

```bash
chmod +x deploy_ocr_server.sh
bash deploy_ocr_server.sh
```

部署脚本会自动完成以下操作：

| 步骤 | 说明 |
|------|------|
| ① 安装系统依赖 | 自动识别 Ubuntu / CentOS，安装 Python3、pip |
| ② 安装 PaddlePaddle | 检测到 NVIDIA GPU 时询问是否安装 GPU 版 |
| ③ 安装 PaddleOCR | 飞桨 OCR 工具包 |
| ④ 安装 HTTP 服务 | uvicorn、fastapi、requests |
| ⑤ 配置开机自启 | 注册 systemd 服务，服务器重启后自动运行 |
| ⑥ 启动服务 | 加载模型并启动 OCR 服务 |
| ⑦ 输出地址 | 打印本地地址和公网地址 |

#### 第3步：放行云服务器端口

登录云服务器控制台，找到 **安全组 / 防火墙** 配置，添加入站规则：

| 协议类型 | 端口号 | 来源 |
|----------|--------|------|
| TCP | 8000 | 0.0.0.0/0（允许所有 IP 访问） |

> 不同厂商入口不同：腾讯云叫"安全组"，阿里云叫"安全组规则"，华为云叫"安全组"，AWS 叫"Security Group"。

#### 第4步：验证部署

浏览器访问 `http://你的服务器IP:8000/`，看到以下 JSON 即部署成功：

```json
{"service":"PaddleOCR API","status":"running","version":"2.1.0"}
```

也可访问 `http://你的服务器IP:8000/docs` 打开 Swagger 交互式文档。

---

### 方式二：本地电脑启动（开发测试用）

#### Windows

直接双击 **`start_ocr.bat`**，脚本会自动安装所有依赖并启动服务。

如需开启认证或 GPU，先在命令行设置环境变量再运行：

```cmd
set API_KEY=my_secret_key
set USE_GPU=true
start_ocr.bat
```

#### Linux / Mac

```bash
# 安装依赖（CPU 版）
pip3 install paddlepaddle "paddleocr==2.10.0" uvicorn fastapi requests python-multipart

# 或 GPU 版
pip3 install paddlepaddle-gpu "paddleocr==2.10.0" uvicorn fastapi requests python-multipart

# 启动服务
API_KEY=my_key USE_GPU=true uvicorn ocr_api:app --host 0.0.0.0 --port 8000
```

---

## 三、服务管理命令

部署完成后，通过以下命令管理服务：

```bash
# 查看服务状态
systemctl status paddle-ocr

# 手动启动
systemctl start paddle-ocr

# 手动停止
systemctl stop paddle-ocr

# 重启服务
systemctl restart paddle-ocr

# 查看实时日志（按 Ctrl+C 退出）
journalctl -u paddle-ocr -f

# 关闭开机自启
systemctl disable paddle-ocr
```

---

## 四、环境变量说明

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `API_KEY` | 空（不开启） | 设置后所有接口需在 Header 加 `Authorization: Bearer <API_KEY>` |
| `USE_GPU` | 空（自动检测） | 设为 `true` / `1` 强制启用 GPU 推理 |

---

## 五、API 接口说明

### 5.1 图片文字识别

**接口地址：** `POST /ocr/upload`

**请求方式：** multipart/form-data

**请求参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| file | 文件 | 是 | 图片文件（支持 jpg/png/bmp 等格式） |

**请求示例：**

```bash
# 未开启认证时
curl -X POST http://你的服务器IP:8000/ocr/upload -F "file=@截图.png"

# 开启认证后需加 Header
curl -X POST http://你的服务器IP:8000/ocr/upload \
  -H "Authorization: Bearer my_secret_key" \
  -F "file=@截图.png"
```

**返回示例：**

```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "text": "线性回归训练效果",
      "confidence": 0.9991,
      "x": 14.0,
      "y": 24.0,
      "x2": 149.0,
      "y2": 24.0
    }
  ]
}
```

### 5.2 文字查找

**接口地址：** `POST /ocr/search`

**请求方式：** multipart/form-data

**请求参数：**

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| file | 文件 | 是 | - | 图片文件 |
| keyword | 字符串 | 是 | - | 要查找的文字 |
| fuzzy | 布尔 | 否 | true | true=模糊匹配（包含即匹配），false=精确匹配 |

**请求示例：**

```bash
# 模糊查找（默认）
curl -X POST http://你的服务器IP:8000/ocr/search \
  -F "file=@截图.png" \
  -F "keyword=回归" \
  -F "fuzzy=true"

# 精确查找
curl -X POST http://你的服务器IP:8000/ocr/search \
  -F "file=@截图.png" \
  -F "keyword=线性回归训练效果" \
  -F "fuzzy=false"
```

**返回示例：**

```json
{
  "code": 0,
  "message": "success",
  "keyword": "回归",
  "total_recognized": 2,
  "matches": [
    {
      "text": "线性回归训练效果",
      "confidence": 0.9991,
      "x": 14.0,
      "y": 24.0,
      "x2": 149.0,
      "y2": 24.0,
      "match_type": "fuzzy"
    }
  ]
}
```

> 未找到匹配文字时，`matches` 返回空数组 `[]`。

### 5.3 批量图片识别 🆕

**接口地址：** `POST /ocr/batch`

**请求方式：** multipart/form-data

**请求参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| files | 文件数组 | 是 | 同时上传多张图片 |

**请求示例：**

```bash
curl -X POST http://你的服务器IP:8000/ocr/batch \
  -F "files=@图片1.png" \
  -F "files=@图片2.png" \
  -F "files=@图片3.png"
```

**返回示例：**

```json
{
  "code": 0,
  "message": "success",
  "total": 3,
  "results": [
    {
      "index": 0,
      "filename": "图片1.png",
      "data": [
        { "text": "第一张图的文字", "confidence": 0.99, "x": 10.0, "y": 20.0, "x2": 100.0, "y2": 20.0 }
      ]
    },
    {
      "index": 1,
      "filename": "图片2.png",
      "data": [
        { "text": "第二张图的文字", "confidence": 0.98, "x": 5.0, "y": 10.0, "x2": 80.0, "y2": 10.0 }
      ]
    }
  ]
}
```

### 返回字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `text` | 字符串 | 识别出的文字内容 |
| `confidence` | 浮点数 | 识别精度（0~1，越接近1越准确） |
| `x` | 浮点数 | 文字左上角的 X 坐标 |
| `y` | 浮点数 | 文字左上角的 Y 坐标 |
| `x2` | 浮点数 | 文字右上角的 X 坐标 |
| `y2` | 浮点数 | 文字右上角的 Y 坐标 |
| `match_type` | 字符串 | 匹配方式：`fuzzy` 模糊匹配 / `exact` 精确匹配 |

---

## 六、调用示例

### Python

```python
import requests

API = "http://你的服务器IP:8000"
HEADERS = {"Authorization": "Bearer my_secret_key"}  # 开启认证时需要

# 1. OCR 识别
resp = requests.post(f"{API}/ocr/upload", files={"file": open("图片.png", "rb")}, headers=HEADERS)
data = resp.json()["data"]
for item in data:
    print(f"文字: {item['text']}, 精度: {item['confidence']}, 坐标: ({item['x']},{item['y']})")

# 2. 查找文字
resp = requests.post(
    f"{API}/ocr/search",
    files={"file": open("图片.png", "rb")},
    data={"keyword": "回归", "fuzzy": "true"},
    headers=HEADERS
)
for match in resp.json()["matches"]:
    print(f"匹配: {match['text']}, 精度: {match['confidence']}")

# 3. 批量识别
files = [("files", open("图1.png", "rb")), ("files", open("图2.png", "rb"))]
resp = requests.post(f"{API}/ocr/batch", files=files, headers=HEADERS)
for result in resp.json()["results"]:
    print(f"[{result['filename']}] 识别到 {len(result['data'])} 个文字")
```

### Windows PowerShell (curl.exe)

```powershell
# 识别（未开启认证）
curl.exe -X POST http://你的服务器IP:8000/ocr/upload -F "file=@D:\图片.png"

# 识别（开启认证）
curl.exe -X POST http://你的服务器IP:8000/ocr/upload -H "Authorization: Bearer my_secret_key" -F "file=@D:\图片.png"

# 查找
curl.exe -X POST http://你的服务器IP:8000/ocr/search -F "file=@D:\图片.png" -F "keyword=回归" -F "fuzzy=true"

# 批量
curl.exe -X POST http://你的服务器IP:8000/ocr/batch -F "files=@D:\图1.png" -F "files=@D:\图2.png"
```

### 易语言

```e
.版本 2
.支持库 spec

.子程序 OCR识别
.局部变量 WinHttp, 对象
.局部变量 地址, 文本型

地址 ＝ “http://你的服务器IP:8000/ocr/upload”

' 推荐使用 WinHttp.WinHttpRequest.5.1 发送 POST 请求
' 上传文件需构造 multipart/form-data 格式
' 如果开启了认证，在请求头添加：Authorization: Bearer my_secret_key

' 解析返回 JSON：
' json.取通用属性 ("data[0].text")          → 文字
' json.取通用属性 ("data[0].confidence")     → 精度
' json.取通用属性 ("data[0].x")             → 左上X
' json.取通用属性 ("data[0].y")             → 左上Y
' json.取通用属性 ("data[0].x2")            → 右上X
' json.取通用属性 ("data[0].y2")            → 右上Y
```

---

## 七、常见问题

**Q：部署脚本执行报错 "command not found"？**
A：部分云服务器未安装 git，先执行 `yum install -y git`（CentOS）或 `apt install -y git`（Ubuntu）。

**Q：服务启动后外网无法访问？**
A：检查云服务器 **安全组/防火墙** 是否放行了 **8000 端口**，确认来源为 `0.0.0.0/0`。

**Q：服务占用内存多大？**
A：PaddleOCR 加载模型后占用约 500MB~1GB 内存，建议云服务器配置 2GB 以上。

**Q：如何开启 GPU 加速？**
A：在启动前设置环境变量 `USE_GPU=true`，或在部署脚本中选择 GPU 版安装。需提前安装 NVIDIA 驱动和 CUDA 工具包。

**Q：如何开启 API Key 认证？**
A：在启动前设置环境变量 `API_KEY=你的密钥`，之后所有请求都需要在 Header 中加 `Authorization: Bearer 你的密钥`。

**Q：如何更新代码？**
A：进入项目目录执行 `git pull` 拉取最新代码，然后 `systemctl restart paddle-ocr` 重启服务。

**Q：想换端口号？**
A：修改 `deploy_ocr_server.sh` 中的 `--port 8000` 为你想要的端口，重新部署即可。

---

## 八、文件说明

| 文件 | 说明 |
|------|------|
| `ocr_api.py` | API 服务主程序（核心文件） |
| `deploy_ocr_server.sh` | **云服务器一键部署脚本**（含 GPU 检测和开机自启） |
| `start_ocr.sh` | Linux 一键启动脚本（含自动装依赖和公网隧道） |
| `start_ocr.bat` | Windows 一键启动脚本（双击运行，支持 GPU/API_KEY） |
| `调用OCR_API示例.py` | Python 调用示例 |
