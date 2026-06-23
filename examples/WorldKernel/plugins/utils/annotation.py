"""Annotation helpers for marking agent-callable plugin methods."""

import inspect
from functools import wraps
from typing import Any, Callable, Dict, List


def AgentCall(func: Callable) -> Callable:
    """Decorator: mark a method as callable by an agent."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        return await func(*args, **kwargs)

    wrapper._is_agent_call = True
    wrapper._original_func = func
    return wrapper


def prepare_with_metadata(plugin_instance: Any, annotation_type: str) -> List[Dict[str, Any]]:
    """Extract annotated methods and their signatures from a plugin instance."""
    methods: List[Dict[str, Any]] = []
    for name, method in inspect.getmembers(plugin_instance, predicate=inspect.ismethod):
        if getattr(method, "_is_agent_call", False):
            sig = inspect.signature(method)
            methods.append(
                {
                    "name": name,
                    "method": method,
                    "signature": sig,
                    "parameters": {
                        param_name: {
                            "annotation": param.annotation,
                            "default": param.default
                            if param.default != inspect.Parameter.empty
                            else None,
                        }
                        for param_name, param in sig.parameters.items()
                    },
                    "doc": inspect.getdoc(method) or "",
                }
            )
    return methods
