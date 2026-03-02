"""
CALIBRAWEB - LOAD TESTING SUITE
Performance and scalability validation using Locust

Tests:
- Admin interface (changelist, detail views)
- Dashboard endpoints
- Search and filtering
- Concurrent user handling
- Database query performance under load
"""

from locust import HttpUser, task, between, events
from locust.contrib.fasthttp import FastHttpUser
import random
import json
from datetime import datetime, timedelta


class AdminUser(HttpUser):
    """Simulates regular admin user"""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between requests
    
    def on_start(self):
        """Login before starting tasks"""
        self.login()
    
    def login(self):
        """Admin login"""
        response = self.client.get("/admin/login/?next=/admin/", verify=False)
        
        # Extract CSRF token
        csrf_token = None
        if 'csrftoken' in response.cookies:
            csrf_token = response.cookies['csrftoken']
        
        # Login POST
        if csrf_token:
            self.client.post(
                "/admin/login/",
                {
                    "username": "admin",
                    "password": "admin123",
                    "csrfmiddlewaretoken": csrf_token,
                },
                verify=False,
            )
    
    @task(3)
    def view_dashboard(self):
        """View admin dashboard"""
        self.client.get("/admin/", verify=False)
    
    @task(2)
    def view_instrumento_list(self):
        """View instruments list"""
        page = random.randint(1, 5)
        self.client.get(
            f"/admin/metrologia/instrumento/?p={page}",
            verify=False,
            name="/admin/metrologia/instrumento/",
        )
    
    @task(2)
    def view_instrumento_detail(self):
        """View instrument detail"""
        instrumento_id = random.randint(1, 100)
        self.client.get(
            f"/admin/metrologia/instrumento/{instrumento_id}/change/",
            verify=False,
            name="/admin/metrologia/instrumento/[id]/change/",
        )
    
    @task(2)
    def view_colaborador_list(self):
        """View employees list"""
        page = random.randint(1, 3)
        self.client.get(
            f"/admin/rh/colaborador/?p={page}",
            verify=False,
            name="/admin/rh/colaborador/",
        )
    
    @task(2)
    def view_historico_calibracao(self):
        """View calibration history"""
        self.client.get(
            "/admin/metrologia/historicocalibracao/",
            verify=False,
        )
    
    @task(1)
    def search_instrumento(self):
        """Search instruments"""
        search_term = random.choice([
            "micrometro",
            "paquimetro",
            "termometro",
            "balança",
            "medidor",
        ])
        self.client.get(
            f"/admin/metrologia/instrumento/?q={search_term}",
            verify=False,
            name="/admin/metrologia/instrumento/search",
        )


class PowerUser(FastHttpUser):
    """Heavy admin user with lots of searches and filters"""
    
    wait_time = between(0.5, 2)
    
    def on_start(self):
        """Login before starting tasks"""
        self.login()
    
    def login(self):
        """Admin login"""
        response = self.client.get("/admin/login/?next=/admin/")
        
        csrf_token = None
        if 'csrftoken' in response.cookies:
            csrf_token = response.cookies['csrftoken']
        
        if csrf_token:
            self.client.post(
                "/admin/login/",
                {
                    "username": "admin",
                    "password": "admin123",
                    "csrfmiddlewaretoken": csrf_token,
                },
            )
    
    @task(5)
    def filter_by_date(self):
        """Filter by date range"""
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")
        
        self.client.get(
            f"/admin/metrologia/historicocalibracao/?data_calibracao__gte={start_date}&data_calibracao__lte={end_date}",
            name="/admin/metrologia/historicocalibracao/filter",
        )
    
    @task(3)
    def filter_by_status(self):
        """Filter by status"""
        status = random.choice(["aprovada", "reprovada", "pendente"])
        self.client.get(
            f"/admin/metrologia/historicocalibracao/?status={status}",
            name="/admin/metrologia/historicocalibracao/filter",
        )
    
    @task(2)
    def admin_search(self):
        """Complex admin search"""
        search_terms = [
            "instrumento",
            "calibração",
            "procedimento",
            "colaborador",
            "setor",
        ]
        
        for term in search_terms:
            self.client.get(
                f"/admin/search/?q={term}",
                name="/admin/search",
            )
    
    @task(1)
    def list_with_ordering(self):
        """List with ordering"""
        ordering = random.choice(["-data_criacao", "nome", "-id"])
        self.client.get(
            f"/admin/metrologia/instrumento/?o={ordering}",
            name="/admin/metrologia/instrumento/ordered",
        )


class APIUser(HttpUser):
    """Tests API endpoints if available"""
    
    wait_time = between(1, 2)
    
    @task(3)
    def get_instruments(self):
        """Get instruments API endpoint"""
        page = random.randint(1, 5)
        self.client.get(f"/api/v1/instruments/?page={page}", verify=False)
    
    @task(2)
    def get_calibrations(self):
        """Get calibrations API endpoint"""
        self.client.get("/api/v1/calibrations/", verify=False)
    
    @task(1)
    def get_employees(self):
        """Get employees API endpoint"""
        self.client.get("/api/v1/employees/", verify=False)


# Event handlers for statistics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Print test start message"""
    print("\n" + "="*80)
    print("CALIBRAWEB - LOAD TEST STARTING")
    print("="*80)
    print(f"Target: {environment.host}")
    print(f"Started: {datetime.now().isoformat()}")
    print("="*80 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print test summary"""
    print("\n" + "="*80)
    print("LOAD TEST COMPLETED")
    print("="*80)
    
    # Collect statistics
    stats = environment.stats
    total_requests = sum(1 for _ in stats.entries)
    failed_requests = sum(1 for s in stats.entries.values() if s.fail_count > 0)
    
    print(f"Total Requests: {total_requests}")
    print(f"Failed Requests: {failed_requests}")
    print(f"Average Response Time: {stats.total.avg_response_time:.0f}ms")
    print(f"Min Response Time: {stats.total.min_response_time:.0f}ms")
    print(f"Max Response Time: {stats.total.max_response_time:.0f}ms")
    print("="*80 + "\n")


if __name__ == "__main__":
    """
    Running the load test:
    
    1. Install Locust:
       pip install locust
    
    2. Start the test:
       locust -f load_testing.py -u 50 -r 10 -t 5m --host http://localhost:8000
    
    Parameters:
    -u NUM_USERS    : Number of concurrent users
    -r SPAWN_RATE   : Users spawned per second
    -t TEST_DURATION: Duration (e.g., 5m for 5 minutes)
    --host          : Target URL
    
    Examples:
    
    # Light load: 10 users, slow ramp-up
    locust -f load_testing.py -u 10 -r 2 -t 5m --host http://localhost:8000
    
    # Medium load: 50 users
    locust -f load_testing.py -u 50 -r 10 -t 10m --host http://localhost:8000
    
    # Heavy load: 200+ users
    locust -f load_testing.py -u 200 -r 20 -t 15m --host http://localhost:8000
    
    # Interactive mode (web UI at http://localhost:8089):
    locust -f load_testing.py --host http://localhost:8000
    """
    pass
