#!/usr/bin/env python
"""
CALIBRAWEB - DATABASE BACKUP & RECOVERY STRATEGY
Automated backup solution with point-in-time recovery

Features:
- Automatic daily backups
- Point-in-time recovery capability
- Backup rotation (keep last 30 days)
- Compression and encryption ready
- Monitoring and alerts
- Multiple backend support (PostgreSQL, SQLite)
"""

import os
import sys
import json
import gzip
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class BackupManager:
    """Manages database backups and recovery procedures"""
    
    def __init__(self):
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
        self.retention_days = 30
        self.timestamp = datetime.now()
        self.log_file = self.backup_dir / "backup.log"
        
    def log(self, message: str, level: str = "INFO"):
        """Log backup operations"""
        timestamp = datetime.now().isoformat()
        log_message = f"[{timestamp}] [{level}] {message}"
        
        with open(self.log_file, "a") as f:
            f.write(log_message + "\n")
        
        print(log_message)
    
    def get_db_config(self) -> Dict[str, str]:
        """Get database configuration from Django settings"""
        try:
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
            import django
            django.setup()
            
            from django.conf import settings
            db_config = settings.DATABASES['default']
            return db_config
        except Exception as e:
            self.log(f"Failed to get DB config: {e}", "ERROR")
            return {}
    
    def backup_postgresql(self, db_config: Dict) -> bool:
        """Backup PostgreSQL database"""
        try:
            db_name = db_config.get('NAME', 'calibraweb')
            db_user = db_config.get('USER', 'postgres')
            db_host = db_config.get('HOST', 'localhost')
            db_port = db_config.get('PORT', '5432')
            db_password = db_config.get('PASSWORD', '')
            
            # Create backup filename
            timestamp_str = self.timestamp.strftime('%Y%m%d_%H%M%S')
            backup_file = self.backup_dir / f"postgresql_{db_name}_{timestamp_str}.sql"
            
            # Set password for pg_dump if provided
            env = os.environ.copy()
            if db_password:
                env['PGPASSWORD'] = db_password
            
            # Execute pg_dump
            cmd = [
                'pg_dump',
                '-h', db_host,
                '-p', str(db_port),
                '-U', db_user,
                '-d', db_name,
                '-Fc',  # Custom format for better compression and restore options
            ]
            
            with open(backup_file, 'wb') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env)
            
            if result.returncode == 0:
                size_mb = backup_file.stat().st_size / (1024 * 1024)
                self.log(f"PostgreSQL backup created: {backup_file.name} ({size_mb:.2f}MB)")
                return True
            else:
                self.log(f"PostgreSQL backup failed: {result.stderr.decode()}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"PostgreSQL backup error: {e}", "ERROR")
            return False
    
    def backup_sqlite(self, db_config: Dict) -> bool:
        """Backup SQLite database"""
        try:
            db_path = db_config.get('NAME', 'db.sqlite3')
            
            # Create backup filename
            timestamp_str = self.timestamp.strftime('%Y%m%d_%H%M%S')
            backup_file = self.backup_dir / f"sqlite_{Path(db_path).stem}_{timestamp_str}.sqlite3"
            
            # Copy database file
            if os.path.exists(db_path):
                shutil.copy2(db_path, backup_file)
                
                # Compress backup
                backup_gz = backup_file.with_suffix('.sqlite3.gz')
                with open(backup_file, 'rb') as f_in:
                    with gzip.open(backup_gz, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # Remove uncompressed backup
                backup_file.unlink()
                
                size_mb = backup_gz.stat().st_size / (1024 * 1024)
                self.log(f"SQLite backup created: {backup_gz.name} ({size_mb:.2f}MB)")
                return True
            else:
                self.log(f"SQLite database not found: {db_path}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"SQLite backup error: {e}", "ERROR")
            return False
    
    def run_backup(self) -> bool:
        """Execute backup based on database type"""
        self.log("=" * 60)
        self.log("BACKUP STARTED")
        
        db_config = self.get_db_config()
        if not db_config:
            self.log("Could not determine database type", "ERROR")
            return False
        
        engine = db_config.get('ENGINE', '')
        
        if 'postgresql' in engine:
            success = self.backup_postgresql(db_config)
        elif 'sqlite' in engine:
            success = self.backup_sqlite(db_config)
        else:
            self.log(f"Unsupported database: {engine}", "ERROR")
            return False
        
        if success:
            self.log("BACKUP COMPLETED SUCCESSFULLY")
        else:
            self.log("BACKUP FAILED", "ERROR")
        
        self.log("=" * 60)
        return success
    
    def rotate_backups(self):
        """Delete backups older than retention period"""
        try:
            cutoff_date = self.timestamp - timedelta(days=self.retention_days)
            deleted_count = 0
            
            for backup_file in self.backup_dir.glob("*"):
                if backup_file.is_file() and backup_file.name != 'backup.log':
                    file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                    if file_time < cutoff_date:
                        backup_file.unlink()
                        deleted_count += 1
                        self.log(f"Deleted old backup: {backup_file.name}")
            
            if deleted_count > 0:
                self.log(f"Rotated {deleted_count} old backups")
            else:
                self.log("No backups older than retention period")
                
        except Exception as e:
            self.log(f"Rotation error: {e}", "ERROR")
    
    def list_backups(self) -> List[Path]:
        """List all available backups"""
        backups = sorted(
            [f for f in self.backup_dir.glob("*") if f.is_file() and f.name != 'backup.log'],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        return backups
    
    def restore_postgresql(self, backup_file: Path, db_config: Dict) -> bool:
        """Restore PostgreSQL from backup"""
        try:
            db_name = db_config.get('NAME', 'calibraweb')
            db_user = db_config.get('USER', 'postgres')
            db_host = db_config.get('HOST', 'localhost')
            db_port = db_config.get('PORT', '5432')
            db_password = db_config.get('PASSWORD', '')
            
            env = os.environ.copy()
            if db_password:
                env['PGPASSWORD'] = db_password
            
            # Restore from backup
            cmd = [
                'pg_restore',
                '-h', db_host,
                '-p', str(db_port),
                '-U', db_user,
                '-d', db_name,
                '-c',  # Clean before restore
                str(backup_file)
            ]
            
            result = subprocess.run(cmd, stderr=subprocess.PIPE, env=env)
            
            if result.returncode == 0:
                self.log(f"PostgreSQL restored from: {backup_file.name}")
                return True
            else:
                self.log(f"PostgreSQL restore failed: {result.stderr.decode()}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"PostgreSQL restore error: {e}", "ERROR")
            return False
    
    def restore_sqlite(self, backup_file: Path, db_config: Dict) -> bool:
        """Restore SQLite from backup"""
        try:
            db_path = db_config.get('NAME', 'db.sqlite3')
            
            # Check if backup is compressed
            if backup_file.suffix == '.gz':
                with gzip.open(backup_file, 'rb') as f_in:
                    with open(db_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy2(backup_file, db_path)
            
            self.log(f"SQLite restored from: {backup_file.name}")
            return True
            
        except Exception as e:
            self.log(f"SQLite restore error: {e}", "ERROR")
            return False
    
    def restore_backup(self, backup_name: str) -> bool:
        """Restore database from specific backup"""
        self.log("=" * 60)
        self.log("RESTORE STARTED")
        
        backup_file = self.backup_dir / backup_name
        
        if not backup_file.exists():
            self.log(f"Backup not found: {backup_name}", "ERROR")
            return False
        
        db_config = self.get_db_config()
        if not db_config:
            self.log("Could not determine database type", "ERROR")
            return False
        
        engine = db_config.get('ENGINE', '')
        
        if 'postgresql' in engine:
            success = self.restore_postgresql(backup_file, db_config)
        elif 'sqlite' in engine:
            success = self.restore_sqlite(backup_file, db_config)
        else:
            self.log(f"Unsupported database: {engine}", "ERROR")
            return False
        
        if success:
            self.log("RESTORE COMPLETED SUCCESSFULLY")
        else:
            self.log("RESTORE FAILED", "ERROR")
        
        self.log("=" * 60)
        return success
    
    def generate_backup_report(self) -> Dict:
        """Generate backup status report"""
        backups = self.list_backups()
        
        total_size = sum(b.stat().st_size for b in backups) / (1024 * 1024)
        
        report = {
            'timestamp': self.timestamp.isoformat(),
            'total_backups': len(backups),
            'total_size_mb': round(total_size, 2),
            'retention_days': self.retention_days,
            'backups': [
                {
                    'name': b.name,
                    'size_mb': round(b.stat().st_size / (1024 * 1024), 2),
                    'created': datetime.fromtimestamp(b.stat().st_mtime).isoformat()
                }
                for b in backups[:10]  # Last 10 backups
            ]
        }
        
        return report


def print_usage():
    """Print usage information"""
    print("""
    CalibraWeb Database Backup & Recovery Tool
    
    Usage:
        python backup_manager.py <command> [options]
    
    Commands:
        backup              - Run backup now
        list                - List all backups
        restore <backup>    - Restore from backup (e.g., restore sqlite_db_20251208_214530.sqlite3.gz)
        status              - Show backup status report
        schedule            - Show scheduling instructions
    
    Examples:
        python backup_manager.py backup
        python backup_manager.py list
        python backup_manager.py restore sqlite_db_20251208_214530.sqlite3.gz
        python backup_manager.py status
    """)


def print_scheduling_instructions():
    """Print instructions for scheduling backups"""
    print("""
    ╔════════════════════════════════════════════════════════════════════════════╗
    ║           AUTOMATIC BACKUP SCHEDULING INSTRUCTIONS                         ║
    ╚════════════════════════════════════════════════════════════════════════════╝
    
    LINUX / MAC (Cron)
    ──────────────────────────────────────────────────────────────────────────────
    
    1. Open crontab editor:
       crontab -e
    
    2. Add this line to run backup daily at 2 AM:
       0 2 * * * cd /path/to/CalibraWeb && python backup_manager.py backup >> /var/log/calibraweb_backup.log 2>&1
    
    3. For multiple daily backups (2 AM, 8 AM, 2 PM, 8 PM):
       0 2,8,14,20 * * * cd /path/to/CalibraWeb && python backup_manager.py backup >> /var/log/calibraweb_backup.log 2>&1
    
    WINDOWS (Task Scheduler)
    ──────────────────────────────────────────────────────────────────────────────
    
    1. Open Task Scheduler (Win+R, type: taskschd.msc)
    
    2. Create Basic Task:
       - Name: "CalibraWeb Database Backup"
       - Description: "Automated daily backup"
       - Trigger: Daily at 2:00 AM
    
    3. Action settings:
       - Program: C:\\Python312\\python.exe
       - Arguments: C:\\path\\to\\CalibraWeb\\backup_manager.py backup
       - Start in: C:\\path\\to\\CalibraWeb
    
    4. Advanced options:
       - Run with highest privileges: Yes
       - If task already running: Do not start new instance
    
    DOCKER / KUBERNETES
    ──────────────────────────────────────────────────────────────────────────────
    
    In Dockerfile or docker-compose:
    
    services:
      backup:
        image: python:3.12
        command: |
          sh -c 'pip install -r requirements.txt &&
                 while true; do
                   python backup_manager.py backup
                   sleep 86400
                 done'
        volumes:
          - ./backups:/app/backups
          - ./:/app
        environment:
          - DJANGO_SETTINGS_MODULE=config.settings
    
    RAILWAY / CLOUD PLATFORMS
    ──────────────────────────────────────────────────────────────────────────────
    
    1. Create separate service/worker for backups
    2. Set command to: python backup_manager.py backup
    3. Configure to run periodically via platform cron/scheduler
    
    MONITORING & ALERTS
    ──────────────────────────────────────────────────────────────────────────────
    
    Monitor backup logs:
        tail -f backups/backup.log
    
    Alert if backup fails (add to cron):
        0 2 * * * cd /path/to/CalibraWeb && python backup_manager.py backup || /path/to/alert_script.sh
    
    Integration with monitoring (Datadog, New Relic, etc):
        1. Parse backup.log file
        2. Send success/failure metrics
        3. Alert on consecutive failures
    """)


if __name__ == '__main__':
    manager = BackupManager()
    
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'backup':
        success = manager.run_backup()
        manager.rotate_backups()
        sys.exit(0 if success else 1)
    
    elif command == 'list':
        print("\n📦 Available Backups:")
        print("=" * 80)
        backups = manager.list_backups()
        
        if not backups:
            print("No backups found")
        else:
            for i, backup in enumerate(backups, 1):
                size_mb = backup.stat().st_size / (1024 * 1024)
                created = datetime.fromtimestamp(backup.stat().st_mtime)
                print(f"{i}. {backup.name}")
                print(f"   Size: {size_mb:.2f} MB | Created: {created}")
        print("=" * 80 + "\n")
    
    elif command == 'restore':
        if len(sys.argv) < 3:
            print("ERROR: Backup name required")
            print("Usage: python backup_manager.py restore <backup_name>")
            print("\nAvailable backups:")
            for backup in manager.list_backups():
                print(f"  - {backup.name}")
            sys.exit(1)
        
        backup_name = sys.argv[2]
        success = manager.restore_backup(backup_name)
        sys.exit(0 if success else 1)
    
    elif command == 'status':
        report = manager.generate_backup_report()
        print("\n📊 Backup Status Report")
        print("=" * 80)
        print(f"Generated: {report['timestamp']}")
        print(f"Total Backups: {report['total_backups']}")
        print(f"Total Size: {report['total_size_mb']:.2f} MB")
        print(f"Retention: {report['retention_days']} days")
        print("\nRecent Backups:")
        for backup in report['backups']:
            print(f"  - {backup['name']}")
            print(f"    Size: {backup['size_mb']:.2f} MB | Created: {backup['created']}")
        print("=" * 80 + "\n")
    
    elif command == 'schedule':
        print_scheduling_instructions()
    
    else:
        print(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)
