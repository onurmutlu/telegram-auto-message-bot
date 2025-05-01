from celery import Celery
from celery.schedules import crontab
import os

# Celery yapılandırması
celery_app = Celery(
    'telegram_bot',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0',
    include=['bot.tasks']
)

# Celery ayarları
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Istanbul',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 saat
    worker_max_tasks_per_child=1000,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_ignore_result=False,
    task_store_errors_even_if_ignored=True,
    task_routes={
        'bot.tasks.*': {'queue': 'telegram_bot'},
    },
    beat_schedule={
        'discover-groups': {
            'task': 'bot.tasks.discover_groups',
            'schedule': crontab(minute='*/30'),  # Her 30 dakikada bir
        },
        'send-messages': {
            'task': 'bot.tasks.send_messages',
            'schedule': crontab(minute='*/5'),  # Her 5 dakikada bir
        },
        'update-stats': {
            'task': 'bot.tasks.update_stats',
            'schedule': crontab(minute='*/15'),  # Her 15 dakikada bir
        },
    }
)

if __name__ == '__main__':
    celery_app.start() 