"""
服务器启动脚本
解决 Windows 平台上 psycopg 与 ProactorEventLoop 的兼容性问题
"""
import asyncio
import sys
import uvicorn

# 必须在导入任何其他模块之前设置事件循环策略
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print("Windows 平台: 已设置 WindowsSelectorEventLoopPolicy")

# 现在导入 main
from main import app
from common.config import get_settings

settings = get_settings()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
