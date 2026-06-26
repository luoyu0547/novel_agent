from langchain.tools import tool, ToolRuntime

from app.ai.models import NovelAgentState


@tool
async def save_character_changes(
    changes: list[dict],
    runtime: ToolRuntime[None, NovelAgentState],
) -> str:
    """记录角色变化到待确认区。

    changes 格式: [{name, field, change_description, reason}]
    示例: [{name: "主角", field: "current_state", change_description: "得知身世真相后情绪崩溃", reason: "第5章揭露身世"}]
    """
    runtime.state["pending_confirmations"].append({
        "memory_type": "character_change",
        "data": changes,
    })
    return f"已记录 {len(changes)} 条角色变化，待用户确认"


@tool
async def save_plot_facts(
    facts: list[dict],
    runtime: ToolRuntime[None, NovelAgentState],
) -> str:
    """记录剧情事实到待确认区。

    facts 格式: [{event, characters_involved, importance, description}]
    """
    runtime.state["pending_confirmations"].append({
        "memory_type": "plot_fact",
        "data": facts,
    })
    return f"已记录 {len(facts)} 条剧情事实，待用户确认"


@tool
async def save_world_settings(
    settings: list[dict],
    runtime: ToolRuntime[None, NovelAgentState],
) -> str:
    """记录新世界观设定到待确认区。

    settings 格式: [{title, category, content}]
    category 可选: geography | faction | rule | history | culture | other
    """
    runtime.state["pending_confirmations"].append({
        "memory_type": "world_setting",
        "data": settings,
    })
    return f"已记录 {len(settings)} 条世界观设定，待用户确认"


@tool
async def save_foreshadowing_candidates(
    candidates: list[dict],
    runtime: ToolRuntime[None, NovelAgentState],
) -> str:
    """记录伏笔候选到待确认区。

    candidates 格式: [{name, description, hint, expected_reveal_after_chapter, related_characters}]
    """
    runtime.state["pending_confirmations"].append({
        "memory_type": "foreshadowing",
        "data": candidates,
    })
    return f"已记录 {len(candidates)} 条伏笔候选，待用户确认"
