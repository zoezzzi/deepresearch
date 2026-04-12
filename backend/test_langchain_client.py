"""测试 LangChainClient 调用和返回数据"""
import asyncio
from infrastructure.llm.langchain_client import LangChainClient

async def test_chat():
    """测试聊天功能"""
    print("Testing LangChainClient chat functionality...")
    
    try:
        # 创建客户端实例
        client = LangChainClient()
        
        # 测试简单的聊天
        response = await client.chat([
            {"role": "user", "content": "Hello, how are you?"}
        ])
        
        print(f"Response: {response}")
        print("Test passed! Client returned data successfully.")
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chat())