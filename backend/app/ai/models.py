from langchain.agents import AgentState


class NovelAgentState(AgentState):
    novel_id: int = 0
    chapter_id: int = 0
    user_id: int = 0
    pending_confirmations: list[dict] = []
