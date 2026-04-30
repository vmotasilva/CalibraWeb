"""
Django management command to manage Flower configuration and monitoring
File: qms/management/commands/flower_manage.py
"""

from django.core.management.base import BaseCommand, CommandError
import subprocess
import os
import signal
import time
from pathlib import Path


class Command(BaseCommand):
    help = 'Manage Flower monitoring dashboard for Celery tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            type=str,
            choices=['start', 'stop', 'restart', 'status', 'config', 'logs'],
            help='Action to perform'
        )
        parser.add_argument(
            '--port',
            type=int,
            default=5555,
            help='Port to run Flower on (default: 5555)'
        )
        parser.add_argument(
            '--log-level',
            type=str,
            default='info',
            choices=['debug', 'info', 'warning', 'error', 'critical'],
            help='Logging level (default: info)'
        )
        parser.add_argument(
            '--background',
            action='store_true',
            help='Run Flower in background'
        )

    def handle(self, *args, **options):
        action = options['action']
        
        if action == 'start':
            self.start_flower(options)
        elif action == 'stop':
            self.stop_flower()
        elif action == 'restart':
            self.stop_flower()
            time.sleep(2)
            self.start_flower(options)
        elif action == 'status':
            self.status_flower()
        elif action == 'config':
            self.show_config()
        elif action == 'logs':
            self.show_logs()

    def start_flower(self, options):
        """Start Flower monitoring dashboard"""
        port = options['port']
        log_level = options['log_level']
        background = options['background']

        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('Starting Flower Monitoring'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(f'Port: {port}')
        self.stdout.write(f'Log Level: {log_level}')
        self.stdout.write(f'Background: {background}')
        self.stdout.write('')

        cmd = [
            'celery',
            '-A', 'config',
            'flower',
            f'--port={port}',
            f'--loglevel={log_level}',
            '--config=config.flower_config'
        ]

        if background:
            # Start in background
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.stdout.write(self.style.SUCCESS(f'✓ Flower started on http://localhost:{port}'))
        else:
            # Start in foreground
            try:
                self.stdout.write(self.style.WARNING('Press Ctrl+C to stop'))
                self.stdout.write('')
                subprocess.run(cmd, check=False)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING('\n✓ Flower stopped'))

    def stop_flower(self):
        """Stop Flower process"""
        self.stdout.write(self.style.WARNING('Stopping Flower...'))
        
        try:
            # Try to find and kill flower process
            result = subprocess.run(
                ['pkill', '-f', 'celery.*flower'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.stdout.write(self.style.SUCCESS('✓ Flower stopped'))
            else:
                self.stdout.write(self.style.WARNING('No Flower process found'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error stopping Flower: {str(e)}'))

    def status_flower(self):
        """Check Flower status"""
        self.stdout.write(self.style.SUCCESS('Checking Flower Status...'))
        self.stdout.write('')
        
        try:
            # Check if Flower is running
            result = subprocess.run(
                ['pgrep', '-f', 'celery.*flower'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                pid = result.stdout.strip().split('\n')[0]
                self.stdout.write(self.style.SUCCESS(f'✓ Flower is running (PID: {pid})'))
                self.stdout.write(f'Access: http://localhost:5555')
            else:
                self.stdout.write(self.style.ERROR('✗ Flower is not running'))
                self.stdout.write(self.style.WARNING('Start it with: python manage.py flower_manage start'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error checking status: {str(e)}'))

    def show_config(self):
        """Show Flower configuration"""
        self.stdout.write(self.style.SUCCESS('Flower Configuration'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write('')

        config = {
            'Port': os.getenv('FLOWER_PORT', '5555'),
            'Username': os.getenv('FLOWER_USERNAME', '<not set>'),
            'Log Level': os.getenv('FLOWER_LOG_LEVEL', 'info'),
            'Database': os.getenv('FLOWER_DB', 'flower.db'),
            'Max Tasks': os.getenv('FLOWER_MAX_TASKS', '10000'),
            'Broker URL': os.getenv('CELERY_BROKER_URL', '<not set>'),
            'Result Backend': os.getenv('CELERY_RESULT_BACKEND', '<not set>'),
        }

        for key, value in config.items():
            self.stdout.write(f'{key:.<30} {value}')

        self.stdout.write('')
        self.stdout.write(self.style.WARNING('Note: Passwords are hidden for security'))

    def show_logs(self):
        """Show Flower logs"""
        self.stdout.write(self.style.SUCCESS('Flower Logs (Last 50 lines)'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write('')

        try:
            result = subprocess.run(
                ['journalctl', '-u', 'flower', '-n', '50', '--no-pager'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.stdout.write(result.stdout)
            else:
                self.stdout.write(self.style.WARNING('Using systemd logs requires systemd integration'))
                self.stdout.write('Run Flower in foreground to see logs:')
                self.stdout.write('  python manage.py flower_manage start')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error reading logs: {str(e)}'))
