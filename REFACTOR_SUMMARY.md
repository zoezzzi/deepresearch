# DeepResearch 架构重构总结

## 概述

本次重构成功将原始的 5 层架构（API、Application、Domain、Infrastructure、Common）简化为 3 层轻量级整洁架构（API、Core、Infrastructure），去除了过度抽象，提高了代码可维护性。

## 新架构设计

```
backend/
├── api/                    # 接口层（保持不变）
│   ├── controllers/
│   ├── models/
│   └── dependencies.py
├── core/                   # 核心层（Application + Domain 合并）
│   ├── models/            # 数据模型（Entity + VO + DTO 合并）
│   ├── services/          # 业务服务（Domain Services + Application Services）
│   ├── agents/            # Agent 实现
│   ├── workflow/          # 工作流相关
│   ├── events/            # 事件相关
│   ├── tasks/             # 后台任务
│   ├── repositories/      # Repository 接口
│   ├── __init__.py
│   └── service_factory.py
├── infrastructure/        # 基础设施层（保持不变）
│   ├── db/
│   ├── llm/
│   ├── search/
│   ├── storage/
│   ├── evaluation/
│   └── sse/
└── common/                # 公共模块（保持不变）
```

## 主要改进

### 1. 去除过度抽象

- **删除的 Value Object（使用原生类型替代）**：
  - `TaskId` → `str`
  - `WorkflowId` → `str`
  - `TaskSummary` → `str`
  - `SearchQuery` → `str`
  - `TaskIntent` → `str`
  - `SourcesSummary` → `str`
  - `Notices` → `str`
  - `ReportUrl` → `str`
  - `ReportContent` → `str`

- **保留的 Value Object（有实际业务逻辑）**：
  - `WorkflowStatus` (Enum)
  - `TaskStatus` (Enum)
  - `EvaluationStatus` (Enum)

### 2. 合并重复概念

| 原位置 | 新位置 | 说明 |
|--------|--------|------|
| `domain/entities/` | `core/models/` | 简化为 Pydantic 模型 |
| `domain/value_objects/` | `core/models/` 或原生类型 | 去除过度包装 |
| `domain/aggregates/` | 移除 | 功能合并到 Entity |
| `domain/domain_services/` | `core/services/` | 业务服务 |
| `domain/agents/` | `core/agents/` | Agent 保持 |
| `domain/repositories/` | `core/repositories/` | Repository 接口 |
| `application/application_services/` | `core/services/` | 应用服务 |
| `application/dtos/` | `core/models/` | DTO 合并 |
| `application/workflow/` | `core/workflow/` | 工作流保持 |
| `application/events/` | `core/events/` | 事件保持 |
| `application/tasks/` | `core/tasks/` | 后台任务保持 |

### 3. 简化的 Entity 设计

使用 Pydantic 模型替代传统的 Entity 类，提供了：
- 自动验证
- 更简洁的代码
- 更好的类型提示
- 内置的 JSON 序列化/反序列化

### 4. 解决的问题

1. **循环导入**：通过延迟导入和 `__getattr__` 方法解决了循环依赖问题
2. **分层过深**：从 5 层减少到 3 层
3. **概念重复**：Entity、DTO、Model 高度重复的问题得到解决
4. **过度抽象**：去除了不必要的 Value Object 包装

## 文件列表

### 新增文件
- `backend/core/__init__.py` - Core 模块入口
- `backend/core/service_factory.py` - 服务工厂
- `backend/core/models/enums.py` - 枚举类型
- `backend/core/models/models.py` - 核心数据模型
- `backend/core/models/dtos.py` - DTO 模型
- `backend/core/models/__init__.py` - Models 模块入口
- `backend/core/services/research_plan_service.py` - 研究计划服务
- `backend/core/services/task_execution_service.py` - 任务执行服务
- `backend/core/services/report_generation_service.py` - 报告生成服务
- `backend/core/services/evaluation_service.py` - 评估服务
- `backend/core/services/research_service.py` - 研究主服务
- `backend/core/services/__init__.py` - Services 模块入口
- `backend/core/agents/base.py` - Agent 基类
- `backend/core/agents/plan_agent.py` - 计划 Agent
- `backend/core/agents/search_agent.py` - 搜索 Agent
- `backend/core/agents/summarizer_agent.py` - 摘要 Agent
- `backend/core/agents/generate_agent.py` - 生成 Agent
- `backend/core/agents/__init__.py` - Agents 模块入口
- `backend/core/workflow/state.py` - 工作流状态
- `backend/core/workflow/graph.py` - 工作流图
- `backend/core/workflow/saver.py` - 检查点管理器
- `backend/core/workflow/__init__.py` - Workflow 模块入口
- `backend/core/events/event_types.py` - 事件类型
- `backend/core/events/event_publisher.py` - 事件发布器
- `backend/core/events/__init__.py` - Events 模块入口
- `backend/core/tasks/evaluation_task.py` - 评估任务
- `backend/core/tasks/__init__.py` - Tasks 模块入口
- `backend/core/repositories/workflow_repository.py` - Workflow Repository 接口
- `backend/core/repositories/task_repository.py` - Task Repository 接口
- `backend/core/repositories/evaluation_repository.py` - Evaluation Repository 接口
- `backend/core/repositories/__init__.py` - Repositories 模块入口

### 修改文件
- `backend/api/models/__init__.py` - 更新导入路径
- `backend/api/dependencies.py` - 更新依赖注入
- `backend/api/controllers/research_controller.py` - 更新服务引用
- `backend/infrastructure/db/models.py` - 更新枚举导入
- `backend/infrastructure/db/repositories/workflow_repository_impl.py` - 更新实现
- `backend/infrastructure/db/repositories/task_repository_impl.py` - 更新实现
- `backend/infrastructure/db/repositories/evaluation_repository_impl.py` - 更新实现
- `backend/main.py` - 更新导入路径

### 现有但未修改的文件
- `backend/domain/` - 原有的 Domain 层（保留用于参考）
- `backend/application/` - 原有的 Application 层（保留用于参考）

## 验证结果

- ✅ 所有模块导入正常
- ✅ 主应用可以正常初始化
- ✅ 循环导入问题已解决
- ✅ Repository 实现已更新
- ✅ API 控制器已更新

## 下一步建议

1. **测试覆盖**：更新测试用例以适配新架构
2. **代码清理**：可以考虑删除旧的 `domain/` 和 `application/` 目录（保留备份）
3. **性能测试**：确保新架构没有引入性能问题
4. **文档更新**：更新相关文档以反映新的架构设计

## 总结

本次重构成功实现了架构简化，去除了过度抽象，合并了重复概念，同时保持了代码的可维护性和功能完整性。新的三层架构更加清晰，减少了代码复杂度，便于后续开发和维护。
