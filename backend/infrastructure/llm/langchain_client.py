from typing import AsyncGenerator, List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain_core.outputs import ChatResult
from tenacity import stop_after_attempt, wait_exponential, retry_base, RetryError
from tenacity.asyncio import AsyncRetrying
from infrastructure.llm.base import LLMClient
from common.config import get_settings
from common.logger import logger

settings = get_settings()


class LangChainClient(LLMClient):
    """
    LangChain LLM 客户端实现
    
    设计考虑：
    1. 复用 ChatOpenAI 客户端实例，避免频繁创建连接
    2. 优雅处理 API 返回异常（如 choices 为 null）
    3. 合理的重试策略，平衡稳定性和响应时间
    """
    
    def __init__(self):
        self.api_key = settings.LLM_API_KEY
        self.base_url = settings.LLM_BASE_URL
        self.model = settings.LLM_MODEL_ID
        self.temperature = settings.LLM_TEMPERATURE
        self.timeout = settings.LLM_TIMEOUT
        
        if not self.api_key:
            self.api_key = settings.QWEN_API_KEY
            self.base_url = settings.QWEN_BASE_URL
        
        # 复用客户端实例，避免每次请求创建新连接
        self._client = None
        self._client_params = {
            'model': self.model,
            'api_key': self.api_key,
            'base_url': self.base_url,
            'temperature': self.temperature,
            'timeout': self.timeout
        }
        
        logger.debug(f"LangChainClient initialized with model: {self.model}")
    
    def _get_client(self, **override_params) -> ChatOpenAI:
        """
        获取 ChatOpenAI 客户端实例
        
        策略：
        - 默认复用实例，减少连接开销
        - 当参数变化时创建新实例
        """
        # 检查是否有参数覆盖
        current_params = {**self._client_params, **override_params}
        
        # 如果参数变化或客户端未创建，则创建新实例
        if (self._client is None or 
            current_params.get('model') != self._client_params.get('model') or
            current_params.get('temperature') != self._client_params.get('temperature')):
            
            self._client = ChatOpenAI(
                model=current_params['model'],
                api_key=current_params['api_key'],
                base_url=current_params['base_url'],
                temperature=current_params['temperature'],
                timeout=current_params['timeout']
            )
            logger.debug(f"[LangChainClient] Created new client instance with model: {current_params['model']}")
        
        return self._client
    
    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[BaseMessage]:
        """将 OpenAI 格式的消息转换为 LangChain 格式"""
        langchain_messages = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "user":
                langchain_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
        return langchain_messages
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """
        判断错误是否可重试
        
        可重试错误：
        - 连接错误
        - 超时错误
        - 服务暂时不可用（500系列错误）
        - 空响应（可能是服务暂时问题）
        
        不可重试错误：
        - 认证错误（401/403）
        - 参数错误（400）
        - 模型不存在（404）
        """
        error_str = str(error).lower()
        
        # 连接和超时错误
        if isinstance(error, (ConnectionError, TimeoutError)):
            return True
        
        # HTTP 状态码判断
        if '429' in error_str:  # 限流
            return True
        if '500' in error_str or '502' in error_str or '503' in error_str:  # 服务端错误
            return True
        if '504' in error_str:  # 网关超时
            return True
        
        # 空响应或格式错误（可能是服务暂时问题）
        if 'null' in error_str and 'choices' in error_str:
            return True
        if 'empty response' in error_str:
            return True
        
        # 不可重试的错误
        if '401' in error_str or '403' in error_str:  # 认证错误
            return False
        if '400' in error_str:  # 参数错误
            return False
        if '404' in error_str:  # 模型不存在
            return False
        
        # 默认不重试其他错误
        return False
    
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        发送聊天请求并获取响应
        
        健壮性设计：
        1. 优雅处理 choices 为 null 的情况
        2. 合理的重试策略（最多2次重试，指数退避）
        3. 详细的错误日志
        4. 复用客户端连接
        """
        model = kwargs.get("model", self.model)
        temperature = kwargs.get("temperature", self.temperature)
        
        logger.info(f"[LangChainClient] Calling chat with model: {model}")
        
        langchain_messages = self._convert_messages(messages)
        
        # 使用简单的重试机制
        # 策略：最多2次重试，指数退避（1s, 2s），最大等待5秒
        max_attempts = 2
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                client = self._get_client(model=model, temperature=temperature)
                response = await client.ainvoke(langchain_messages)
                
                # 健壮性：处理各种异常响应
                result = self._parse_response(response)
                if result:
                    logger.info(f"[LangChainClient] Chat completed successfully")
                    return result
                else:
                    # 空响应，记录警告但继续重试
                    logger.warning(f"[LangChainClient] Empty or invalid response, will retry")
                    last_error = ValueError("Empty or invalid response from LLM API")
                    
            except Exception as e:
                last_error = e
                logger.warning(f"[LangChainClient] Attempt {attempt + 1}/{max_attempts} failed: {str(e)}")
                
                # 判断是否应该重试
                if not self._is_retryable_error(e):
                    logger.error(f"[LangChainClient] Non-retryable error, aborting: {str(e)}")
                    raise
            
            # 如果不是最后一次尝试，等待后继续
            if attempt < max_attempts - 1:
                delay = min(1 * (2 ** attempt), 5)  # 指数退避
                logger.warning(f"[LangChainClient] Retrying in {delay:.1f}s...")
                import asyncio
                await asyncio.sleep(delay)
            else:
                break
        
        # 所有重试都失败了
        logger.error(f"[LangChainClient] All retry attempts failed: {str(last_error)}")
        raise RetryError(last_error)
    
    def _parse_response(self, response: Any) -> Optional[str]:
        """
        解析 LLM 响应，处理各种异常情况
        
        返回：
        - 成功：返回内容字符串
        - 失败：返回 None（调用方决定如何处理）
        """
        try:
            # 检查响应是否为 None
            if response is None:
                logger.warning("[LangChainClient] Response is None")
                return None
            
            # 检查响应类型
            if isinstance(response, ChatResult):
                # LangChain ChatResult 类型
                if not response.generations:
                    logger.warning("[LangChainClient] No generations in response")
                    return None
                
                generation = response.generations[0]
                if not generation or not generation.text:
                    logger.warning("[LangChainClient] Empty generation text")
                    return None
                
                return generation.text
            
            # 检查是否有 content 属性（AIMessage 等）
            if hasattr(response, 'content'):
                content = response.content
                if content:
                    return content
                else:
                    logger.warning("[LangChainClient] Response content is empty")
                    return None
            
            # 检查是否为字符串
            if isinstance(response, str):
                return response
            
            # 未知类型，尝试转换为字符串
            logger.warning(f"[LangChainClient] Unknown response type: {type(response)}")
            return str(response) if response else None
            
        except Exception as e:
            logger.error(f"[LangChainClient] Error parsing response: {str(e)}")
            return None
    
    async def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """
        流式聊天请求
        
        注意：流式请求通常不重试，因为已经开始了数据传输
        但如果连接失败，可以重试整个请求
        """
        model = kwargs.get("model", self.model)
        temperature = kwargs.get("temperature", self.temperature)
        
        logger.info(f"[LangChainClient] Calling chat stream with model: {model}")
        
        langchain_messages = self._convert_messages(messages)
        
        # 流式请求只重试连接错误，不重试内容错误
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                client = self._get_client(model=model, temperature=temperature)
                
                chunk_count = 0
                async for chunk in client.astream(langchain_messages):
                    if chunk and hasattr(chunk, 'content') and chunk.content:
                        chunk_count += 1
                        yield chunk.content
                
                if chunk_count == 0:
                    logger.warning("[LangChainClient] No chunks received in stream")
                else:
                    logger.info(f"[LangChainClient] Stream completed with {chunk_count} chunks")
                
                return  # 成功完成
                
            except (ConnectionError, TimeoutError) as e:
                if attempt < max_attempts - 1:
                    logger.warning(f"[LangChainClient] Stream connection failed, retrying: {str(e)}")
                    import asyncio
                    await asyncio.sleep(1 * (attempt + 1))  # 指数退避
                else:
                    logger.error(f"[LangChainClient] Stream failed after {max_attempts} attempts: {str(e)}")
                    raise
            except Exception as e:
                logger.error(f"[LangChainClient] Stream error: {str(e)}")
                raise
