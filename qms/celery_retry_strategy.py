"""
Celery retry strategy with exponential backoff, jitter, and failure handling.

Features:
- Exponential backoff with configurable base and max delay
- Jitter to prevent thundering herd
- Automatic retry with decay
- Max retry attempts
- Dead letter queue integration
- Task failure logging

Example:
    from qms.celery_retry_strategy import retry_with_backoff, get_retry_config

    @shared_task(bind=True, **get_retry_config())
    def my_task(self, data):
        try:
            # Do work
            return result
        except Exception as exc:
            retry_with_backoff(self, exc)
"""

import random
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from functools import wraps

from celery import current_task
from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded

logger = logging.getLogger(__name__)


class RetryStrategy:
    """Configuration for exponential backoff retry strategy."""
    
    def __init__(
        self,
        base_delay: int = 5,
        max_delay: int = 3600,
        max_retries: int = 12,
        backoff_multiplier: float = 2.0,
        jitter: bool = True,
        jitter_range: float = 0.1,
    ):
        """
        Initialize retry strategy.
        
        Args:
            base_delay: Initial delay in seconds (default: 5s)
            max_delay: Maximum delay between retries (default: 1h)
            max_retries: Maximum number of retry attempts
            backoff_multiplier: Multiplier for exponential backoff (default: 2.0)
            jitter: Add randomness to prevent thundering herd
            jitter_range: Jitter range as fraction of delay (default: 10%)
        
        Timeline Example (base=5s, multiplier=2.0):
        - Attempt 1: 0s (immediate)
        - Retry 1: 5s
        - Retry 2: 10s
        - Retry 3: 20s
        - Retry 4: 40s
        - Retry 5: 80s
        - Retry 6: 160s
        - ... up to max_delay
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
        self.jitter_range = jitter_range
    
    def get_delay_for_attempt(self, attempt: int) -> int:
        """
        Calculate delay for a specific attempt number.
        
        Args:
            attempt: Attempt number (0-indexed)
        
        Returns:
            Delay in seconds
        """
        if attempt == 0:
            return 0  # First attempt is immediate
        
        # Calculate exponential delay
        delay = self.base_delay * (self.backoff_multiplier ** (attempt - 1))
        
        # Cap at max_delay
        delay = min(int(delay), self.max_delay)
        
        # Add jitter
        if self.jitter:
            jitter_amount = delay * self.jitter_range
            delay = int(delay + random.uniform(-jitter_amount, jitter_amount))
            delay = max(delay, 0)  # Ensure non-negative
        
        return delay
    
    def should_retry(self, attempt: int) -> bool:
        """Check if we should retry for this attempt number."""
        return attempt < self.max_retries
    
    def get_retry_timeline(self, num_retries: Optional[int] = None) -> Dict[int, int]:
        """
        Generate complete retry timeline.
        
        Args:
            num_retries: Number of retries to show (default: max_retries)
        
        Returns:
            Dictionary mapping attempt number to delay in seconds
        """
        if num_retries is None:
            num_retries = self.max_retries
        
        timeline = {}
        for attempt in range(num_retries):
            timeline[attempt] = self.get_delay_for_attempt(attempt)
        
        return timeline
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get retry configuration as dictionary for @task decorator."""
        return {
            'autoretry_for': (Exception,),
            'retry_kwargs': {'max_retries': self.max_retries},
            'default_retry_delay': self.base_delay,
        }


# Default retry strategies for different task types
RETRY_STRATEGIES = {
    # Critical tasks: retry aggressively
    'critical': RetryStrategy(
        base_delay=5,
        max_delay=3600,
        max_retries=12,
        backoff_multiplier=2.0,
    ),
    
    # Important tasks: moderate retries
    'important': RetryStrategy(
        base_delay=10,
        max_delay=1800,
        max_retries=8,
        backoff_multiplier=2.0,
    ),
    
    # Standard tasks: normal retries
    'standard': RetryStrategy(
        base_delay=15,
        max_delay=900,
        max_retries=6,
        backoff_multiplier=2.0,
    ),
    
    # Low priority: minimal retries
    'low_priority': RetryStrategy(
        base_delay=30,
        max_delay=300,
        max_retries=3,
        backoff_multiplier=1.5,
    ),
}


