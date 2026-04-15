__all__ = [
    "get_sse_manager",
    "create_research_service",
    "ResearchService"
]


def __getattr__(name):
    if name in __all__:
        from .service_factory import (
            get_sse_manager,
            create_research_service,
            ResearchService
        )
        return locals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")
