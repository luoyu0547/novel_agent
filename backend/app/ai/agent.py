from collections.abc import Callable
from typing import Any, Literal

from langchain.agents import AgentState, create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.ai.config import FLASH_MODEL, PRO_MODEL


def create_novel_agent(
    model_type: Literal["flash", "pro"] = "flash",
    tools: list[BaseTool] | None = None,
    system_prompt: str = "",
    state_schema: type[AgentState] | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    middleware: list[Callable[..., Any]] | None = None,
):
    model_name = FLASH_MODEL if model_type == "flash" else PRO_MODEL
    model = init_chat_model(model_name, model_provider="deepseek")
    return create_agent(
        model=model,
        tools=tools or [],
        system_prompt=system_prompt,
        state_schema=state_schema,
        checkpointer=checkpointer,
        middleware=middleware or [],
    )


def create_novel_deep_agent(
    tools: list[BaseTool] | None = None,
    system_prompt: str = "",
    state_schema: type[AgentState] | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    middleware: list[Callable[..., Any]] | None = None,
):
    model = init_chat_model(PRO_MODEL, model_provider="deepseek")
    try:
        from deepagents import create_deep_agent
    except ImportError:
        raise ImportError("deepagents package required for create_novel_deep_agent")
    return create_deep_agent(
        model=model,
        tools=tools or [],
        system_prompt=system_prompt,
        state_schema=state_schema,
        checkpointer=checkpointer,
        middleware=middleware or [],
    )
