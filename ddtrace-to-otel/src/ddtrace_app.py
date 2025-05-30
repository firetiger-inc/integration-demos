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
import os

# Pure ddtrace imports - no OpenTelemetry dependencies
from ddtrace import tracer
from ddtrace.ext import http, db

# DataDog metrics (DogStatsD)
from datadog import initialize, statsd

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
        
        # Initialize DogStatsD for metrics
        dogstatsd_host = os.getenv('DD_DOGSTATSD_HOST', 'localhost')
        dogstatsd_port = int(os.getenv('DD_DOGSTATSD_PORT', '8125'))
        
        initialize(
            statsd_host=dogstatsd_host,
            statsd_port=dogstatsd_port,
            statsd_namespace='webapp'
        )
        
        logger.info("Initialized DDTrace web application simulator")
        logger.info("DDTrace will send traces to localhost:8126 (DataDog agent port)")
        logger.info(f"DogStatsD will send metrics to {dogstatsd_host}:{dogstatsd_port}")
        
        # Validate metrics configuration
        if dogstatsd_host == 'otel-collector':
            logger.warning("⚠️  METRICS ROUTING: DogStatsD configured to send to OTEL collector")
            logger.warning("⚠️  This may interfere with DataDog metrics if OTEL collector is listening on port 8125")
        elif dogstatsd_host == 'datadog-agent':
            logger.info("✅ METRICS ROUTING: DogStatsD configured to send directly to DataDog agent")
        else:
            logger.info(f"ℹ️  METRICS ROUTING: DogStatsD configured to send to custom host: {dogstatsd_host}")
        
        # Send initialization metrics with routing information
        statsd.increment('app.started', tags=[
            'env:demo', 
            'version:1.0.0', 
            f'metrics_host:{dogstatsd_host}',
            f'metrics_port:{dogstatsd_port}'
        ])
        
        # Send a test metric to validate the delivery path
        statsd.gauge('app.metrics_test.connectivity', 1, tags=[
            'test_type:connectivity',
            f'target_host:{dogstatsd_host}',
            f'target_port:{dogstatsd_port}'
        ])
        
        # Store configuration for later validation
        self.dogstatsd_host = dogstatsd_host
        self.dogstatsd_port = dogstatsd_port
    
    def simulate_database_operation(self, operation, table, duration_ms=None):
        """Simulate a database operation with ddtrace"""
        duration = duration_ms or random.uniform(10, 100)
        
        # Metrics: Start timer and increment counter
        timer_start = time.time()
        statsd.increment('database.operations.total', tags=[
            f'operation:{operation.lower()}', 
            f'table:{table}', 
            'service:postgresql'
        ])
        
        with tracer.trace("database.query", service="postgresql") as span:
            span.set_tag("db.system", "postgresql")
            span.set_tag("db.name", "webapp_db") 
            span.set_tag("db.statement", f"{operation.upper()} FROM {table}")
            span.set_tag("db.table", table)
            span.set_tag("db.rows_affected", random.randint(1, 10))
            span.set_tag("component", "postgresql")
            
            # Simulate processing time
            time.sleep(duration / 1000.0)
            
            # Metrics: Record duration
            duration_actual = (time.time() - timer_start) * 1000
            statsd.histogram('database.operations.duration', duration_actual, tags=[
                f'operation:{operation.lower()}', 
                f'table:{table}', 
                'service:postgresql'
            ])
            
            # Occasionally simulate database errors
            if random.random() < 0.02:  # 2% error rate
                span.set_tag("error.msg", "Connection timeout")
                span.set_tag("error.type", "DatabaseError")
                span.error = 1
                
                # Metrics: Record error
                statsd.increment('database.operations.errors', tags=[
                    f'operation:{operation.lower()}', 
                    f'table:{table}', 
                    'error_type:timeout',
                    'service:postgresql'
                ])
                
                logger.warning(f"Database error for {operation} on {table}")
                raise Exception("Database connection timeout")
            
            # Metrics: Record success
            statsd.increment('database.operations.success', tags=[
                f'operation:{operation.lower()}', 
                f'table:{table}', 
                'service:postgresql'
            ])
            
            return f"DB {operation} completed"
    
    def simulate_http_request(self, service, endpoint, method="GET"):
        """Simulate an HTTP request to another service"""
        duration = random.uniform(50, 300)
        
        # Metrics: Start timer and increment counter
        timer_start = time.time()
        statsd.increment('http.requests.total', tags=[
            f'service:{service}', 
            f'method:{method}', 
            'direction:outbound'
        ])
        
        with tracer.trace("http.request", service=service) as span:
            span.set_tag(http.METHOD, method)
            span.set_tag(http.URL, f"http://{service}:8080{endpoint}")
            span.set_tag("component", "requests")
            span.set_tag("span.kind", "client")
            
            # Simulate processing time
            time.sleep(duration / 1000.0)
            
            # Metrics: Record duration
            duration_actual = (time.time() - timer_start) * 1000
            statsd.histogram('http.requests.duration', duration_actual, tags=[
                f'service:{service}', 
                f'method:{method}', 
                'direction:outbound'
            ])
            
            # Occasionally simulate HTTP errors
            if random.random() < 0.05:  # 5% error rate
                status_code = random.choice([500, 502, 503, 504])
                span.set_tag(http.STATUS_CODE, status_code)
                span.set_tag("error.msg", f"HTTP {status_code} error")
                span.error = 1
                
                # Metrics: Record error
                statsd.increment('http.requests.errors', tags=[
                    f'service:{service}', 
                    f'method:{method}', 
                    f'status_code:{status_code}',
                    'direction:outbound'
                ])
                
                logger.warning(f"HTTP error {status_code} calling {service}")
                return status_code
            else:
                status_code = random.choice([200, 201, 204])
                span.set_tag(http.STATUS_CODE, status_code)
                
                # Metrics: Record success
                statsd.increment('http.requests.success', tags=[
                    f'service:{service}', 
                    f'method:{method}', 
                    f'status_code:{status_code}',
                    'direction:outbound'
                ])
                
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
        
        # Metrics: Start timer and increment request counter
        timer_start = time.time()
        statsd.increment('web.requests.total', tags=[
            f'endpoint:{endpoint}', 
            f'method:{method}', 
            'service:webapp'
        ])
        
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
                        
                        # Metrics: Record auth failure
                        duration_actual = (time.time() - timer_start) * 1000
                        statsd.histogram('web.requests.duration', duration_actual, tags=[
                            f'endpoint:{endpoint}', 
                            f'method:{method}', 
                            'status_code:401',
                            'service:webapp'
                        ])
                        statsd.increment('web.requests.errors', tags=[
                            f'endpoint:{endpoint}', 
                            f'method:{method}', 
                            'status_code:401',
                            'error_type:auth_failure',
                            'service:webapp'
                        ])
                        
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
                            
                            # Metrics: Record dependency failure
                            duration_actual = (time.time() - timer_start) * 1000
                            statsd.histogram('web.requests.duration', duration_actual, tags=[
                                f'endpoint:{endpoint}', 
                                f'method:{method}', 
                                'status_code:500',
                                'service:webapp'
                            ])
                            statsd.increment('web.requests.errors', tags=[
                                f'endpoint:{endpoint}', 
                                f'method:{method}', 
                                'status_code:500',
                                'error_type:dependency_failure',
                                'service:webapp'
                            ])
                            
                            return 500
                
                # Success
                status_code = 200 if method == "GET" else 201
                root_span.set_tag(http.STATUS_CODE, status_code)
                
                # Metrics: Record successful request
                duration_actual = (time.time() - timer_start) * 1000
                statsd.histogram('web.requests.duration', duration_actual, tags=[
                    f'endpoint:{endpoint}', 
                    f'method:{method}', 
                    f'status_code:{status_code}',
                    'service:webapp'
                ])
                statsd.increment('web.requests.success', tags=[
                    f'endpoint:{endpoint}', 
                    f'method:{method}', 
                    f'status_code:{status_code}',
                    'service:webapp'
                ])
                
                return status_code
                
            except Exception as e:
                root_span.set_tag("error.msg", str(e))
                root_span.set_tag("error.type", type(e).__name__)
                root_span.error = 1
                root_span.set_tag(http.STATUS_CODE, 500)
                
                # Metrics: Record error request
                duration_actual = (time.time() - timer_start) * 1000
                statsd.histogram('web.requests.duration', duration_actual, tags=[
                    f'endpoint:{endpoint}', 
                    f'method:{method}', 
                    'status_code:500',
                    'service:webapp'
                ])
                statsd.increment('web.requests.errors', tags=[
                    f'endpoint:{endpoint}', 
                    f'method:{method}', 
                    'status_code:500',
                    'error_type:internal_error',
                    'service:webapp'
                ])
                
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
    
    def send_validation_metrics(self):
        """Send periodic validation metrics to test delivery paths"""
        while True:
            try:
                # Send heartbeat metric
                statsd.gauge('app.metrics_test.heartbeat', 1, tags=[
                    f'target_host:{self.dogstatsd_host}',
                    f'target_port:{self.dogstatsd_port}',
                    'test_type:heartbeat'
                ])
                
                # Send timestamp metric to verify delivery
                statsd.gauge('app.metrics_test.timestamp', int(time.time()), tags=[
                    f'target_host:{self.dogstatsd_host}',
                    f'target_port:{self.dogstatsd_port}',
                    'test_type:timestamp'
                ])
                
                # Send counter that should increment
                statsd.increment('app.metrics_test.counter', tags=[
                    f'target_host:{self.dogstatsd_host}',
                    f'target_port:{self.dogstatsd_port}',
                    'test_type:counter'
                ])
                
                logger.debug(f"Sent validation metrics to {self.dogstatsd_host}:{self.dogstatsd_port}")
                time.sleep(30)  # Send validation metrics every 30 seconds
                
            except Exception as e:
                logger.error(f"Error sending validation metrics: {e}")
                time.sleep(30)

    def run_simulation(self, num_requests=100, num_workers=5, interval_ms=100, user_count=50):
        """Run the trace generation simulation"""
        interval_seconds = interval_ms / 1000.0
        
        logger.info(f"Starting DDTrace simulation with {num_workers} workers")
        logger.info(f"Generating {num_requests} requests per worker, interval: {interval_ms}ms")
        logger.info(f"Simulating {user_count} users across {len(self.ENDPOINTS)} endpoints")
        
        # Start validation metrics thread
        validation_thread = threading.Thread(
            target=self.send_validation_metrics,
            daemon=True
        )
        validation_thread.start()
        logger.info(f"Started validation metrics thread (sending to {self.dogstatsd_host}:{self.dogstatsd_port})")
        
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
        
        # Send final summary metrics
        statsd.increment('app.simulation.completed', tags=[
            f'target_host:{self.dogstatsd_host}',
            f'target_port:{self.dogstatsd_port}',
            f'workers:{num_workers}',
            f'requests_per_worker:{num_requests}'
        ])
        
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