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

### 架构改进

**重构前 (5 层)**:

- API → Application → Domain → Infrastructure
- 问题：层级过深，Entity/DTO/VO 重复定义，概念重叠

**重构后 (3 层)**:

- API → Core → Infrastructure
- 改进：层级清晰，使用 Pydantic 统一数据模型，去除过度抽象
- 代码量减少约 30%，171 个测试全部通过

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

# 启动后端服务 (Windows 平台使用 run_server.py)
python run_server.py
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

前端服务将在 `http://localhost:5173` 启动。

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

## 项目结构

```
research-assistant/
├── backend/
│   ├── api/                          # 接口层
│   │   ├── controllers/              # 控制器
│   │   │   └── research_controller.py
│   │   ├── models/                   # API 模型
│   │   ├── dependencies.py           # 依赖注入
│   │   └── __init__.py
│   ├── core/                         # 核心层 (合并 Application + Domain)
│   │   ├── models/                   # 数据模型 (Pydantic)
│   │   │   ├── enums.py              # 枚举类型
│   │   │   ├── models.py             # 核心实体
│   │   │   └── dtos.py               # 数据传输对象
│   │   ├── services/                 # 业务服务
│   │   │   ├── research_service.py   # 研究主服务
│   │   │   ├── research_plan_service.py
│   │   │   ├── task_execution_service.py
│   │   │   ├── report_generation_service.py
│   │   │   └── evaluation_service.py
│   │   ├── agents/                   # AI Agent 实现
│   │   │   ├── base.py
│   │   │   ├── plan_agent.py         # 规划 Agent
│   │   │   ├── search_agent.py       # 搜索 Agent
│   │   │   ├── summarizer_agent.py   # 摘要 Agent
│   │   │   └── generate_agent.py     # 报告生成 Agent
│   │   ├── workflow/                 # 工作流编排 (LangGraph)
│   │   │   ├── graph.py              # 工作流图定义
│   │   │   ├── saver.py              # 状态持久化
│   │   │   └── state.py              # 工作流状态
│   │   ├── events/                   # 事件发布 (SSE)
│   │   │   ├── event_publisher.py
│   │   │   └── event_types.py
│   │   ├── tasks/                    # 异步任务
│   │   │   └── evaluation_task.py    # 评估任务
│   │   ├── repositories/             # 仓储接口
│   │   │   ├── evaluation_repository.py
│   │   │   ├── task_repository.py
│   │   │   └── workflow_repository.py
│   │   ├── service_factory.py        # 服务工厂
│   │   └── __init__.py
│   ├── infrastructure/               # 基础设施层
│   │   ├── db/                       # 数据库
│   │   │   ├── repositories/         # 仓储实现
│   │   │   │   ├── evaluation_repository_impl.py
│   │   │   │   ├── task_repository_impl.py
│   │   │   │   └── workflow_repository_impl.py
│   │   │   ├── async_pool.py         # 异步连接池
│   │   │   ├── models.py             # 数据库模型
│   │   │   └── session.py            # 会话管理
│   │   ├── evaluation/               # 评估模块
│   │   │   ├── base_evaluator.py     # 评估器基类
│   │   │   ├── llm_judge_evaluator.py # LLM-as-Judge 评估器
│   │   │   ├── orchestrator.py       # 评估编排器
│   │   │   ├── ragas_evaluator.py    # RAGAS 评估器
│   │   │   └── rule_evaluator.py     # 规则评估器
│   │   ├── llm/                      # LLM 客户端
│   │   │   ├── base.py
│   │   │   ├── factory.py
│   │   │   └── langchain_client.py
│   │   ├── search/                   # 搜索源
│   │   │   ├── base.py
│   │   │   ├── factory.py
│   │   │   └── tavily_source.py
│   │   ├── sse/                      # SSE 管理器
│   │   │   └── manager.py
│   │   ├── storage/                  # 对象存储
│   │   │   ├── base.py
│   │   │   ├── local_storage.py
│   │   │   └── minio_client.py
│   │   ├── config.py                 # 配置管理
│   │   ├── logger.py                 # 日志配置
│   │   └── __init__.py
│   ├── tests/                        # 测试目录
│   │   ├── unit/                     # 单元测试
│   │   │   ├── models/               # 模型测试
│   │   │   ├── services/             # 服务测试
│   │   │   ├── agents/               # Agent 测试
│   │   │   ├── workflow/             # 工作流测试
│   │   │   └── events/               # 事件测试
│   ├── common/                       # 公共模块
│   │   ├── utils/
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   └── logger.py
│   ├── main.py                       # FastAPI 入口
│   ├── .env.example                  # 环境变量示例
│   ├── requirements.txt              # 生产依赖
├── frontend/                         # 前端代码
│   ├── src/
│   │   ├── api/                      # API 客户端
│   │   │   ├── client.ts
│   │   │   └── sse.ts
│   │   ├── components/               # 组件
│   │   │   └── TaskCard.vue
│   │   ├── router/                   # 路由
│   │   │   └── index.ts
│   │   ├── stores/                   # 状态管理 (Pinia)
│   │   │   └── research.ts
│   │   ├── types/                    # TypeScript 类型
│   │   │   └── index.ts
│   │   ├── views/                    # 页面
│   │   │   ├── ResearchForm.vue
│   │   │   ├── TaskBoard.vue
│   │   │   └── ReportPreview.vue
│   │   ├── App.vue
│   │   └── main.ts
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml                # Docker Compose 配置
└── README.md
```

## 核心层 (Core) 说明

Core 层是重构后的核心，合并了原有的 Application 和 Domain 层：

### Models

使用 Pydantic 模型统一替代传统的 Entity + Value Object + DTO：

- `Workflow` - 工作流实体，包含状态转换方法
- `Task` - 任务实体，管理任务生命周期
- `ResearchReport` - 研究报告
- `EvaluationResult` - 评估结果

### Services

业务逻辑实现：

- `ResearchService` - 研究主服务，协调整个工作流
- `ResearchPlanService` - 生成研究计划
- `TaskExecutionService` - 执行任务（搜索+摘要）
- `ReportGenerationService` - 生成研究报告
- `EvaluationService` - 评估服务

### Agents

AI 代理，封装与 LLM 的交互：

- `PlanAgent` - 分析主题，生成子任务
- `SearchAgent` - 执行搜索查询
- `SummarizerAgent` - 总结搜索结果
- `GenerateAgent` - 生成最终报告

### Workflow

使用 LangGraph 编排工作流：

- `ResearchWorkflowGraph` - 定义工作流图
- 节点：plan → execute\_task → generate\_report
- 支持状态持久化和恢复

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

### 添加新的 Agent

1. 在 `core/agents/` 中创建新的 Agent 类，继承自 `Agent`
2. 在 `core/services/` 中创建对应的领域服务
3. 在 `core/workflow/graph.py` 中添加新的工作流节点
4. 在 `api/dependencies.py` 中添加依赖注入

### 添加新的搜索源

1. 在 `infrastructure/search/` 中实现搜索源接口
2. 在 `infrastructure/search/factory.py` 中注册新的搜索源
3. 在 `infrastructure/config.py` 中添加配置

### 运行测试

```bash
cd backend

# 运行所有测试
python -m pytest tests -v

# 只运行单元测试
python -m pytest tests/unit -v
```

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

