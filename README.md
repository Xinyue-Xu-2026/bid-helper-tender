# 投标助手 MVP 第一阶段

## 运行方式

```bash
venv\Scripts\activate
python main.py
```

## AI 解析配置

1. 首次使用：点击左侧"设置"，粘贴 API Key，点"测试连接"验证后保存。支持两种 Key：
   - Moonshot 开放平台 Key（platform.moonshot.cn 创建，按量计费，每次约 ¥0.2）
   - Kimi 编程订阅 Key（`sk-kimi-` 开头，如 Kimi for Coding 订阅）：程序自动识别并使用编程网关（api.kimi.com/coding），模型按 k3 处理，无需额外配置
2. 解析招标文件时，程序将招标文件文本发送至云端 API 进行智能抽取；无 Key 或调用失败时自动使用内置规则解析。
3. 也可通过环境变量 `MOONSHOT_API_KEY` 配置（优先级高于设置界面）。

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
- AI 智能解析：接入 Kimi 大模型自动抽取招标要求（评分细则、资格证明、保证金等全覆盖），规则解析离线兜底
- 设置界面：配置 Moonshot API Key（存本地 data/config.json，不上传）、切换解析模型、测试连接
