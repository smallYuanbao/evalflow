"""Celery 任务队列:评测执行入队由 worker 消费(Ch10)。execute_run 保持纯函数,这里薄包装。"""
from celery import Celery

from backend.config import settings

celery_app = Celery(
    "evalflow",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_acks_late=True,           # worker 崩溃消息不丢,由 broker 重投
    worker_prefetch_multiplier=1,  # 不囤积任务,多 worker 均衡分发
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)


@celery_app.task(name="evalflow.execute_run")
def run_task(run_id: int) -> None:
    """入队入口:worker 消费后执行真实评测逻辑(纯函数在 run_service.execute_run)。"""
    from backend.run_service import execute_run
    execute_run(run_id)