def retry_with_backoff(task_self, exc: Exception, strategy: Optional[RetryStrategy] = None):
    """
    Retry a task with exponential backoff.
    
    Args:
        task_self: The task instance (self)
        exc: The exception that triggered the retry
        strategy: RetryStrategy to use (default: standard)
    
    Raises:
        Retry: Celery retry exception
    """
    if strategy is None:
        strategy = RETRY_STRATEGIES['standard']
    
    # Get current attempt count
    attempt = task_self.request.retries
    
    # Check if we should retry
    if not strategy.should_retry(attempt):
        logger.error(
            f"Task {task_self.name} failed after {attempt} retries. "
            f"Giving up. Error: {str(exc)}"
        )
        raise exc
    
    # Calculate delay
    delay = strategy.get_delay_for_attempt(attempt)
    
    # Log retry info
    logger.warning(
        f"Task {task_self.name} failed (attempt {attempt + 1}/{strategy.max_retries}). "
        f"Retrying in {delay}s. Error: {str(exc)}"
    )
    
    # Retry with delay
    raise task_self.retry(exc=exc, countdown=delay)


def get_retry_config(strategy_type: str = 'standard') -> Dict[str, Any]:
    """
    Get retry configuration for task decorator.
    
    Args:
        strategy_type: Type of strategy ('critical', 'important', 'standard', 'low_priority')
    
    Returns:
        Dictionary for @task(**get_retry_config()) decorator
    
    Example:
        @shared_task(bind=True, **get_retry_config('critical'))
        def critical_task(self):
            ...
    """
    strategy = RETRY_STRATEGIES.get(strategy_type, RETRY_STRATEGIES['standard'])
    return strategy.get_config_dict()


def retry_decorator(strategy_type: str = 'standard', dlq_handler: Optional[Callable] = None):
    """
    Decorator for automatic retry handling.
    
    Args:
        strategy_type: Retry strategy type
        dlq_handler: Optional callback for dead letter queue
    
    Example:
        @retry_decorator('critical')
        def my_function():
            ...
    """
    strategy = RETRY_STRATEGIES.get(strategy_type, RETRY_STRATEGIES['standard'])
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            last_exc = None
            
            while attempt < strategy.max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    attempt += 1
                    
                    if attempt < strategy.max_retries:
                        delay = strategy.get_delay_for_attempt(attempt)
                        logger.warning(
                            f"Function {func.__name__} failed (attempt {attempt}). "
                            f"Retrying in {delay}s. Error: {str(exc)}"
                        )
                        import time
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"Function {func.__name__} failed after {attempt} attempts. "
                            f"Error: {str(exc)}"
                        )
                        if dlq_handler:
                            dlq_handler(func.__name__, args, kwargs, exc)
            
            raise last_exc
        
        return wrapper
    
    return decorator


# ============================================================================
# CELERY TASK TIMEOUT HANDLING
# ============================================================================

class TaskTimeoutHandler:
    """Handle task timeouts with graceful degradation."""
    
    @staticmethod
    def handle_soft_timeout(task_self, exc: SoftTimeLimitExceeded):
        """
        Handle soft time limit exceeded.
        
        Soft timeout allows task to clean up before hard timeout.
        """
        logger.warning(
            f"Task {task_self.name} soft timeout. "
            f"Attempt {task_self.request.retries}. Retrying..."
        )
        
        # Retry with backoff
        retry_with_backoff(task_self, exc, RETRY_STRATEGIES['standard'])
    
    @staticmethod
    def handle_hard_timeout(task_self, exc: TimeLimitExceeded):
        """
        Handle hard time limit exceeded.
        
        Hard timeout kills task immediately. Don't retry,
        just log and move to DLQ.
        """
        logger.error(
            f"Task {task_self.name} hard timeout. "
            f"Attempt {task_self.request.retries}. Giving up."
        )
        raise exc


