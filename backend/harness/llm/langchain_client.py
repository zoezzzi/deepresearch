from typing import AsyncGenerator, List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain_core.outputs import ChatResult
from tenacity import stop_after_attempt, wait_exponential, retry_base, RetryError
from tenacity.asyncio import AsyncRetrying
from harness.llm.base import LLMClient
from harness.config import get_harness_settings
from harness.logger import logger

settings = get_harness_settings()


class LangChainClient(LLMClient):
    def __init__(self):
        self.api_key = settings.LLM_API_KEY
        self.base_url = settings.LLM_BASE_URL
        self.model = settings.LLM_MODEL_ID
        self.temperature = settings.LLM_TEMPERATURE
        self.timeout = settings.LLM_TIMEOUT
        
        if not self.api_key and hasattr(settings, 'QWEN_API_KEY'):
            self.api_key = settings.QWEN_API_KEY
            self.base_url = settings.QWEN_BASE_URL
        
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
        current_params = {**self._client_params, **override_params}
        
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
        error_str = str(error).lower()
        
        if isinstance(error, (ConnectionError, TimeoutError)):
            return True
        
        if '429' in error_str:
            return True
        if '500' in error_str or '502' in error_str or '503' in error_str:
            return True
        if '504' in error_str:
            return True
        
        if 'null' in error_str and 'choices' in error_str:
            return True
        if 'empty response' in error_str:
            return True
        
        if '401' in error_str or '403' in error_str:
            return False
        if '400' in error_str:
            return False
        if '404' in error_str:
            return False
        
        return False
    
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        model = kwargs.get("model", self.model)
        temperature = kwargs.get("temperature", self.temperature)
        timeout = kwargs.get("timeout", self.timeout)
        
        logger.info(f"[LangChainClient] Calling chat with model: {model}, timeout: {timeout}s")
        
        langchain_messages = self._convert_messages(messages)
        
        max_attempts = 2
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                client = self._get_client(model=model, temperature=temperature, timeout=timeout)
                response = await client.ainvoke(langchain_messages)
                
                result = self._parse_response(response)
                if result:
                    logger.info(f"[LangChainClient] Chat completed successfully")
                    return result
                else:
                    logger.warning(f"[LangChainClient] Empty or invalid response, will retry")
                    last_error = ValueError("Empty or invalid response from LLM API")
                    
            except Exception as e:
                last_error = e
                logger.warning(f"[LangChainClient] Attempt {attempt + 1}/{max_attempts} failed: {str(e)}")
                
                if not self._is_retryable_error(e):
                    logger.error(f"[LangChainClient] Non-retryable error, aborting: {str(e)}")
                    raise
            
            if attempt < max_attempts - 1:
                delay = min(1 * (2 ** attempt), 5)
                logger.warning(f"[LangChainClient] Retrying in {delay:.1f}s...")
                import asyncio
                await asyncio.sleep(delay)
            else:
                break
        
        logger.error(f"[LangChainClient] All retry attempts failed: {str(last_error)}")
        raise RetryError(last_error)
    
    def _parse_response(self, response: Any) -> Optional[str]:
        try:
            if response is None:
                logger.warning("[LangChainClient] Response is None")
                return None
            
            if isinstance(response, ChatResult):
                if not response.generations:
                    logger.warning("[LangChainClient] No generations in response")
                    return None
                
                generation = response.generations[0]
                if not generation or not generation.text:
                    logger.warning("[LangChainClient] Empty generation text")
                    return None
                
                return generation.text
            
            if hasattr(response, 'content'):
                content = response.content
                if content:
                    return content
                else:
                    logger.warning("[LangChainClient] Response content is empty")
                    return None
            
            if isinstance(response, str):
                return response
            
            logger.warning(f"[LangChainClient] Unknown response type: {type(response)}")
            return str(response) if response else None
            
        except Exception as e:
            logger.error(f"[LangChainClient] Error parsing response: {str(e)}")
            return None
    
    async def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        model = kwargs.get("model", self.model)
        temperature = kwargs.get("temperature", self.temperature)
        
        logger.info(f"[LangChainClient] Calling chat stream with model: {model}")
        
        langchain_messages = self._convert_messages(messages)
        
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
                
                return
                
            except (ConnectionError, TimeoutError) as e:
                if attempt < max_attempts - 1:
                    logger.warning(f"[LangChainClient] Stream connection failed, retrying: {str(e)}")
                    import asyncio
                    await asyncio.sleep(1 * (attempt + 1))
                else:
                    logger.error(f"[LangChainClient] Stream failed after {max_attempts} attempts: {str(e)}")
                    raise
            except Exception as e:
                logger.error(f"[LangChainClient] Stream error: {str(e)}")
                raise
