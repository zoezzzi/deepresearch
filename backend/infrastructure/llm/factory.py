from typing import Dict, Type
from infrastructure.llm.base import LLMClient
from infrastructure.llm.langchain_client import LangChainClient
from common.config import get_settings
from common.logger import logger

settings = get_settings()


class LLMFactory:
    _clients: Dict[str, Type[LLMClient]] = {
        "qwen": LangChainClient,
        "langchain": LangChainClient,
        "openai": LangChainClient,
        "custom": LangChainClient,
        "ollama": LangChainClient,
        "lmstudio": LangChainClient
    }

    @classmethod
    def register_client(cls, name: str, client_class: Type[LLMClient]) -> None:
        cls._clients[name] = client_class
        logger.info(f"Registered LLM client: {name}")

    @classmethod
    def create_client(cls, name: str = None) -> LLMClient:
        if name is None:
            name = settings.LLM_PROVIDER
        
        if name not in cls._clients:
            raise ValueError(f"Unknown LLM client: {name}. Available: {list(cls._clients.keys())}")
        logger.info(f"Creating LLM client: {name}")
        return cls._clients[name]()


def get_llm_client(name: str = None) -> LLMClient:
    return LLMFactory.create_client(name)
