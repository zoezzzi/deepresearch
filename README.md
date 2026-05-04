# DeepResearch - AI 驱动的研究助手

一个基于 AI 的研究助手系统，通过多 Agent 协作（规划、搜索、总结、生成报告）完成用户的调研任务，并通过 SSE 实时推送进度和结果。

## 技术架构

### 三层轻量级整洁架构

重构后的架构采用三层设计，合并了原有的 Application 和 Domain 层为 Core 层，去除过度抽象，提高代码可维护性：

```
┌─────────────────────────────────────────────────────────┐
│                      前端 (Vue3 + TS)                    │
│  调研表单 │ 任务看板 │ 报告预览 │ SSE 状态同步            │
└───────────────────────┬─────────────────────────────────┘
                        │ REST API / SSE
                        ▼
┌─────────────────────────────────────────────────────────┐
│                   接口层 (API Layer)                     │
│  Controllers │ API Models │ Dependencies                  │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                    核心层 (Core Layer)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Models     │  │   Services   │  │    Agents    │  │
│  │ (Pydantic)   │  │(业务逻辑)    │  │  (AI 代理)   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Workflow   │  │   Events     │  │ Repositories │  │
│  │  (LangGraph) │  │  (SSE)       │  │   (接口)     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                基础设施层 (Infrastructure Layer)          │
│  Config │ Logger │ DB │ SSE │ LLM │ Search │ Storage     │
└─────────────────────────────────────────────────────────┘
```

###

### 技术栈

**后端**

- **Web 框架**: FastAPI
- **工作流编排**: LangGraph
- **ORM**: SQLAlchemy
- **配置管理**: Pydantic Settings
- **日志**: Loguru
- **LLM**: 通义千问 (Qwen)
- **搜索**: Tavily
- **对象存储**: MinIO / 本地存储
- **数据库**: PostgreSQL
- **评估框架**: RAGAS (可选)

**前端**

- **框架**: Vue 3 + TypeScript
- **构建工具**: Vite
- **路由**: Vue Router
- **状态管理**: Pinia
- **HTTP 客户端**: Axios
- **Markdown 渲染**: Marked

**测试**

- **单元测试**: Pytest
- **前端测试**: Vitest

## 快速开始

### 前置要求

- Python 3.10+
- Node.js 18+
- Docker 和 Docker Compose
- Qwen API Key
- Tavily API Key

### 1. 环境配置

复制 `.env.example` 为 `.env` 并填入你的配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API 密钥：

```env
# Qwen 配置
QWEN_API_KEY=your_qwen_api_key_here

# Tavily 配置
TAVILY_API_KEY=your_tavily_api_key_here

# 数据库配置
POSTGRES_USER=deepresearch
POSTGRES_PASSWORD=deepresearch
POSTGRES_DB=deepresearch

# MinIO 配置
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
```

### 2. 启动基础设施

使用 Docker Compose 启动 PostgreSQL 和 MinIO：

```bash
docker-compose up -d
```

### 3. 后端设置

```bash
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动后端服务 
python main.py
```

后端服务将在 `http://localhost:8000` 启动，API 文档可访问：

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 4. 前端设置

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端服务将在 `http://localhost:3000 `启动。

## API 端点

### 研究相关

| 方法   | 端点                               | 说明         |
| ---- | -------------------------------- | ---------- |
| POST | `/research`                      | 创建并启动调研工作流 |
| GET  | `/research/{workflow_id}`        | 获取工作流状态和详情 |
| GET  | `/research/{workflow_id}/stream` | SSE 实时事件流  |

### 健康检查

| 方法  | 端点        | 说明   |
| --- | --------- | ---- |
| GET | `/`       | 欢迎页面 |
| GET | `/health` | 健康检查 |

## SSE 事件类型

| 事件类型            | 说明                     |
| --------------- | ---------------------- |
| `plan`          | 推送所有子任务清单              |
| `task_start`    | 某个子任务开始执行              |
| `task_complete` | 某个子任务完成                |
| `chunk`         | 报告生成过程中的流式 Markdown 片段 |
| `result`        | 报告生成完成                 |
| `error`         | 工作流或子任务失败              |

## 设计原则

本项目遵循以下设计原则：

1. **单一职责原则 (SRP)**: 每个类和模块只负责一件事
2. **开闭原则 (OCP)**: 对扩展开放，对修改关闭
3. **依赖倒置原则 (DIP)**: 依赖抽象而非具体实现
4. **分层调用约束**: 单向依赖，API → Core → Infrastructure
5. **接口隔离原则 (ISP)**: 接口最小化，避免胖接口
6. **迪米特法则 (LoD)**: 最少知识原则
7. **里氏替换原则 (LSP)**: 子类可以替换父类

## 开发指南

### 添加新的场景

项目采用场景化架构，添加新场景（如学术研究、市场分析等）只需 3 步：

**步骤 1：创建场景目录和文件**

在 `app/scenarios/` 下创建新场景目录，包含 3 个文件：

```
app/scenarios/
├── your_scenario/
│   ├── __init__.py      # 场景注册函数
│   ├── config.py         # 场景配置（ID、名称、UI配置等）
│   └── executor.py       # 场景执行器（实现 ScenarioExecutor 协议）
```

**步骤 2：实现场景代码**

参考现有场景 `dev_survey` 或 `research_assistant`，复制其结构并修改：

- `config.py`：定义场景 ID、名称、API 路由前缀、UI 配置
- `executor.py`：实现 `ScenarioExecutor` 协议，绑定对应的 Service
- `__init__.py`：创建 Executor 实例并注册到 `ScenarioRegistry`

**步骤 3：注册并启用场景**

1. 在 `app/scenarios/manager.py` 的 `_SCENARIO_REGISTRY` 中添加场景：
```python
_SCENARIO_REGISTRY: Dict[str, Callable[[], None]] = {
    "research_assistant_v1": register_research_assistant,
    "dev_survey": register_dev_survey,
    "your_scenario": register_your_scenario,  # 新增
}
```

2. 在 `.env` 或配置中添加场景 ID：
```
ENABLED_SCENARIOS=research_assistant_v1,dev_survey,your_scenario
```

### 添加新的 Agent

1. 在场景目录下创建 Agent 类，继承自 `Agent`
2. 在场景的 Service 中创建对应的领域服务
3. 在场景的 workflow 中添加新的工作流节点
4. 在场景的 executor 中添加依赖注入

### 添加新的搜索源

1. 在 `infrastructure/search/` 中实现搜索源接口
2. 在 `infrastructure/search/factory.py` 中注册新的搜索源
3. 在 `infrastructure/config.py` 中添加配置


### 评估模块

本项目集成了报告质量评估模块，包含 5 个评估指标：

| 指标                 | 说明     | 实现方式         |
| ------------------ | ------ | ------------ |
| Faithfulness       | 事实一致性  | RAGAS        |
| Context Relevancy  | 上下文相关性 | RAGAS        |
| Coverage           | 覆盖度    | LLM-as-Judge |
| Structure          | 结构完整性  | LLM-as-Judge |
| Professional Depth | 专业深度   | 规则评估         |

评估在报告生成后**异步执行**，不影响前端响应。评估结果存储在数据库中，供开发人员分析。

<br />

## 许可证

Apache License
