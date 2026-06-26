import logging
import time

from langchain.agents.middleware import wrap_model_call

logger = logging.getLogger("novel_agent.ai")


@wrap_model_call
async def logging_middleware(request, handler):
    """记录模型调用的耗时和基本信息"""
    start = time.time()
    response = await handler(request)
    elapsed = time.time() - start
    logger.info("Model call completed in %.2fs", elapsed)
    return response
