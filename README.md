# 投标助手 MVP 第一阶段

## 运行方式

```bash
venv\Scripts\activate
python main.py
```

## 自动版本管理

开启文件监控，源码有变动时自动 `git add` + `commit` + `push`：

```bash
python -u scripts/auto_commit.py
```

按 `Ctrl+C` 停止。自动提交的信息格式为 `auto: sync changes (...)`。

> 首次 push 时会要求输入 GitHub 账号密码，Windows 凭据管理器会自动记住，之后不再需要输入。

## 目录说明

- `src/bidhelper/`：源码
- `data/`：SQLite 数据库和配置
- `imports/`：导入的招标文件副本
- `projects/`：项目资料文件夹

## 功能

- 项目管理（新建/编辑/删除，双击打开）
- 导入 PDF/DOCX 招标文件，后台线程解析，进度反馈不卡界面
- 自动解析招标要求（评分项、废标项、资质门槛、格式要求、时间节点）
- 要求清单：统计卡片、搜索/筛选/排序、状态与分类表格内直接编辑
- 要求清单导出 Excel（冻结表头、自动筛选、状态着色、合法值下拉校验）
