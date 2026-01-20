# QuickSearch 🚀 

**QuickSearch** 是一款专为 macOS 设计的极简、极速本地文件搜索工具。它基于 PyQt5 开发，采用 SQLite 数据库进行毫秒级检索，并支持系统级实时文件监控。

---

## ✨ 功能特性

- **极速搜索**：基于 SQLite WAL 模式，毫秒级响应上万文件的检索。
- **实时监控**：利用 `watchdog` 监听文件变动，自动同步索引。
- **系统集成**：常驻 macOS 状态栏，支持快速唤醒与设置。
- **极简 UI**：无边框设计，完美融入 macOS 现代审美。
- **低资源占用**：Python 编写，仅在搜索时占用少量 CPU。

## 📸 预览
<img width="700" height="450" alt="image" src="https://github.com/user-attachments/assets/9589fe08-06e5-4748-9093-c64c791a2eaa" />



---

## 🛠️ 安装与运行

### 1. 克隆仓库
```bash
git clone [https://github.com/你的用户名/macos_search_file.git](https://github.com/你的用户名/macos_search_file.git)
cd macos_search_file

```

### 2. 创建并激活虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate

```

### 3. 安装依赖

```bash
pip install -r requirements.txt

```

### 4. 运行程序

```bash
python main.py

```

---

## 📦 如何打包成 .app

如果你想生成独立的 macOS 应用程序，可以执行以下步骤：

1. **安装打包工具**：
```bash
pip install pyinstaller Pillow

```


2. **执行打包脚本**：
```bash
python -m PyInstaller --noconfirm --onedir --windowed \
--name "QuickSearch" \
--icon "AppIcon.icns" \
--clean \
main.py

```


3. 打包完成后，在 `dist/` 目录下即可找到 `QuickSearch.app`。

---

## ⚙️ 配置说明

* **搜索路径**：首次运行可在“设置”中添加需要索引的文件夹。
* **索引数据库**：默认存储在 `~/.mac_search_index.db`。

---



## 📄 开源协议

本项目采用 [MIT License](https://www.google.com/search?q=LICENSE) 协议。

