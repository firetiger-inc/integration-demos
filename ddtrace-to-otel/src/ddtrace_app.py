#!/usr/bin/env python3
"""
DDTrace Web Application Simulator

Simple web application with ddtrace instrumentation.
Run with: ddtrace-run python ddtrace_app.py

DDTrace automatically sends traces to localhost:8126 (DataDog agent port).
OpenTelemetry collector with DataDog receiver captures and converts them.
"""

import time
import random
import logging
import threading
import uuid
import argparse

# Pure ddtrace imports - no OpenTelemetry dependencies
from ddtrace import tracer
from ddtrace.ext import http, db

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ddtrace-webapp")

class WebAppSimulator:
    """Simulate a web application with ddtrace instrumentation"""
    
    # Simulated endpoints
    ENDPOINTS = [
        "/api/users",
        "/api/orders", 
        "/api/products",
        "/api/inventory",
        "/api/payments",
        "/api/analytics",
        "/api/search",
        "/api/recommendations"
    ]
    
    HTTP_METHODS = ["GET", "POST", "PUT", "DELETE"]
    
    # Service dependencies
    SERVICES = {
        "user-service": ["database", "cache"],
        "order-service": ["database", "payment-service", "inventory-service"],
        "product-service": ["database", "search-service"],
        "payment-service": ["external-payment-api"],
        "inventory-service": ["database", "warehouse-api"],
        "analytics-service": ["database", "data-warehouse"],
        "search-service": ["elasticsearch"],
        "recommendation-service": ["ml-service", "database"]
    }
    
    def __init__(self):
        """Initialize the simulator with ddtrace configuration"""
        # Set global tags
        tracer.set_tags({
            "env": "demo",
            "version": "1.0.0"
        })
        
        logger.info("Initialized DDTrace web application simulator")
        logger.info("DDTrace will send traces to localhost:8126 (DataDog agent port)")
    
    def simulate_database_operation(self, operation, table, duration_ms=None):
        """Simulate a database operation with ddtrace"""
        duration = duration_ms or random.uniform(10, 100)
        
        with tracer.trace("database.query", service="postgresql") as span:
            span.set_tag("db.system", "postgresql")
            span.set_tag("db.name", "webapp_db") 
            span.set_tag("db.statement", f"{operation.upper()} FROM {table}")
            span.set_tag("db.table", table)
            span.set_tag("db.rows_affected", random.randint(1, 10))
            span.set_tag("component", "postgresql")
            
            # Simulate processing time
            time.sleep(duration / 1000.0)
            
            # Occasionally simulate database errors
            if random.random() < 0.02:  # 2% error rate
                span.set_tag("error.msg", "Connection timeout")
                span.set_tag("error.type", "DatabaseError")
                span.error = 1
                logger.warning(f"Database error for {operation} on {table}")
                raise Exception("Database connection timeout")
            
            return f"DB {operation} completed"
    
    def simulate_http_request(self, service, endpoint, method="GET"):
        """Simulate an HTTP request to another service"""
        duration = random.uniform(50, 300)
        
        with tracer.trace("http.request", service=service) as span:
            span.set_tag(http.METHOD, method)
            span.set_tag(http.URL, f"http://{service}:8080{endpoint}")
            span.set_tag("component", "requests")
            span.set_tag("span.kind", "client")
            
            # Simulate processing time
            time.sleep(duration / 1000.0)
            
            # Occasionally simulate HTTP errors
            if random.random() < 0.05:  # 5% error rate
                status_code = random.choice([500, 502, 503, 504])
                span.set_tag(http.STATUS_CODE, status_code)
                span.set_tag("error.msg", f"HTTP {status_code} error")
                span.error = 1
                logger.warning(f"HTTP error {status_code} calling {service}")
                return status_code
            else:
                status_code = random.choice([200, 201, 204])
                span.set_tag(http.STATUS_CODE, status_code)
                return status_code
    
    def simulate_cache_operation(self, operation, key):
        """Simulate a cache operation"""
        with tracer.trace("cache.operation", service="redis") as span:
            span.set_tag("cache.operation", operation)
            span.set_tag("cache.key", key)
            span.set_tag("component", "redis")
            span.set_tag("db.type", "redis")
            
            # Simulate cache hit/miss
            if operation == "get":
                hit = random.random() < 0.8  # 80% cache hit rate
                span.set_tag("cache.hit", hit)
                if not hit:
                    span.set_tag("cache.miss", True)
            
            # Fast cache operations
            time.sleep(random.uniform(1, 5) / 1000.0)
    
    def simulate_external_api_call(self, api_name, endpoint):
        """Simulate a call to an external API"""
        duration = random.uniform(100, 500)
        
        with tracer.trace("external.api", service=api_name) as span:
            span.set_tag(http.METHOD, "POST")
            span.set_tag(http.URL, f"https://{api_name}.example.com{endpoint}")
            span.set_tag("component", "http_client")
            span.set_tag("span.kind", "client")
            span.set_tag("external.service", api_name)
            
            time.sleep(duration / 1000.0)
            
            # External APIs can be flaky
            if random.random() < 0.08:  # 8% error rate
                status_code = random.choice([400, 401, 429, 500, 502, 503])
                span.set_tag(http.STATUS_CODE, status_code)
                span.set_tag("error.msg", f"External API error: {status_code}")
                span.error = 1
                return status_code
            else:
                status_code = 200
                span.set_tag(http.STATUS_CODE, status_code)
                return status_code
    
    def process_user_request(self, user_id, endpoint, method):
        """Process a complete user request through multiple services"""
        request_id = uuid.uuid4().hex[:8]
        
        with tracer.trace("web.request", service="webapp") as root_span:
            root_span.set_tag("user.id", user_id)
            root_span.set_tag("request.id", request_id)
            root_span.set_tag(http.METHOD, method)
            root_span.set_tag(http.URL, f"https://webapp.example.com{endpoint}")
            root_span.set_tag("span.kind", "server")
            
            try:
                # Simulate authentication
                with tracer.trace("auth.verify", service="auth-service") as auth_span:
                    auth_span.set_tag("user.id", user_id)
                    auth_span.set_tag("component", "auth")
                    time.sleep(random.uniform(5, 15) / 1000.0)
                    
                    if random.random() < 0.01:  # 1% auth failure
                        auth_span.set_tag("error.msg", "Invalid token")
                        auth_span.error = 1
                        root_span.set_tag(http.STATUS_CODE, 401)
                        return 401
                
                # Determine service and dependencies
                service_name = self.get_service_for_endpoint(endpoint)
                dependencies = self.SERVICES.get(service_name, ["database"])
                
                # Process business logic
                with tracer.trace("business.process", service=service_name) as business_span:
                    business_span.set_tag("endpoint", endpoint)
                    business_span.set_tag("service.name", service_name)
                    
                    # Process dependencies
                    for dependency in dependencies:
                        try:
                            if dependency == "database":
                                table = self.get_table_for_endpoint(endpoint)
                                operation = "SELECT" if method == "GET" else "INSERT"
                                self.simulate_database_operation(operation, table)
                                
                            elif dependency == "cache":
                                cache_key = f"{endpoint}:{user_id}"
                                self.simulate_cache_operation("get", cache_key)
                                
                            elif dependency.endswith("-service"):
                                status = self.simulate_http_request(dependency, "/health")
                                if status >= 500:
                                    business_span.set_tag("error.msg", f"Dependency {dependency} failed")
                                    business_span.error = 1
                                    
                            elif dependency.endswith("-api"):
                                status = self.simulate_external_api_call(dependency, "/api/v1/process")
                                if status >= 400:
                                    business_span.set_tag("error.msg", f"External API {dependency} failed")
                                    if status >= 500:
                                        business_span.error = 1
                                        
                        except Exception as e:
                            business_span.set_tag("error.msg", str(e))
                            business_span.error = 1
                            root_span.set_tag(http.STATUS_CODE, 500)
                            return 500
                
                # Success
                status_code = 200 if method == "GET" else 201
                root_span.set_tag(http.STATUS_CODE, status_code)
                return status_code
                
            except Exception as e:
                root_span.set_tag("error.msg", str(e))
                root_span.set_tag("error.type", type(e).__name__)
                root_span.error = 1
                root_span.set_tag(http.STATUS_CODE, 500)
                return 500
    
    def get_service_for_endpoint(self, endpoint):
        """Map endpoint to service name"""
        mapping = {
            "/api/users": "user-service",
            "/api/orders": "order-service",
            "/api/products": "product-service",
            "/api/inventory": "inventory-service",
            "/api/payments": "payment-service",
            "/api/analytics": "analytics-service",
            "/api/search": "search-service",
            "/api/recommendations": "recommendation-service"
        }
        return mapping.get(endpoint, "web-service")
    
    def get_table_for_endpoint(self, endpoint):
        """Map endpoint to database table"""
        mapping = {
            "/api/users": "users",
            "/api/orders": "orders",
            "/api/products": "products",
            "/api/inventory": "inventory",
            "/api/payments": "transactions",
            "/api/analytics": "events",
            "/api/search": "search_index",
            "/api/recommendations": "user_preferences"
        }
        return mapping.get(endpoint, "data")
    
    def generate_traces_worker(self, worker_id, num_requests, interval, user_count):
        """Worker function to generate traces"""
        successful_requests = 0
        error_requests = 0
        
        for i in range(num_requests):
            user_id = f"user_{random.randint(1, user_count)}"
            endpoint = random.choice(self.ENDPOINTS)
            method = random.choice(self.HTTP_METHODS)
            
            try:
                status_code = self.process_user_request(user_id, endpoint, method)
                
                if status_code < 400:
                    successful_requests += 1
                else:
                    error_requests += 1
                    
            except Exception as e:
                error_requests += 1
                logger.error(f"Worker {worker_id} error: {e}")
            
            time.sleep(interval)
        
        logger.info(f"Worker {worker_id}: {successful_requests}/{num_requests} successful, {error_requests} errors")
    
    def run_simulation(self, num_requests=100, num_workers=5, interval_ms=100, user_count=50):
        """Run the trace generation simulation"""
        interval_seconds = interval_ms / 1000.0
        
        logger.info(f"Starting DDTrace simulation with {num_workers} workers")
        logger.info(f"Generating {num_requests} requests per worker, interval: {interval_ms}ms")
        logger.info(f"Simulating {user_count} users across {len(self.ENDPOINTS)} endpoints")
        
        threads = []
        for worker_id in range(num_workers):
            thread = threading.Thread(
                target=self.generate_traces_worker,
                args=(worker_id, num_requests, interval_seconds, user_count)
            )
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        logger.info("DDTrace simulation completed")
        time.sleep(1)  # Allow final traces to be sent

def main():
    """Parse arguments and run the simulator"""
    parser = argparse.ArgumentParser(description='DDTrace Web Application Simulator')
    parser.add_argument('--requests', type=int, default=100, help='Requests per worker')
    parser.add_argument('--workers', type=int, default=5, help='Number of workers')
    parser.add_argument('--interval', type=str, default='100ms', help='Interval between requests')
    parser.add_argument('--users', type=int, default=50, help='Number of simulated users')
    
    args = parser.parse_args()
    
    # Parse interval
    if args.interval.endswith('ms'):
        interval_ms = int(args.interval[:-2])
    elif args.interval.endswith('s'):
        interval_ms = int(float(args.interval[:-1]) * 1000)
    else:
        interval_ms = int(args.interval)
    
    simulator = WebAppSimulator()
    simulator.run_simulation(
        num_requests=args.requests,
        num_workers=args.workers,
        interval_ms=interval_ms,
        user_count=args.users
    )

if __name__ == "__main__":
    main()