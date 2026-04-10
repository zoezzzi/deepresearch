from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from infrastructure.config import get_settings
from infrastructure.logger import logger
from infrastructure.db.session import init_db
from application.workflow import setup_checkpointer
from api.controllers import research_router

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(research_router)


@app.on_event("startup")
async def startup_event():
    logger.info("应用启动，初始化数据库...")
    init_db()
    reports_path = Path(settings.REPORT_STORAGE_PATH)
    reports_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"报告存储目录已准备: {reports_path}")
    
    logger.info("初始化 LangGraph checkpoint 表...")
    try:
        await setup_checkpointer()
        logger.info("LangGraph checkpoint 表初始化完成")
    except Exception as e:
        logger.error(f"LangGraph checkpoint 表初始化失败: {e}")
    
    logger.info("数据库初始化完成")


@app.get("/")
async def root():
    logger.info("Root endpoint called")
    return {"message": "Welcome to DeepResearch", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
