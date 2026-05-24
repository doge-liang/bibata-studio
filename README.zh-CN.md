# bibata-studio

**简体中文** · [English](./README.md)

本地优先、纯 Python 的 CLI，用来构建 [Bibata](https://github.com/ful1e5/Bibata_Cursor) 鼠标光标主题。没有 Web 框架，没有数据库，没有登录系统，没有 Figma token —— SVG 进，光标 `.zip` 出。

> **跟上游什么关系？** 这是 Bibata 构建管线的**独立重写**，不是 git 意义上的 fork。光标 SVG 和 [`ctgen`](https://github.com/ful1e5/clickgen) 的构建配置**原样 vendor** 自 [`ful1e5/Bibata_Cursor`](https://github.com/ful1e5/Bibata_Cursor) 的 commit `35ccfe2`（2024-06-18）。所有 Python 代码都是新写的，跟 [`ful1e5/bibata`](https://github.com/ful1e5/bibata) 那个 Web 应用零代码共享 —— 只借用了三个占位 hex 色（`#00FF00` / `#0000FF` / `#FF0000`）作为颜色替换协议。完整声明见 [`NOTICE`](./NOTICE)。

```
$ bibata build --variant modern --color amber --platform windows --windows-size large
[bibata] Rendering 'modern' with palette 'Amber' (#FF8300 / #FFFFFF / #001524)
[bibata]   rendered 164 PNGs in 1.4s
[bibata] Packing Windows theme 'Bibata-Modern-Amber-Large' …
[bibata] Done. Wrote 1 artifact(s):
  → ./out/Bibata-Modern-Amber-Large-Windows.zip
```

## 为什么做这个

上游的 [`ful1e5/bibata`](https://github.com/ful1e5/bibata) 是个 Next.js + Flask + Postgres + Vercel-KV + GitHub OAuth 的 Web 应用，里面包的核心其实就两件事：

1. 在几张 SVG 里替换三种"占位"颜色
2. 把出来的 PNG 喂给 [`clickgen`](https://github.com/ful1e5/clickgen) 打包成 Windows 或 X11 主题

那套架构对收赞助的 SaaS 站点是合理的。本地用就全是负担 —— 而且 2024 年底开始也开始崩了：

- `@vercel/kv` 2024 年 12 月并进 Upstash 后被弃用，上游代码还在 import
- Vercel Postgres 并进 Neon，上游连接串失效
- Figma 文件访问要原作者的 `FIGMA_TOKEN`
- 上游最后一次 commit 是 2024 年 7 月，多个 issue 在说站点挂了

本项目把虚线以上的东西全砍掉：

```
  ┌───────────────────────────────────────────────┐
  │  Next.js · NextAuth · Prisma · @vercel/kv ·   │   ← 砍掉
  │  Vercel Postgres · Figma API · Flask · Docker │
  ├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┤
  │  SVG 颜色替换  +  clickgen 打包                │   ← 保留
  └───────────────────────────────────────────────┘
```

留下的部分用大约 1100 行 Python 重写。

## 安装

需要 **Python ≥ 3.10**。Windows 11 + Python 3.12 上测过。

`pip` 会拉两个运行时依赖：
- [`resvg-py`](https://pypi.org/project/resvg-py/) —— Rust 后端的 SVG 栅格化器（Windows wheel 已预编译）
- [`clickgen`](https://pypi.org/project/clickgen/) —— 原 Bibata 作者写的 XCursor/CUR/ANI 打包器

### 给人类用户

直接用还是改代码，下面两种选一个。

**直接用**（PowerShell，Windows）：

```powershell
# 整段复制粘贴
git clone https://github.com/doge-liang/bibata-studio.git
cd bibata-studio
python -m pip install --user .
python -m bibata_studio install -v modern -c amber
# ↑ 会弹一次 UAC，点"是"，这是全程唯一一次手动操作
```

**改代码**（editable 装，跨平台）：

```powershell
git clone https://github.com/doge-liang/bibata-studio.git
cd bibata-studio
python -m pip install --user -e .[dev]
python -m pytest                                          # 应该 8/8 通过
python -m bibata_studio preview -v modern -c amber        # 浏览器里看一眼
```

`python` 不在 PATH 上的话用 `py -3.12`（Windows 自带的 Python launcher），或者你平台上对应的写法。`pip install --user` 警告 `Scripts\` 不在 PATH 上 —— 忽略，用 `python -m bibata_studio ...` 调就好，不用动 PATH。

### 给 Agent

下面这些都是非交互 + 幂等的，给 CI、autonomous coding agent、沙箱里跑都行。

**一行（uvx，推荐 —— 不用管 venv）：**

```bash
uvx --from git+https://github.com/doge-liang/bibata-studio.git@main \
    bibata build -v modern -c amber -p windows --windows-size large -o ./out
```

**一行（pip + python -m，不依赖 PATH）：**

```bash
python -m pip install --quiet --user 'bibata-studio @ git+https://github.com/doge-liang/bibata-studio.git@main' \
  && python -m bibata_studio --version \
  && python -m bibata_studio build -v modern -c amber -p windows --windows-size large -o ./out \
  && ls ./out/*.zip
```

**完整 setup + 冒烟测试（多步、可恢复）：**

```bash
set -euo pipefail
REPO=https://github.com/doge-liang/bibata-studio.git
WORKDIR="${WORKDIR:-./bibata-studio}"

# 1. 拉源码（已存在就跳过）
[ -d "$WORKDIR" ] || git clone --depth 1 "$REPO" "$WORKDIR"
cd "$WORKDIR"

# 2. 装上（editable，user scope，静默）
python -m pip install --quiet --user -e .

# 3. 端到端跑构建管线（不弹 UAC，不真装到系统）
python -m bibata_studio --version
python -m bibata_studio list
python -m bibata_studio build -v modern -c amber -p windows --windows-size large -o ./out

# 4. 校验产物 zip 的二进制结构
python tests/verify_windows_zip.py ./out/Bibata-Modern-Amber-Large-Windows
```

**Agent 注意事项：**
- `bibata install` / `bibata uninstall` 在 Windows 上**需要交互式 UAC 同意**。autonomous 流程跳过这两个，用 `bibata build` 出 zip，让人类用户自己装。
- `bibata preview` 调的是 `webbrowser.open()`。headless 环境加 `--no-open`，只打印文件 URI 就行。
- 构建是确定的：同一组 `(variant, palette)` 输入会出 byte-identical 的 zip（install.inf 的注释也是稳定的）。放心缓存。
- pip wheel 缓存跨多次 run 复用 —— 重复装只要几秒。

## 命令一览

```text
bibata build      -v <变体> -c <配色> [-p <平台>] [--windows-size <尺寸>] [-o <目录>]
bibata install    -v <变体> -c <配色> [--windows-size <尺寸>]    # 仅 Windows
bibata uninstall  <已解压主题目录路径>                            # 仅 Windows
bibata preview    -v <变体> -c <配色> [-s <像素>] [-o <目录>] [--no-open]
bibata list       # 列出所有变体和配色
```

### 变体

| 名字 | 含义 |
|---|---|
| `modern` | 圆角，左手 |
| `modern-right` | 圆角，右手镜像 |
| `original` | 尖角，左手 |
| `original-right` | 尖角，右手镜像 |

### 内置配色

| 名字 | base | outline | watch 背景 |
|---|---|---|---|
| `amber` | `#FF8300` | 白 | `#001524` |
| `classic` | 黑 | 白 | 黑 |
| `ice` | 白 | 黑 | 白 |

### 自定义配色

```powershell
# Gruvbox 深色
bibata build -v original -c custom `
    --base "#282828" --outline "#EBDBB2" --watch-bg "#000000" `
    -p windows --windows-size large

# Dracula
bibata build -v modern -c custom `
    --base "#282A36" --outline "#F8F8F2" --watch-bg "#44475A" `
    -p windows --windows-size large
```

### 输出平台

| `-p` 值 | 输出 |
|---|---|
| `windows` | 含 `.cur` / `.ani` + `install.inf` + `uninstall.bat` 的 `.zip` |
| `x11` | Linux XCursor 主题目录（看下面注意事项） |
| `both` | 两个一起出 |

### Windows 尺寸档

上游为每个手向变体准备了四档 hotspot/尺寸 profile —— 选一档，或者一次性出全部：

| `--windows-size` | 基础尺寸 | 适用 |
|---|---:|---|
| `regular` | 32 px | 常规 1×/1.25× DPI |
| `large`（默认） | 48 px | 1.5×/1.75× DPI |
| `xl` | 64 px | 2× DPI 及以上 |
| `all` | — | 三档一次出 |

### 手动装一个 zip

不想用 `bibata install` 的话，手动装也行：

1. 右键 zip → 解压
2. 在解压出的目录里 **Shift + 右键** `install.inf`（Win11 上右键 → 显示更多选项）→ **安装**
3. 通过 UAC
4. 新方案立刻生效。想确认的话开控制面板鼠标属性（`control main.cpl ,,1`），指针标签的方案下拉里应该看到 `Bibata-…-Windows Cursors` 已被选中

方案名规则是 `Bibata-<变体>-<配色>-<尺寸> Cursors`（末尾 "Cursors" 是 clickgen 自动加的，不是手贱）。

## 架构

```
bibata-studio/
├── pyproject.toml
└── src/bibata_studio/
    ├── cli.py        # argparse 入口 + 流程编排
    ├── presets.py    # 配色 + 变体到 group 的映射 + 命名规则
    ├── render.py     # SVG 颜色替换 + resvg-py 栅格化
    ├── build.py      # 进程内调 clickgen.scripts.ctgen.main
    ├── preview.py    # HTML 画廊生成器
    └── data/
        ├── svg/groups/         # 从 Bibata_Cursor/svg/groups/ vendor
        │   ├── shared/ ...
        │   ├── modern-arrow/ ...
        │   ├── modern/ ...
        │   ├── modern-right/ ...
        │   ├── original-arrow/ ...
        │   ├── original/ ...
        │   ├── original-right/ ...
        │   ├── hand/ ...
        │   └── hand-right/ ...
        └── configs/            # vendor 的 ctgen TOML
            ├── normal/{x,win_rg,win_lg,win_xl}.build.toml
            └── right/{x,win_rg,win_lg,win_xl}.build.toml
```

一次 build 分三步：

1. **走目录**：按 `presets.VARIANTS` 找出当前变体对应的 group 目录序列
2. **渲染**：每个 SVG 做颜色替换后渲染到 256×256 PNG，扔进一个扁平的 `bitmaps/` 目录
3. **打包**：把 vendored 的 TOML + bitmaps 目录交给 `clickgen.scripts.ctgen.main`（in-process 调用）。clickgen 负责 `.cur`/`.ani` 编码、多尺寸重采样、hotspot、Windows symlink 和 `install.inf` 生成

## 注意事项

- **X11 主题在 Windows 上需要 symlink 权限**。clickgen 用 `os.symlink` 给 XCursor 创建名字别名，Windows 上要管理员或开发者模式。只出 Windows（`-p windows`）的话不受影响。Linux/macOS 没这限制。
- **暂时没 GUI**。Roadmap 里有个 PySide6 选色面板。在那之前，`bibata preview -v <变体> -c <配色>` 出一个 HTML 画廊（96px，含动画播放），用默认浏览器打开。

## Roadmap

按大致优先级：

- [ ] `bibata watch` 模式：监听 SVG 改动自动重新渲染，方便改图
- [ ] PySide6/Tk 的 GUI，带实时预览和"草稿"配色
- [ ] PyInstaller 打成绿色 `.exe`，没装 Python 的用户也能用
- [ ] 不靠 symlink 的 X11 输出路径（用复制文件代替）
- [ ] 动画帧间隔的可调开关（现在用上游默认的 30ms）

## 借来的 vs 自写的

精确版本 —— 法律层看 [`NOTICE`](./NOTICE)。

| 资产 | 来源 | 形式 |
|---|---|---|
| 372 个光标 SVG | `ful1e5/Bibata_Cursor` @ `35ccfe2` | 原样拷到 `src/bibata_studio/data/svg/groups/` |
| 8 个 `ctgen` 构建 TOML | `ful1e5/Bibata_Cursor` @ `35ccfe2` | 原样拷到 `src/bibata_studio/data/configs/` |
| 变体→group 的映射 | `ful1e5/Bibata_Cursor/svg/link.py` | 改写成 Python dict 放在 `presets.VARIANTS` |
| 三个占位 hex 色 | `ful1e5/bibata` web app + Bibata_Cursor README | 借了协议（`#00FF00` / `#0000FF` / `#FF0000`） |
| `.cur` / `.ani` 打包 | `clickgen` pip 包 | 运行时 import |
| 全部 Python 源码（~1100 行） | — | 本项目原创，**跟 `ful1e5/bibata` 零代码共享** |

`ful1e5/bibata` 那个 Web 应用一行代码都没贡献 —— 只贡献了颜色占位约定。所有美术成果归 **Abdulkaiz Khatri**（[@ful1e5](https://github.com/ful1e5)）。觉得 Bibata 好用的话，去 [赞助 @ful1e5](https://github.com/sponsors/ful1e5)。

## License

MIT。见 [`LICENSE`](./LICENSE)。
