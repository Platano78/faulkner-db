import time
import logging
from functools import wraps
from typing import Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Metrics storage
tool_usage_count: Dict[str, int] = {}
error_counts: Dict[str, int] = {}
response_times: Dict[str, float] = {}
knowledge_growth: Dict[str, int] = {
    'decisions': 0,
    'patterns': 0,
    'failures': 0
}


def track_tool(func):
    """Decorator to track tool usage, errors, and response times."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        func_name = func.__name__
        
        try:
            result = await func(*args, **kwargs)
            
            # Update metrics
            tool_usage_count[func_name] = tool_usage_count.get(func_name, 0) + 1
            response_times[func_name] = round(time.time() - start_time, 3)
            
            logger.info(f"Tool {func_name} completed in {response_times[func_name]}s")
            return result
            
        except Exception as e:
            error_counts[func_name] = error_counts.get(func_name, 0) + 1
            logger.error(f"Tool {func_name} failed: {str(e)}")
            raise e
            
    return wrapper


def get_metrics() -> Dict:
    """Return all collected metrics."""
    return {
        'tool_usage': tool_usage_count,
        'errors': error_counts,
        'response_times': response_times,
        'knowledge_growth': knowledge_growth
    }
