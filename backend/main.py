import asyncio
import selectors
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from harness.config import get_harness_settings
from harness.logger import logger
from app.infrastructure.db.session import init_db
from harness.db.async_pool import init_connection_pool, close_connection_pool, get_pool_stats, check_pool_health
from app.research_assistant.workflow.saver import setup_checkpointer, get_saver_manager
from api.controllers import research_router

from app.scenarios.research_assistant import register_research_assistant
from app.scenarios.registry import ScenarioRegistry

# Windows 平台需要设置 SelectorEventLoop 以兼容 psycopg
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    logger.info("Windows 平台: 已设置 WindowsSelectorEventLoopPolicy")

settings = get_harness_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理器
    
    在应用启动时初始化连接池和 AsyncPostgresSaver，失败则阻止应用启动。
    在应用关闭时清理资源。
    """
    logger.info("=" * 60)
    logger.info("应用启动中...")
    logger.info("=" * 60)
    
    # 注册场景
    logger.info("注册场景...")
    register_research_assistant()
    logger.info(f"已注册 {len(ScenarioRegistry.list_executors())} 个场景")
    
    # 初始化同步数据库
    logger.info("初始化同步数据库...")
    try:
        init_db()
        logger.info("同步数据库初始化完成")
    except Exception as e:
        logger.error(f"同步数据库初始化失败: {e}")
        raise RuntimeError(f"同步数据库初始化失败: {e}") from e
    
    # 准备报告存储目录
    reports_path = Path(settings.REPORT_STORAGE_PATH)
    reports_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"报告存储目录已准备: {reports_path}")
    
    # 初始化异步数据库连接池（关键组件，失败则阻止启动）
    logger.info("初始化异步数据库连接池...")
    try:
        pool = await init_connection_pool()
        
        # 验证连接池健康状态
        is_healthy = await pool.health_check()
        if not is_healthy:
            raise RuntimeError("连接池健康检查失败")
        
        logger.info("异步数据库连接池初始化完成且健康")
        
    except Exception as e:
        logger.error(f"异步数据库连接池初始化失败: {e}")
        logger.error("连接池是核心组件，应用无法启动")
        raise RuntimeError(f"异步数据库连接池初始化失败: {e}") from e
    
    # 强制初始化并验证 AsyncPostgresSaver（关键组件，失败则阻止启动）
    logger.info("初始化并验证 AsyncPostgresSaver...")
    try:
        saver_manager = get_saver_manager()
        await saver_manager.initialize_and_verify()
        logger.info("AsyncPostgresSaver 初始化并验证成功")
    except Exception as e:
        logger.error(f"AsyncPostgresSaver 初始化失败: {e}")
        logger.error("持久化存储是核心组件，应用无法启动")
        raise RuntimeError(f"应用启动失败: 无法初始化持久化存储 - {e}") from e
    
    # 初始化 LangGraph checkpoint 表（关键组件，失败则阻止启动）
    logger.info("初始化 LangGraph checkpoint 表...")
    try:
        await setup_checkpointer()
        logger.info("LangGraph checkpoint 表初始化完成")
    except Exception as e:
        logger.error(f"LangGraph checkpoint 表初始化失败: {e}")
        logger.error("Checkpoint 表是核心组件，应用无法启动")
        raise RuntimeError(f"应用启动失败: 无法初始化 checkpoint 表 - {e}") from e
    
    logger.info("=" * 60)
    logger.info("应用启动完成")
    logger.info("=" * 60)
    
    yield  # 应用运行期间
    
    # 应用关闭时的清理工作
    logger.info("=" * 60)
    logger.info("应用关闭中...")
    logger.info("=" * 60)
    
    try:
        saver_manager = get_saver_manager()
        await saver_manager.close()
        logger.info("AsyncPostgresSaver 已关闭")
    except Exception as e:
        logger.error(f"关闭 AsyncPostgresSaver 时出错: {e}")
    
    try:
        await close_connection_pool()
        logger.info("异步数据库连接池已关闭")
    except Exception as e:
        logger.error(f"关闭异步数据库连接池时出错: {e}")
    
    logger.info("=" * 60)
    logger.info("应用关闭完成")
    logger.info("=" * 60)


app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(research_router)


@app.get("/")
async def root():
    logger.info("Root endpoint called")
    return {"message": "Welcome to DeepResearch", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """健康检查端点"""
    health_status = {"status": "healthy", "components": {}}
    
    # 检查数据库连接池
    try:
        pool_healthy = await check_pool_health()
        health_status["components"]["database_pool"] = {
            "status": "healthy" if pool_healthy else "unhealthy"
        }
        if not pool_healthy:
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["components"]["database_pool"] = {
            "status": "unavailable",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    return health_status


@app.get("/health/db-pool-stats")
async def db_pool_stats():
    """数据库连接池统计信息端点"""
    try:
        stats = await get_pool_stats()
        return {
            "status": "success",
            "data": stats
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
