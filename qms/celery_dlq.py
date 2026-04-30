"""
Dead Letter Queue (DLQ) for failed tasks.

Features:
- Persistent storage of failed tasks
- Task replay capability
- Failure analysis and reporting
- Automatic recovery strategies
- Monitoring and alerting

Example:
    from qms.celery_dlq import DeadLetterQueue, dlq_handler

    dlq = DeadLetterQueue()

    @shared_task(bind=True)
    def my_task(self):
        try:
            # Task code
        except Exception as exc:
            dlq.add_failed_task(
                task_name=self.name,
                task_id=self.request.id,
                exc=exc,
                args=self.request.args,
                kwargs=self.request.kwargs,
            )
"""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class FailureReason(Enum):
    """Reasons for task failure."""
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    TIMEOUT = "timeout"
    EXCEPTION = "exception"
    WORKER_LOST = "worker_lost"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class DLQTask(models.Model):
    """Model to store failed tasks in database."""
    
    task_id = models.CharField(max_length=255, unique=True, db_index=True)
    task_name = models.CharField(max_length=255, db_index=True)
    
    # Task execution info
    args = models.JSONField(default=list)
    kwargs = models.JSONField(default=dict)
    result = models.JSONField(null=True, blank=True)
    
    # Failure info
    exception_type = models.CharField(max_length=255)
    exception_message = models.TextField()
    traceback = models.TextField(blank=True)
    
    # Metadata
    failure_reason = models.CharField(
        max_length=50,
        choices=[(f.value, f.name) for f in FailureReason],
        default=FailureReason.UNKNOWN.value
    )
    attempt_count = models.IntegerField(default=1)
    max_retries = models.IntegerField(default=12)
    
    # Timestamps
    first_failed_at = models.DateTimeField(auto_now_add=True)
    last_failed_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_resolved = models.BooleanField(default=False)
    replay_count = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'dlq_tasks'
        ordering = ['-last_failed_at']
        indexes = [
            models.Index(fields=['task_name', 'is_resolved']),
            models.Index(fields=['last_failed_at']),
        ]
    
    def __str__(self):
        return f"{self.task_name} ({self.task_id[:8]})"
    
    @property
    def days_in_dlq(self) -> int:
        """Days since task failed."""
        return (timezone.now() - self.first_failed_at).days
    
    def mark_resolved(self, notes: str = ""):
        """Mark task as resolved."""
        self.is_resolved = True
        self.resolved_at = timezone.now()
        self.notes = notes
        self.save()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API/JSON responses."""
        return {
            'task_id': self.task_id,
            'task_name': self.task_name,
            'args': self.args,
            'kwargs': self.kwargs,
            'exception_type': self.exception_type,
            'exception_message': self.exception_message,
            'failure_reason': self.failure_reason,
            'attempt_count': self.attempt_count,
            'first_failed_at': self.first_failed_at.isoformat(),
            'last_failed_at': self.last_failed_at.isoformat(),
            'is_resolved': self.is_resolved,
            'replay_count': self.replay_count,
        }


class DeadLetterQueue:
    """Main DLQ manager class."""
    
    def __init__(self, db_model=DLQTask, redis_client=None):
        """
        Initialize DLQ.
        
        Args:
            db_model: Django model for persistence
            redis_client: Optional Redis for caching
        """
        self.db_model = db_model
        self.redis = redis_client
    
    # =========================================================================
    # ADD TO DLQ
    # =========================================================================
    
    def add_failed_task(
        self,
        task_name: str,
        task_id: str,
        exc: Exception,
        args: List = None,
        kwargs: Dict = None,
        failure_reason: FailureReason = FailureReason.EXCEPTION,
        attempt_count: int = 1,
        max_retries: int = 12,
        traceback: str = "",
    ) -> DLQTask:
        """
        Add a failed task to the DLQ.
        
        Args:
            task_name: Name of the task
            task_id: Celery task ID
            exc: Exception that caused failure
            args: Task positional arguments
            kwargs: Task keyword arguments
            failure_reason: Reason for failure
            attempt_count: Number of retry attempts
            max_retries: Maximum allowed retries
            traceback: Full exception traceback
        
        Returns:
            DLQTask instance
        """
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
        
        try:
            # Try to get existing task
            dlq_task = self.db_model.objects.get(task_id=task_id)
            dlq_task.attempt_count = attempt_count
            dlq_task.last_failed_at = timezone.now()
        except self.db_model.DoesNotExist:
            # Create new task
            dlq_task = self.db_model(
                task_id=task_id,
                task_name=task_name,
                args=args,
                kwargs=kwargs,
                attempt_count=attempt_count,
                max_retries=max_retries,
            )
        
        # Update failure info
        dlq_task.exception_type = exc.__class__.__name__
        dlq_task.exception_message = str(exc)
        dlq_task.traceback = traceback
        dlq_task.failure_reason = failure_reason.value
        
        dlq_task.save()
        
        logger.error(
            f"Task added to DLQ: {task_name} ({task_id}). "
            f"Reason: {failure_reason.name}. "
            f"Attempt: {attempt_count}/{max_retries}"
        )
        
        # Cache in Redis if available
        if self.redis:
            self._cache_dlq_task(dlq_task)
        
        return dlq_task
    
    # =========================================================================
    # RETRIEVE FROM DLQ
    # =========================================================================
    
    def get_failed_tasks(
        self,
        task_name: Optional[str] = None,
        unresolved_only: bool = True,
        limit: int = 100,
    ) -> List[DLQTask]:
        """
        Get failed tasks from DLQ.
        
        Args:
            task_name: Filter by task name
            unresolved_only: Only unresolved tasks
            limit: Maximum results
        
        Returns:
            List of DLQTask instances
        """
        query = self.db_model.objects.all()
        
        if task_name:
            query = query.filter(task_name=task_name)
        
        if unresolved_only:
            query = query.filter(is_resolved=False)
        
        return list(query[:limit])
    
    def get_critical_failures(self, days: int = 1) -> List[DLQTask]:
        """Get tasks that failed multiple times recently."""
        cutoff = timezone.now() - timedelta(days=days)
        
        return list(
            self.db_model.objects.filter(
                is_resolved=False,
                last_failed_at__gte=cutoff,
                attempt_count__gt=5
            ).order_by('-attempt_count')
        )
    
    def get_task_by_id(self, task_id: str) -> Optional[DLQTask]:
        """Get specific failed task by ID."""
        try:
            return self.db_model.objects.get(task_id=task_id)
        except self.db_model.DoesNotExist:
            return None
    
    # =========================================================================
    # REPLAY/RECOVERY
    # =========================================================================
    
    def can_replay(self, dlq_task: DLQTask) -> bool:
        """Check if task can be replayed."""
        # Don't replay if already resolved
        if dlq_task.is_resolved:
            return False
        
        # Don't replay too soon after last failure
        time_since_failure = timezone.now() - dlq_task.last_failed_at
        if time_since_failure < timedelta(hours=1):
            return False
        
        return True
    
    def replay_task(self, dlq_task: DLQTask) -> Optional[str]:
        """
        Replay a failed task.
        
        Args:
            dlq_task: DLQTask instance to replay
        
        Returns:
            New Celery task ID if successful
        """
        if not self.can_replay(dlq_task):
            logger.warning(f"Cannot replay task {dlq_task.task_id}")
            return None
        
        try:
            # Import Celery app
            from qms.celery_app import app
            
            # Send task
            task_result = app.send_task(
                dlq_task.task_name,
                args=dlq_task.args,
                kwargs=dlq_task.kwargs,
                task_id=dlq_task.task_id,
            )
            
            # Update replay count
            dlq_task.replay_count += 1
            dlq_task.save()
            
            logger.info(
                f"Task replayed: {dlq_task.task_name} "
                f"({dlq_task.task_id}). "
                f"New task ID: {task_result.id}"
            )
            
            return task_result.id
        
        except Exception as e:
            logger.error(f"Replay failed for {dlq_task.task_id}: {e}")
            return None
    
    def bulk_replay(self, task_name: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """
        Replay multiple failed tasks.
        
        Args:
            task_name: Optional filter by task name
            limit: Maximum tasks to replay
        
        Returns:
            Statistics about replayed tasks
        """
        failed_tasks = self.get_failed_tasks(
            task_name=task_name,
            unresolved_only=True,
            limit=limit
        )
        
        replayed = 0
        failed = 0
        
        for dlq_task in failed_tasks:
            if self.can_replay(dlq_task):
                if self.replay_task(dlq_task):
                    replayed += 1
                else:
                    failed += 1
        
        return {
            'total': len(failed_tasks),
            'replayed': replayed,
            'failed': failed,
            'skipped': len(failed_tasks) - replayed - failed,
        }
    
    # =========================================================================
    # STATISTICS & REPORTING
    # =========================================================================
    
    def get_failure_stats(
        self,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get failure statistics."""
        cutoff = timezone.now() - timedelta(days=days)
        
        all_failures = self.db_model.objects.filter(first_failed_at__gte=cutoff)
        unresolved = all_failures.filter(is_resolved=False)
        
        # Group by task name
        by_task = {}
        for task in all_failures:
            if task.task_name not in by_task:
                by_task[task.task_name] = {
                    'count': 0,
                    'resolved': 0,
                    'reasons': {}
                }
            
            by_task[task.task_name]['count'] += 1
            if task.is_resolved:
                by_task[task.task_name]['resolved'] += 1
            
            reason = task.failure_reason
            by_task[task.task_name]['reasons'][reason] = \
                by_task[task.task_name]['reasons'].get(reason, 0) + 1
        
        return {
            'period_days': days,
            'total_failures': all_failures.count(),
            'unresolved_failures': unresolved.count(),
            'resolution_rate': (
                (all_failures.count() - unresolved.count()) / all_failures.count() * 100
                if all_failures.count() > 0 else 0
            ),
            'by_task': by_task,
        }
    
    def get_top_failures(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most frequently failing tasks."""
        tasks = self.db_model.objects\
            .filter(is_resolved=False)\
            .values('task_name')\
            .annotate(count=models.Count('id'))\
            .order_by('-count')[:limit]
        
        return list(tasks)
    
    # =========================================================================
    # CLEANUP & MAINTENANCE
    # =========================================================================
    
    def cleanup_resolved_tasks(self, days: int = 30) -> int:
        """
        Delete resolved tasks older than specified days.
        
        Args:
            days: Age threshold in days
        
        Returns:
            Number of tasks deleted
        """
        cutoff = timezone.now() - timedelta(days=days)
        
        count, _ = self.db_model.objects.filter(
            is_resolved=True,
            resolved_at__lt=cutoff
        ).delete()
        
        logger.info(f"Cleaned up {count} resolved DLQ tasks")
        return count
    
    def cleanup_old_unresolved(self, days: int = 90) -> int:
        """
        Delete unresolved tasks older than specified days.
        
        Args:
            days: Age threshold in days
        
        Returns:
            Number of tasks marked as resolved
        """
        cutoff = timezone.now() - timedelta(days=days)
        
        count = self.db_model.objects.filter(
            is_resolved=False,
            first_failed_at__lt=cutoff
        ).update(
            is_resolved=True,
            resolved_at=timezone.now(),
            notes="Auto-resolved: Task too old"
        )
        
        logger.info(f"Auto-resolved {count} old DLQ tasks")
        return count
    
    # =========================================================================
    # CACHING
    # =========================================================================
    
    def _cache_dlq_task(self, dlq_task: DLQTask):
        """Cache DLQ task in Redis."""
        if not self.redis:
            return
        
        try:
            key = f"dlq:task:{dlq_task.task_id}"
            self.redis.setex(
                key,
                86400,  # 24 hours
                json.dumps(dlq_task.to_dict())
            )
        except Exception as e:
            logger.warning(f"DLQ cache error: {e}")


# ============================================================================
# CELERY EVENT HANDLERS
# ============================================================================

def setup_dlq_handlers(dlq: DeadLetterQueue):
    """
    Setup Celery event handlers for DLQ.
    
    Should be called during Celery app initialization.
    """
    from celery import signals
    
    @signals.task_failure.connect
    def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
        """Handle task failure event."""
        dlq.add_failed_task(
            task_name=sender.name,
            task_id=task_id,
            exc=exception,
            failure_reason=FailureReason.EXCEPTION,
        )
    
    @signals.task_retry.connect
    def task_retry_handler(sender=None, task_id=None, einfo=None, **kwargs):
        """Handle task retry event."""
        logger.warning(
            f"Task {sender.name} ({task_id}) retrying. "
            f"Exception: {einfo}"
        )
    
    @signals.task_success.connect
    def task_success_handler(sender=None, result=None, **kwargs):
        """Handle task success event."""
        logger.debug(f"Task {sender.name} succeeded")


# Global DLQ instance
dlq = DeadLetterQueue()
