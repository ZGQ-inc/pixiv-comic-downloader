# Pixiv Comic Store (PUBLUS Reader) Downloader & Puzzle Reassembler

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT" />
  <img src="https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg" alt="Python: 3.8+" />
  <img src="https://img.shields.io/badge/Primary%20Format-CBZ-orange.svg" alt="Format: CBZ" />
  <img src="https://img.shields.io/badge/Automation-Playwright-purple.svg" alt="Playwright" />
</p>

专为 **Pixiv Comic Store**（采用 **ACCESS PUBLUS Reader HTML5 Canvas** 内核）设计的全自动漫画无损下载与**图像切片打乱重组（Puzzle Slicing & Reassembly）**还原工具。

**核心特性**：
- **CBZ 漫画优先**：默认首选输出为标准 `.cbz` 漫画格式，可直接导入 Tachiyomi、Mihon、CDisplayEx、Calibre、Panels 等主流漫画阅读器，同时向下支持 PNG、JPEG 与 PDF。
- **无损画质还原**：基于纯 Python PIL 逆向还原 $32 \times 32$ 像素网格碎片，100% 像素级无缝拼合。
- **全自动化拦截**：利用 Playwright 无头浏览器在渲染生命周期内注入 Canvas `drawImage` 拦截器，自动捕获坐标映射并免鉴权保存图片二进制流。
- **智能模拟翻页**：模拟原生触控翻页，自动遍历全本漫画并智能检测终点。

---

## 目录结构

```text
pixiv_comic_downloader/
├── core/
│   ├── __init__.py
│   ├── puzzle.py             # 通用图像切片打乱与重组引擎 (PIL 实现)
│   └── coordinate_map.py     # 坐标映射表数据结构与序列化
├── crawler/
│   ├── __init__.py
│   └── playwright_fetcher.py # 基于 Playwright 的阅读器自动化交互与网络/Canvas拦截器
├── utils/
│   ├── __init__.py
│   └── exporter.py           # 导出工具（优先 CBZ 漫画包，支持 PDF / 单页图片）
├── main.py                   # 命令行运行入口
├── pyproject.toml            # 现代 Python 项目打包配置
├── requirements.txt          # Python 依赖清单
├── .gitignore                # Git 忽略配置
├── LICENSE                   # MIT 开源许可证 (ZGQ Inc.)
└── README.md                 # 项目文档
```

---

## 安装与快速开始

### 1. 克隆或下载项目并安装依赖

```bash
cd pixiv_comic_downloader
pip install -r requirements.txt
playwright install chromium
```

### 2. 一键下载并导出为 CBZ 漫画书（默认首选）

支持直接传入完整阅读器 URL 或漫画 `cid`：

```bash
# 默认导出为高质量 .cbz 漫画包
python main.py https://comic-store-viewer.pixiv.net/static/viewer?cid=gkagktexy

# 或者直接传入 cid：
python main.py gkagktexy
```

导出生成的 `.cbz` 格式可无缝用各类漫画阅读器打开，包含完整单页序列与封面。

---

## 命令行参数一览

```text
usage: main.py [-h] [-o OUTPUT_DIR] [-f {cbz,png,jpg,pdf,all}] [--no-headless]
               [--max-pages MAX_PAGES] [--flip-delay FLIP_DELAY]
               [--save-scrambled] [--save-coords]
               target
```

| 参数 | 简写 | 默认值 | 描述 |
|---|---|---|---|
| `target` | - | **必填** | Pixiv 漫画 URL 或单个 `cid` |
| `--format` | `-f` | **`cbz`** | 导出格式：**`cbz`（默认推荐）**、`png`、`jpg`、`pdf`、`all` |
| `--cookies`| - | `None` | **Cookies 文件路径（支持 yt-dlp / Netscape 标准 `cookies.txt`）** |
| `--output-dir`| `-o` | `./output` | 输出文件夹根目录 |
| `--save-coords`| - | 关闭 | 导出全套切片坐标数据为 `coordinate_mappings.json` |
| `--save-scrambled`| - | 关闭 | 额外保存打乱前的未还原碎片原图（供对比与研究） |
| `--max-pages` | - | 无限制 | 限制最大下载页数（测试用） |
| `--flip-delay`| - | `1.0` | 翻页间隔时间（秒） |
| `--no-headless`| - | 隐藏运行 | 弹出可视化浏览器窗口（调试观察用） |

---

## Cookies 登录凭据支持 (yt-dlp 兼容模式)

对于已购买或需要登录 Pixiv 账号才能阅读的完整漫画章节，支持通过 `--cookies` 传入标准的 Netscape / curl `cookies.txt` 文件（逻辑与 `yt-dlp --cookies cookies.txt` 完全一致）：

1. **导出 Cookies**：在浏览器中使用扩展（如 [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)）将登录状态下的 Pixiv Cookie 导出为 `cookies.txt`。
2. **下载付费/需登录漫画**：
   ```bash
   python main.py https://comic-store-viewer.pixiv.net/static/viewer?cid=YOUR_CID --cookies cookies.txt
   ```
程序会自动将 Cookie 注入 Playwright 浏览器上下文，享受登录会员/已购全本权限。

### 进阶用法示例

```bash
# 导出为 PDF 格式
python main.py gkagktexy --format pdf

# 导出所有格式（同时生成 CBZ、PDF、PNG 单页图片及坐标映射表）
python main.py gkagktexy --format all --save-coords

# 保存未还原原图供研究对比
python main.py gkagktexy --save-scrambled --save-coords
```

---

## 图像切片重组原理解析

PUBLUS Reader 采用了基于 HTML5 Canvas 的前端拼图反爬机制：
1. **切片打乱**：服务器分发的图片被切割为 $32 \times 32$ 像素网格并打乱分布在略带 Padding 的大图上（如 $1352 \times 1920$）。
2. **坐标解算**：阅读器前端接收加密配置 `configuration_pack.json`，根据内嵌算法计算每个切片对应的源坐标 `(sx, sy, sw, sh)` 与目标画布坐标 `(dx, dy, dw, dh)`。
3. **Canvas 绘制**：阅读器在画布上逐一切片调用 `CanvasRenderingContext2D.prototype.drawImage` 将碎片画回原位。
4. **本工具还原逻辑**：
   - 在页面注入底层 Hook 拦截每个切片的真实参数；
   - 监听网络流截获高分辨率碎片二进制图片；
   - 由 `core/puzzle.py` 内的通用拼图算法执行高保真还原；
   - 自动生成符合漫画阅读器规范的 `.cbz` 压缩包。

---

## Python API 调用示例

您可以在其它 Python 项目中直接引入本项目的拼图切片与重组模块：

```python
from PIL import Image
from core.puzzle import reassemble_image, scramble_image, generate_grid_mapping

# 1. 根据坐标映射表一键还原图片
restored_img = reassemble_image(scrambled_image_bytes, mapping_data)
restored_img.save("clean_page.png")

# 2. 生成自定义网格打乱映射表并对任意图片进行切片混淆测试
mapping = generate_grid_mapping(width=1280, height=1920, block_width=32, block_height=32, seed=123)
scrambled_img = scramble_image(restored_img, mapping)
recovered_img = reassemble_image(scrambled_img, mapping)
```

---

## License

本项目基于 [MIT License](LICENSE) 开源。