# ============================================================================
# FAILURE TRACKING
# ============================================================================

class TaskFailureTracker:
    """Track and aggregate task failures."""
    
    def __init__(self):
        self.failures = {}
    
    def record_failure(
        self,
        task_name: str,
        exc: Exception,
        attempt: int,
        user_id: Optional[int] = None,
    ):
        """Record a task failure."""
        key = f"{task_name}:{user_id or 'system'}"
        
        if key not in self.failures:
            self.failures[key] = []
        
        self.failures[key].append({
            'exception': str(exc),
            'attempt': attempt,
            'timestamp': datetime.now().isoformat(),
        })
        
        logger.error(
            f"Task failure recorded: {key} "
            f"(attempt {attempt}) - {str(exc)}"
        )
    
    def get_failure_stats(self, task_name: str) -> Dict[str, Any]:
        """Get failure statistics for a task."""
        failures = [
            f for key, f in self.failures.items()
            if key.startswith(task_name)
        ]
        
        if not failures:
            return {}
        
        flat_failures = [item for sublist in failures for item in sublist]
        
        return {
            'total_failures': len(flat_failures),
            'unique_errors': len(set(f['exception'] for f in flat_failures)),
            'recent_failures': flat_failures[-5:],
            'failure_rate': len(flat_failures) / (len(flat_failures) + 1),
        }
    
    def should_circuit_break(self, task_name: str, threshold: float = 0.5) -> bool:
        """Check if task should be circuit-breaker stopped."""
        stats = self.get_failure_stats(task_name)
        
        if not stats:
            return False
        
        failure_rate = stats.get('failure_rate', 0)
        return failure_rate > threshold


# Global failure tracker instance
failure_tracker = TaskFailureTracker()


def with_failure_tracking(task_name: str):
    """Decorator to track task failures."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                attempt = getattr(current_task.request, 'retries', 0)
                user_id = kwargs.get('user_id')
                
                failure_tracker.record_failure(
                    task_name,
                    exc,
                    attempt,
                    user_id
                )
                raise
        
        return wrapper
    
    return decorator


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def format_retry_timeline(timeline: Dict[int, int]) -> str:
    """Format retry timeline for display."""
    lines = []
    total_time = 0
    
    for attempt, delay in timeline.items():
        if attempt == 0:
            lines.append(f"Attempt {attempt + 1}: Immediate (0s)")
        else:
            total_time += delay
            lines.append(f"Attempt {attempt + 1}: After {delay}s ({total_time}s total)")
    
    return '\n'.join(lines)


def print_retry_timeline(strategy: RetryStrategy):
    """Print retry timeline for a strategy."""
    print(f"\n{strategy.__class__.__name__} Timeline:")
    print("=" * 60)
    timeline = strategy.get_retry_timeline()
    print(format_retry_timeline(timeline))
    print("=" * 60 + "\n")


# ============================================================================
# CELERY CONFIGURATION HELPER
# ============================================================================

def get_celery_retry_config() -> Dict[str, Any]:
    """
    Get complete Celery retry configuration.
    
    Use in celery.py settings:
        from qms.celery_retry_strategy import get_celery_retry_config
        
        celery_app.conf.update(**get_celery_retry_config())
    """
    return {
        # Task execution settings
        'task_acks_late': True,  # Acknowledge after task success
        'task_reject_on_worker_lost': True,  # Reject lost tasks
        'task_track_started': True,  # Track task start
        
        # Task timeout settings
        'task_soft_time_limit': 300,  # 5 minutes soft timeout
        'task_time_limit': 600,  # 10 minutes hard timeout
        
        # Retry settings
        'task_autoretry_for': (Exception,),
        'task_max_retries': 12,
        'task_default_retry_delay': 5,
        
        # Worker settings
        'worker_prefetch_multiplier': 1,  # Fetch one task at a time
        'worker_max_tasks_per_child': 1000,  # Recycle workers periodically
    }
