# 投标助手 MVP 第一阶段

## 运行方式

```bash
venv\Scripts\activate
python main.py
```

## 自动版本管理

开启文件监控，源码有变动时自动 `git add` + `commit`：

```bash
python -u scripts/auto_commit.py
```

按 `Ctrl+C` 停止。自动提交的信息格式为 `auto: sync changes (...)`。

## 目录说明

- `src/bidhelper/`：源码
- `data/`：SQLite 数据库和配置
- `imports/`：导入的招标文件副本
- `projects/`：项目资料文件夹

## 功能

- 项目管理（新建/编辑/删除）
- 导入 PDF/DOCX 招标文件
- 自动解析招标要求（评分项、废标项、资质门槛、格式要求、时间节点）
- 人工复核要求清单（增删改）
