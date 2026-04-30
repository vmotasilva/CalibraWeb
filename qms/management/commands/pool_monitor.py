"""
Django management command: pool_monitor
========================================

Monitor and manage PgBouncer connection pool status and health.

Usage:
    python manage.py pool_monitor --stats
    python manage.py pool_monitor --health
    python manage.py pool_monitor --pools
    python manage.py pool_monitor --databases
    python manage.py pool_monitor --all
    python manage.py pool_monitor --watch 10  # Watch for 10 seconds

Examples:
    # Show current pool statistics
    $ python manage.py pool_monitor --stats

    # Show connection pool health
    $ python manage.py pool_monitor --health

    # List all pools and their status
    $ python manage.py pool_monitor --pools

    # Watch pool status updates every second (30 seconds total)
    $ python manage.py pool_monitor --watch 30

    # Full report with all information
    $ python manage.py pool_monitor --all
"""

import time
import logging
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

try:
    import psycopg2
except ImportError:
    psycopg2 = None


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Monitor PgBouncer pool status and health metrics."""

    help = __doc__

    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument(
            "--stats",
            action="store_true",
            help="Show pool statistics (query counts, transaction times, etc.)",
        )

        parser.add_argument(
            "--health",
            action="store_true",
            help="Show pool health check results",
        )

        parser.add_argument(
            "--pools",
            action="store_true",
            help="Show current pool connections and status",
        )

        parser.add_argument(
            "--databases",
            action="store_true",
            help="Show configured databases",
        )

        parser.add_argument(
            "--clients",
            action="store_true",
            help="Show connected clients and their state",
        )

        parser.add_argument(
            "--all",
            action="store_true",
            help="Show all available information",
        )

        parser.add_argument(
            "--watch",
            type=int,
            metavar="SECONDS",
            help="Watch pool status for N seconds (updates every second)",
        )

        parser.add_argument(
            "--pgbouncer-host",
            default="127.0.0.1",
            help="PgBouncer host (default: 127.0.0.1)",
        )

        parser.add_argument(
            "--pgbouncer-port",
            type=int,
            default=6432,
            help="PgBouncer port (default: 6432)",
        )

        parser.add_argument(
            "--pgbouncer-user",
            default="pgbouncer",
            help="PgBouncer console user (default: pgbouncer)",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        # Show help if no arguments provided
        if not any([
            options["stats"],
            options["health"],
            options["pools"],
            options["databases"],
            options["clients"],
            options["all"],
            options["watch"],
        ]):
            self.stdout.write(self.style.WARNING("No options provided. Use --help for usage."))
            return

        # Extract pgbouncer connection options
        pgbouncer_host = options["pgbouncer_host"]
        pgbouncer_port = options["pgbouncer_port"]
        pgbouncer_user = options["pgbouncer_user"]

        # Check if watching
        if options["watch"]:
            self._watch_pools(pgbouncer_host, pgbouncer_port, pgbouncer_user, options["watch"])
            return

        # Get current database connection info
        db_config = connection.get_connection_params()

        # Execute individual reports
        if options["all"]:
            options["stats"] = True
            options["health"] = True
            options["pools"] = True
            options["databases"] = True
            options["clients"] = True

        if options["stats"]:
            self._show_stats(pgbouncer_host, pgbouncer_port, pgbouncer_user)

        if options["health"]:
            self._show_health(pgbouncer_host, pgbouncer_port)

        if options["pools"]:
            self._show_pools(pgbouncer_host, pgbouncer_port, pgbouncer_user)

        if options["databases"]:
            self._show_databases(pgbouncer_host, pgbouncer_port, pgbouncer_user)

        if options["clients"]:
            self._show_clients(pgbouncer_host, pgbouncer_port, pgbouncer_user)

    def _get_pgbouncer_connection(
        self,
        host: str,
        port: int,
        user: str,
    ) -> Optional[object]:
        """
        Get connection to pgbouncer console.

        Args:
            host: PgBouncer host
            port: PgBouncer port
            user: PgBouncer user

        Returns:
            Database connection object or None if unavailable
        """
        if not psycopg2:
            self.stdout.write(self.style.ERROR("psycopg2 required. Install with: pip install psycopg2-binary"))
            return None

        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                database="pgbouncer",
                connect_timeout=5,
            )
            return conn
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"Failed to connect to PgBouncer at {host}:{port}: {e}\n"
                    f"Make sure PgBouncer is running: pgbouncer -d config/pgbouncer.ini"
                )
            )
            return None

    def _show_stats(self, host: str, port: int, user: str) -> None:
        """Show pool statistics."""
        self.stdout.write(self.style.SUCCESS("\n=== POOL STATISTICS ===\n"))

        conn = self._get_pgbouncer_connection(host, port, user)
        if not conn:
            return

        try:
            cursor = conn.cursor()

            # Get statistics
            cursor.execute("SHOW STATS;")
            columns = [desc[0] for desc in cursor.description]

            # Display header
            header = " | ".join(f"{col:15}" for col in columns)
            self.stdout.write(self.style.HTTP_INFO(header))
            self.stdout.write("-" * len(header))

            # Display rows
            for row in cursor.fetchall():
                values = [str(val)[:15].ljust(15) for val in row]
                self.stdout.write(" | ".join(values))

            cursor.close()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
        finally:
            conn.close()

    def _show_pools(self, host: str, port: int, user: str) -> None:
        """Show connection pools status."""
        self.stdout.write(self.style.SUCCESS("\n=== CONNECTION POOLS ===\n"))

        conn = self._get_pgbouncer_connection(host, port, user)
        if not conn:
            return

        try:
            cursor = conn.cursor()

            # Get pool information
            cursor.execute("SHOW POOLS;")
            columns = [desc[0] for desc in cursor.description]

            # Display header
            header = " | ".join(f"{col:12}" for col in columns)
            self.stdout.write(self.style.HTTP_INFO(header))
            self.stdout.write("-" * len(header))

            # Display rows
            for row in cursor.fetchall():
                values = [str(val)[:12].ljust(12) for val in row]
                self.stdout.write(" | ".join(values))

            cursor.close()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
        finally:
            conn.close()

    def _show_databases(self, host: str, port: int, user: str) -> None:
        """Show configured databases."""
        self.stdout.write(self.style.SUCCESS("\n=== CONFIGURED DATABASES ===\n"))

        conn = self._get_pgbouncer_connection(host, port, user)
        if not conn:
            return

        try:
            cursor = conn.cursor()

            # Get database information
            cursor.execute("SHOW DATABASES;")
            columns = [desc[0] for desc in cursor.description]

            # Display header
            header = " | ".join(f"{col:15}" for col in columns)
            self.stdout.write(self.style.HTTP_INFO(header))
            self.stdout.write("-" * len(header))

            # Display rows
            for row in cursor.fetchall():
                values = [str(val)[:15].ljust(15) for val in row]
                self.stdout.write(" | ".join(values))

            cursor.close()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
        finally:
            conn.close()

    def _show_clients(self, host: str, port: int, user: str) -> None:
        """Show connected clients."""
        self.stdout.write(self.style.SUCCESS("\n=== CONNECTED CLIENTS ===\n"))

        conn = self._get_pgbouncer_connection(host, port, user)
        if not conn:
            return

        try:
            cursor = conn.cursor()

            # Get client information
            cursor.execute("SHOW CLIENTS;")
            columns = [desc[0] for desc in cursor.description]

            # Display header
            header = " | ".join(f"{col:12}" for col in columns)
            self.stdout.write(self.style.HTTP_INFO(header))
            self.stdout.write("-" * len(header))

            # Display rows
            for row in cursor.fetchall():
                values = [str(val)[:12].ljust(12) for val in row]
                self.stdout.write(" | ".join(values))

            cursor.close()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
        finally:
            conn.close()

    def _show_health(self, host: str, port: int) -> None:
        """Show pool health status."""
        self.stdout.write(self.style.SUCCESS("\n=== POOL HEALTH ===\n"))

        from config.database_pooling import PoolingHealthCheck

        check = PoolingHealthCheck()
        is_healthy, errors = check.run_all_checks()

        if is_healthy:
            self.stdout.write(self.style.SUCCESS("✓ Pool is healthy"))
        else:
            self.stdout.write(self.style.ERROR("✗ Pool has issues:\n"))
            for error in errors:
                self.stdout.write(f"  • {error}")

    def _watch_pools(self, host: str, port: int, user: str, duration: int) -> None:
        """Watch pool status updates."""
        self.stdout.write(
            self.style.SUCCESS(
                f"\n=== WATCHING POOL STATUS ({duration}s) ===\n"
                "Press Ctrl+C to stop\n"
            )
        )

        start_time = time.time()
        iteration = 0

        try:
            while time.time() - start_time < duration:
                iteration += 1
                elapsed = int(time.time() - start_time)

                self.stdout.write(f"\n[{elapsed}s] Update #{iteration} at {time.strftime('%H:%M:%S')}\n")

                conn = self._get_pgbouncer_connection(host, port, user)
                if conn:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("SHOW POOLS;")

                        # Display brief status
                        for row in cursor.fetchall():
                            database = row[0]
                            user = row[1]
                            cl_active = row[2]
                            cl_waiting = row[3]
                            sv_active = row[4]
                            sv_idle = row[5]

                            status_line = (
                                f"{database:15} | "
                                f"Client: {cl_active:3} active, {cl_waiting:3} waiting | "
                                f"Server: {sv_active:3} active, {sv_idle:3} idle"
                            )
                            self.stdout.write(status_line)

                        cursor.close()
                        conn.close()
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error: {e}"))
                else:
                    break

                # Sleep before next update
                time.sleep(1)

        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\n\nWatching stopped."))
