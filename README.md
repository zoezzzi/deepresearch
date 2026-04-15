
# DeepResearch - AI 驱动的研究助手

一个基于 AI 的研究助手系统，通过多 Agent 协作（规划、搜索、总结、生成报告）完成用户的调研任务，并通过 SSE 实时推送进度和结果。

## 技术架构

### DDD 分层架构

本项目严格遵循领域驱动设计（DDD）的分层架构原则：

```
┌─────────────────────────────────────────────────────────┐
│                      前端 (Vue3 + TS)                    │
│  调研表单 │ 任务看板 │ 报告预览 │ SSE 状态同步            │
└───────────────────────┬─────────────────────────────────┘
                        │ REST API / SSE
                        ▼
┌─────────────────────────────────────────────────────────┐
│                   接口层 (Interface Layer)               │
│  Controllers │ API Models │ Dependencies                  │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                   应用层 (Application Layer)              │
│  Application Services │ DTOs │ Workflow │ Events         │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                    领域层 (Domain Layer)                  │
│  Entities │ Value Objects │ Aggregates │ Domain Services │
│  Agents │ Repository Interfaces                           │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                基础设施层 (Infrastructure Layer)          │
│  Config │ Logger │ DB │ SSE │ LLM │ Search │ Storage     │
└─────────────────────────────────────────────────────────┘
```

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

前端服务将在 `http://localhost:5173` 启动。

## API 端点

### 研究相关

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/research` | 创建并启动调研工作流 |
| GET | `/research/{workflow_id}` | 获取工作流状态和详情 |
| GET | `/research/{workflow_id}/stream` | SSE 实时事件流 |

### 健康检查

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/` | 欢迎页面 |
| GET | `/health` | 健康检查 |

## SSE 事件类型

| 事件类型 | 说明 |
|----------|------|
| `plan` | 推送所有子任务清单 |
| `task_start` | 某个子任务开始执行 |
| `task_complete` | 某个子任务完成 |
| `chunk` | 报告生成过程中的流式 Markdown 片段 |
| `result` | 报告生成完成 |
| `error` | 工作流或子任务失败 |

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
│   ├── application/                  # 应用层
│   │   ├── application_services/     # 应用服务
│   │   │   └── research_application_service.py
│   │   ├── dtos/                     # 数据传输对象
│   │   │   ├── create_research_request.py
│   │   │   └── research_responses.py
│   │   ├── workflow/                 # 工作流编排 (LangGraph)
│   │   │   ├── graph.py              # 工作流图定义
│   │   │   ├── saver.py              # 状态持久化
│   │   │   └── state.py              # 工作流状态
│   │   ├── events/                   # 事件发布
│   │   │   ├── event_publisher.py
│   │   │   └── event_types.py
│   │   ├── tasks/                    # 异步任务
│   │   │   └── evaluation_task.py    # 评估任务
│   │   ├── service_factory.py        # 服务工厂
│   │   └── __init__.py
│   ├── domain/                       # 领域层
│   │   ├── entities/                 # 领域实体
│   │   │   ├── evaluation_result.py  # 评估结果实体
│   │   │   ├── research_report.py
│   │   │   ├── task.py
│   │   │   └── workflow.py
│   │   ├── value_objects/            # 值对象
│   │   │   ├── evaluation_score.py   # 评估分值
│   │   │   ├── evaluation_status.py  # 评估状态
│   │   │   ├── workflow_id.py
│   │   │   ├── workflow_status.py
│   │   │   └── ...
│   │   ├── aggregates/               # 聚合根
│   │   │   └── research_workflow.py
│   │   ├── domain_services/          # 领域服务
│   │   │   ├── evaluation_service.py # 评估服务
│   │   │   ├── report_generation_service.py
│   │   │   ├── research_plan_service.py
│   │   │   └── task_execution_service.py
│   │   ├── agents/                   # Agent 实现
│   │   │   ├── base.py
│   │   │   ├── generate_agent.py
│   │   │   ├── plan_agent.py
│   │   │   ├── search_agent.py
│   │   │   └── summarizer_agent.py
│   │   ├── repositories/             # 仓储接口
│   │   │   ├── evaluation_repository.py
│   │   │   ├── task_repository.py
│   │   │   └── workflow_repository.py
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
│   │   ├── domain/                   # 领域层测试
│   │   │   ├── value_objects/        # 值对象测试
│   │   │   ├── entities/             # 实体测试
│   │   │   └── domain_services/      # 领域服务测试
│   │   ├── infrastructure/           # 基础设施层测试
│   │   │   ├── evaluation/           # 评估器测试
│   │   │   └── db/repositories/      # 仓储测试
│   │   ├── application/              # 应用层测试
│   │   │   └── tasks/                # 任务测试
│   │   └── integration/              # 集成测试
│   │       └── test_evaluation_workflow.py
│   ├── common/                       # 公共模块
│   │   ├── utils/
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   └── logger.py
│   ├── main.py                       # FastAPI 入口
│   ├── requirements.txt              # 生产依赖
│   └── requirements-test.txt         # 测试依赖
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
├── docs/                             # 文档目录
│   └── 评估模块的技术设计方案.md
├── docker-compose.yml                # Docker Compose 配置
├── .env.example                      # 环境变量示例
├── .trae/                            # Trae IDE 配置
│   └── rules/                        # 编码规范
├── pytest.ini                        # Pytest 配置
└── README.md
```

## 设计原则

本项目严格遵循以下设计原则：

1. **单一职责原则 (SRP)**: 每个类和模块只负责一件事
2. **开闭原则 (OCP)**: 对扩展开放，对修改关闭
3. **依赖倒置原则 (DIP)**: 依赖抽象而非具体实现
4. **分层调用约束**: 单向依赖，外层依赖内层
5. **接口隔离原则 (ISP)**: 接口最小化，避免胖接口
6. **迪米特法则 (LoD)**: 最少知识原则
7. **里氏替换原则 (LSP)**: 子类可以替换父类

## 开发指南

### 添加新的 Agent

1. 在 `domain/agents/` 中创建新的 Agent 类，继承自 `BaseAgent`
2. 在 `domain/domain_services/` 中创建对应的领域服务
3. 在 `application/workflow/graph.py` 中添加新的工作流节点
4. 在 `api/dependencies.py` 中添加依赖注入

### 添加新的搜索源

1. 在 `infrastructure/search/` 中实现 `SearchSource` 接口
2. 在 `infrastructure/search/factory.py` 中注册新的搜索源
3. 在 `infrastructure/config.py` 中添加配置

### 评估模块

本项目集成了报告质量评估模块，包含 5 个评估指标：

| 指标 | 说明 | 实现方式 |
|------|------|----------|
| Faithfulness | 事实一致性 | RAGAS |
| Context Relevancy | 上下文相关性 | RAGAS |
| Coverage | 覆盖度 | LLM-as-Judge |
| Structure | 结构完整性 | LLM-as-Judge |
| Professional Depth | 专业深度 | 规则评估 |

评估在报告生成后**异步执行**，不影响前端响应。评估结果存储在数据库中，供开发人员分析。

## 许可证

MIT License

