# OpenStory Launcher 使用教程

## 简介

**OpenStory Launcher** 是 OpenStory 项目的官方游戏客户端，提供一站式的游戏下载、管理与启动体验。您无需手动配置任何运行环境——下载即用，一键启动。

> **⚠️ 注意：目前仅支持 Windows 系统。**

---

# 第一部分：使用指南

## 1. 下载客户端

前往 [https://github.com/ZJU-LLMs/OpenStory/releases](https://github.com/ZJU-LLMs/OpenStory/releases)，找到最新版本，下载对应的客户端 exe 文件。

![下载客户端](asset/0.png)

---

## 2. 启动客户端

下载完成后，**双击下载的 exe 文件**，等待几秒，客户端自动启动，无需安装。

![启动客户端](asset/1.png)

---

## 3. 主界面概览

客户端启动后默认进入 **关于** 页面，展示 OpenStory 项目介绍与最新动态。左侧导航栏包含五个功能模块：

- **关于** — 项目介绍与动态
- **商店** — 浏览与下载游戏
- **库** — 管理已安装游戏
- **下载** — 实时查看下载进度
- **设置** — 个性化配置

![主界面](asset/2.png)

---

## 4. 在商店浏览游戏

点击左侧 **"商店"**，可以看到所有可用的游戏列表，包含封面、名称和简要描述。

![商店界面](asset/3.png)

---

## 5. 查看游戏详情

**单击任意游戏卡片**，弹出该游戏的详细介绍页，包含完整描述、版本信息与下载按钮。

![游戏详情](asset/4.png)

---

## 6. 个性化设置

点击左侧 **"设置"**，可以按需配置以下选项：

- **页面风格**：深色 / 浅色主题切换
- **语言**：中文 / English 切换
- **下载路径**：自定义游戏安装目录（点击"更改"选择文件夹）

![设置界面](asset/5.png)

---

## 7. 下载游戏

在商店或详情页点击 **"下载"** 后，切换到 **"下载"** 页面，可实时查看下载与安装进度。客户端会自动下载游戏包并完成本地解压。

![下载进度](asset/6.png)

---

## 8. 游戏自动入库

下载完成后，客户端自动完成本地环境配置，游戏随即出现在 **"库"** 中，无需任何手动操作。

![游戏入库](asset/7.png)

---

## 9. 启动游戏

在 **"库"** 中找到目标游戏，点击 **"启动"** 按钮，游戏立即开始运行，客户端状态切换为"游戏中"。

![启动游戏](asset/8.png)

---

## 10. 配置 API 信息

> **⚠️ 注意：** 游戏依赖大语言模型接口，首次游玩前需要在游戏界面中配置 API 信息。

在游戏页面填写以下字段并保存，之后才可以正式开始游戏：

- **API Key** — 您的大模型 API 密钥
- **API URL** — 模型服务的接口地址
- **Model** — 使用的模型名称（如 `gpt-4o`）

![配置 API](asset/9.png)

---

## 11. 进入游戏

配置完成后点击开始，正式进入游戏世界，享受 AI 驱动的沉浸式体验。

![进入游戏](asset/10.png)

---

# 第二部分：新游戏打包接入规范

本节面向希望将自己的游戏接入 OpenStory Launcher 的开发者。

---

## 1. 游戏包目录结构

游戏包解压后必须包含以下结构（顶层为游戏文件夹）：

```
your-game-id/
  manifest.json        ← 必须，启动配置文件
  launch.bat           ← Windows 启动脚本
  game/                ← 游戏代码与资源
  runtime/             ← 运行时依赖（Python、Redis 等）
  ...
```

---

## 2. manifest.json 格式

`manifest.json` 放在游戏包根目录，客户端依赖此文件识别和启动游戏：

```json
{
  "id": "your-game-id",
  "name": "游戏显示名称",
  "version": "1.0.0",
  "launch": {
    "type": "bat",
    "command": "launch.bat",
    "working_dir": ".",
    "port": 8001
  }
}
```

| 字段 | 说明 |
|---|---|
| `id` | 游戏唯一标识，与 `projects.json` 中保持一致 |
| `name` | 客户端中显示的游戏名称 |
| `version` | 版本号 |
| `launch.command` | 启动命令，相对于 `working_dir` |
| `launch.working_dir` | 工作目录，通常为 `.`（游戏根目录） |
| `launch.port` | 游戏服务监听的 TCP 端口，客户端用此判断游戏是否就绪；不填则启动后立即切为"游戏中" |

---

## 3. 打包要求

**必须使用 Python 的 `zipfile` 模块打包**，不可使用 Windows 自带压缩、7-Zip 或其他工具，否则中文文件名在解压时会出现乱码。

打包脚本：

```python
import zipfile, os

def pack(src_dir, output_zip):
    src_dir = os.path.abspath(src_dir)
    base = os.path.dirname(src_dir)
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for root, dirs, files in os.walk(src_dir):
            for f in files:
                path = os.path.join(root, f)
                arcname = os.path.relpath(path, base).replace('\\', '/')
                zf.write(path, arcname)

pack(r'D:\your-game-id', r'D:\your-game-id.zip')
```

打包后 zip 内部结构示例：

```
your-game-id/manifest.json
your-game-id/launch.bat
your-game-id/game/...
your-game-id/runtime/...
```

---

## 4. projects.json 配置

在仓库的 `project-index` Release 中维护 `projects.json`，为每个游戏添加一条记录：

```json
{
  "id": "your-game-id",
  "name": "游戏名（中文）",
  "name_en": "Game Name (English)",
  "description": "游戏描述，展示在商店卡片和详情页",
  "author": "ZJU-LLMs",
  "cover": "https://封面图片直链URL",
  "category": "simulation",
  "tags": ["tag1", "tag2"],
  "latest_version": "1.0.0",
  "release_tag": "your-game-id-v1.0.0",
  "platforms": ["win64"],
  "size": {"win64": "200MB"}
}
```

| 字段 | 说明 |
|---|---|
| `release_tag` | 必须与 GitHub Release 的 Tag 完全一致 |
| `cover` | 建议使用仓库内图片的 raw 链接 |
| `platforms` | 目前支持 `win64` |

---

## 5. 发布到 GitHub Release

在 `ZJU-LLMs/OpenStory` 仓库完成以下操作：

**① 上传游戏包**

创建新 Release，Tag 名设为 `your-game-id-v1.0.0`，上传对应的 zip 文件。

**② 更新项目列表**

编辑 Tag 为 `project-index` 的 Release，将新版 `projects.json` 替换旧文件。

---

## 6. 游戏网页性能要求

游戏的前端网页运行在客户端内嵌浏览器（Electron Chromium）中，用户体验直接影响游戏可用性。请在开发时重点关注以下方面：

### 6.1 模式切换

- 切换游戏模式（如剧情模式 / 自由模式）时，前端状态应完整清理后再初始化新模式，避免残留数据污染
- 切换过程中禁止用户操作（可加 loading 遮罩），切换完成后再解锁，防止重复触发
- 后端切换接口应保证幂等性，多次请求不产生副作用

### 6.2 页面回退与前进

- 游戏内页面跳转建议使用前端路由（如 History API），而非完整页面刷新，保持游戏状态连续
- 禁止浏览器默认的页面回退跳出游戏（可通过 `history.pushState` 或拦截 `popstate` 事件实现）
- 若有多步骤流程，回退时应恢复到上一步的有效状态，而非直接返回首页

### 6.3 页面刷新

- 关键游戏状态（当前场景、角色位置、对话历史等）应定期持久化到后端或 `localStorage`，避免刷新后全部丢失
- 刷新后自动恢复到最近的有效状态，给用户明确的恢复提示
- 避免刷新导致后端任务重复启动，建议在启动前检查服务是否已在运行（如通过端口检测）

### 6.4 避免卡死与冲突

- AI 推演等耗时操作必须在后台异步执行，前端通过轮询或 WebSocket 获取进度，切勿阻塞主线程
- 同一时刻只允许发起一次推演请求，重复点击应有防抖或禁用处理
- 长时间无响应（超过 30 秒）时，前端应给出超时提示，并提供取消或重试选项
- 多个 AI 角色并发操作时，避免对同一资源（如地图格子、对话槽位）产生写冲突，后端应做并发保护

### 6.5 整体性能建议

- 地图、贴图等大体积资源建议懒加载，避免首屏加载时间过长
- 长列表（对话历史、角色列表）使用虚拟滚动或分页，防止 DOM 数量过多导致卡顿
- 定时轮询的频率根据业务需要合理设置，避免过于频繁的请求拖慢服务端响应
- 在客户端内嵌环境中，尽量避免弹出新窗口；如需跳转外部链接，使用 `target="_blank"` 由系统浏览器打开

---

## 7. 检查清单

发布前逐项确认：

- [ ] `manifest.json` 存在于游戏包根目录
- [ ] `launch.command` 指定的脚本可正常启动游戏服务
- [ ] `launch.port` 填写的端口游戏服务实际在监听
- [ ] zip 使用 Python `zipfile` 打包，中文路径验证无乱码
- [ ] GitHub Release Tag 与 `projects.json` 中 `release_tag` 完全一致
- [ ] `projects.json` 中 `project-index` Release 已更新
