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
import base64
import json
import hashlib
from datetime import datetime, timedelta

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
    
    # Authentication endpoints
    AUTH_ENDPOINTS = [
        "/auth/saml/login",
        "/auth/email/login",
        "/auth/validate"
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
    
    def simulate_database_operation(self, operation, table, user_id=None, duration_ms=None):
        """Simulate a database operation with ddtrace"""
        duration = duration_ms or random.uniform(10, 100)
        
        # Metrics: Start timer and increment counter
        timer_start = time.time()
        db_tags = [
            f'operation:{operation.lower()}', 
            f'table:{table}', 
            'service:postgresql'
        ]
        if user_id:
            db_tags.append(f'user_id:{user_id}')
        
        statsd.increment('database.operations.total', tags=db_tags)
        
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
            statsd.histogram('database.operations.duration', duration_actual, tags=db_tags)
            
            # Occasionally simulate database errors
            if random.random() < 0.02:  # 2% error rate
                span.set_tag("error.msg", "Connection timeout")
                span.set_tag("error.type", "DatabaseError")
                span.error = 1
                
                # Metrics: Record error
                error_tags = db_tags + ['error_type:timeout']
                statsd.increment('database.operations.errors', tags=error_tags)
                
                logger.warning(f"Database error for {operation} on {table}")
                raise Exception("Database connection timeout")
            
            # Metrics: Record success
            statsd.increment('database.operations.success', tags=db_tags)
            
            return f"DB {operation} completed"
    
    def simulate_http_request(self, service, endpoint, method="GET", user_id=None):
        """Simulate an HTTP request to another service"""
        duration = random.uniform(50, 300)
        
        # Metrics: Start timer and increment counter
        timer_start = time.time()
        http_tags = [
            f'service:{service}', 
            f'method:{method}', 
            'direction:outbound'
        ]
        if user_id:
            http_tags.append(f'user_id:{user_id}')
            
        statsd.increment('http.requests.total', tags=http_tags)
        
        with tracer.trace("http.request", service=service) as span:
            span.set_tag(http.METHOD, method)
            span.set_tag(http.URL, f"http://{service}:8080{endpoint}")
            span.set_tag("component", "requests")
            span.set_tag("span.kind", "client")
            
            # Simulate processing time
            time.sleep(duration / 1000.0)
            
            # Metrics: Record duration
            duration_actual = (time.time() - timer_start) * 1000
            statsd.histogram('http.requests.duration', duration_actual, tags=http_tags)
            
            # Occasionally simulate HTTP errors
            if random.random() < 0.05:  # 5% error rate
                status_code = random.choice([500, 502, 503, 504])
                span.set_tag(http.STATUS_CODE, status_code)
                span.set_tag("error.msg", f"HTTP {status_code} error")
                span.error = 1
                
                # Metrics: Record error
                error_tags = http_tags + [f'status_code:{status_code}']
                statsd.increment('http.requests.errors', tags=error_tags)
                
                logger.warning(f"HTTP error {status_code} calling {service}")
                return status_code
            else:
                status_code = random.choice([200, 201, 204])
                span.set_tag(http.STATUS_CODE, status_code)
                
                # Metrics: Record success
                success_tags = http_tags + [f'status_code:{status_code}']
                statsd.increment('http.requests.success', tags=success_tags)
                
                return status_code
    
    def generate_saml_token(self, user_id, corrupt=False):
        """Generate a SAML JWT token, optionally corrupted for user_13"""
        header = {
            "alg": "HS256",
            "typ": "JWT"
        }
        
        # Current time for token validity
        now = datetime.utcnow()
        exp = now + timedelta(hours=1)
        
        payload = {
            "iss": "https://saml.company.com",
            "sub": user_id,
            "aud": "webapp-service", 
            "exp": int(exp.timestamp()),
            "iat": int(now.timestamp()),
            "email": f"{user_id}@company.com",
            "groups": ["users", "employees"],
            "tenant_id": "company_tenant",
            "saml_session_id": uuid.uuid4().hex
        }
        
        # Base64 encode header and payload
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        
        # Create signature (simplified - just hash of header.payload)
        signature_data = f"{header_b64}.{payload_b64}".encode()
        signature = hashlib.sha256(signature_data).hexdigest()[:32]
        signature_b64 = base64.urlsafe_b64encode(signature.encode()).decode().rstrip('=')
        
        token = f"{header_b64}.{payload_b64}.{signature_b64}"
        
        if corrupt and user_id == "user_13":
            token = self.corrupt_saml_token(token, user_id)
            
        return token, payload
    
    def corrupt_saml_token(self, token, user_id):
        """Introduce subtle corruption into SAML token for user_13"""
        parts = token.split('.')
        
        corruption_type = random.choice([
            "invalid_signature",
            "malformed_header", 
            "missing_claims",
            "character_corruption"
        ])
        
        if corruption_type == "invalid_signature":
            # Corrupt the signature part
            signature = parts[2]
            if len(signature) > 5:
                # Replace a character in the middle
                mid = len(signature) // 2
                corrupted = signature[:mid] + 'X' + signature[mid+1:]
                parts[2] = corrupted
                
        elif corruption_type == "malformed_header":
            # Corrupt the algorithm in header
            header_data = json.loads(base64.urlsafe_b64decode(parts[0] + '==').decode())
            header_data["alg"] = "HS25G"  # Invalid algorithm
            corrupted_header = base64.urlsafe_b64encode(json.dumps(header_data).encode()).decode().rstrip('=')
            parts[0] = corrupted_header
            
        elif corruption_type == "missing_claims":
            # Remove required claims from payload
            payload_data = json.loads(base64.urlsafe_b64decode(parts[1] + '==').decode())
            if "exp" in payload_data:
                del payload_data["exp"]  # Remove expiration
            if "iss" in payload_data:
                payload_data["iss"] = "https://wrong-issuer.com"  # Wrong issuer
            corrupted_payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip('=')
            parts[1] = corrupted_payload
            
        elif corruption_type == "character_corruption":
            # Random character corruption in payload
            payload = parts[1]
            if len(payload) > 10:
                pos = random.randint(5, len(payload) - 5)
                corrupted = payload[:pos] + random.choice('XYZ!@#') + payload[pos+1:]
                parts[1] = corrupted
        
        return '.'.join(parts)
    
    def simulate_saml_authentication(self, user_id):
        """Simulate SAML SSO authentication with potential corruption for user_13"""
        timer_start = time.time()
        
        # Determine if this user should get corrupt tokens
        should_corrupt = (user_id == "user_13")
        
        auth_tags = [
            f'user_id:{user_id}',
            'auth_method:saml',
            'service:auth-service'
        ]
        
        statsd.increment('auth.attempts.total', tags=auth_tags)
        
        with tracer.trace("auth.saml.login", service="auth-service") as span:
            span.set_tag("user.id", user_id)
            span.set_tag("auth.method", "saml")
            span.set_tag("auth.provider", "company-saml")
            span.set_tag("component", "saml_processor")
            
            # Generate SAML token
            token, payload = self.generate_saml_token(user_id, corrupt=should_corrupt)
            
            span.set_tag("saml.token.length", len(token))
            span.set_tag("saml.session.id", payload.get("saml_session_id"))
            span.set_tag("saml.issuer", payload.get("iss"))
            span.set_tag("saml.audience", payload.get("aud"))
            
            # Log token details (would be redacted in production)
            if should_corrupt:
                span.set_tag("saml.token.status", "corrupted")
                span.set_tag("saml.token.user_config", "invalid")
                # Log partial token for debugging (first/last 20 chars)
                span.set_tag("saml.token.preview", f"{token[:20]}...{token[-20:]}")
            else:
                span.set_tag("saml.token.status", "valid")
                span.set_tag("saml.token.user_config", "valid")
            
            # Simulate token validation
            time.sleep(random.uniform(50, 150) / 1000.0)  # 50-150ms
            
            # Record metrics
            duration_actual = (time.time() - timer_start) * 1000
            statsd.histogram('auth.saml.token_validation.duration', duration_actual, tags=auth_tags)
            
            if should_corrupt:
                # SAML fails for user_13
                error_type = random.choice([
                    "invalid_signature", 
                    "malformed_token",
                    "invalid_issuer", 
                    "token_expired"
                ])
                
                span.set_tag("error.msg", f"SAML validation failed: {error_type}")
                span.set_tag("error.type", "SamlValidationError")
                span.set_tag("saml.error.type", error_type)
                span.error = 1
                
                # Metrics for SAML error
                error_tags = auth_tags + [f'error_type:{error_type}', 'status:failure']
                statsd.increment('auth.saml.errors', tags=error_tags)
                statsd.increment('auth.attempts.errors', tags=error_tags)
                
                logger.warning(f"SAML authentication failed for {user_id}: {error_type}")
                return False, error_type
            else:
                # SAML succeeds for all other users
                span.set_tag("auth.result", "success")
                span.set_tag("saml.validation.result", "valid")
                
                success_tags = auth_tags + ['status:success']
                statsd.increment('auth.attempts.success', tags=success_tags)
                
                return True, "saml_success"
    
    def simulate_email_authentication(self, user_id):
        """Simulate email/password authentication as fallback"""
        timer_start = time.time()
        
        auth_tags = [
            f'user_id:{user_id}',
            'auth_method:email',
            'service:auth-service'
        ]
        
        statsd.increment('auth.attempts.total', tags=auth_tags)
        
        with tracer.trace("auth.email.login", service="auth-service") as span:
            span.set_tag("user.id", user_id)
            span.set_tag("auth.method", "email")
            span.set_tag("auth.provider", "internal")
            span.set_tag("component", "email_auth")
            span.set_tag("email.address", f"{user_id}@company.com")
            
            # Simulate password validation
            time.sleep(random.uniform(100, 200) / 1000.0)  # 100-200ms
            
            # Email auth rarely fails (2% failure rate)
            if random.random() < 0.02:
                span.set_tag("error.msg", "Invalid credentials")
                span.set_tag("error.type", "AuthenticationError")
                span.error = 1
                
                error_tags = auth_tags + ['error_type:invalid_credentials', 'status:failure']
                statsd.increment('auth.attempts.errors', tags=error_tags)
                
                return False, "invalid_credentials"
            else:
                span.set_tag("auth.result", "success")
                
                success_tags = auth_tags + ['status:success']
                statsd.increment('auth.attempts.success', tags=success_tags)
                
                duration_actual = (time.time() - timer_start) * 1000
                statsd.histogram('auth.email.validation.duration', duration_actual, tags=auth_tags)
                
                return True, "email_success"
    
    def simulate_authentication_flow(self, user_id, endpoint):
        """Simulate complete authentication flow with SAML fallback to email"""
        with tracer.trace("auth.flow", service="webapp") as auth_span:
            auth_span.set_tag("user.id", user_id)
            auth_span.set_tag("requested.endpoint", endpoint)
            auth_span.set_tag("component", "auth_flow")
            
            # Try SAML first
            saml_success, saml_result = self.simulate_saml_authentication(user_id)
            
            if saml_success:
                auth_span.set_tag("auth.final_method", "saml")
                auth_span.set_tag("auth.result", "success")
                return True, "saml"
            else:
                # SAML failed, try email fallback
                auth_span.set_tag("auth.saml.failed", True)
                auth_span.set_tag("auth.saml.error", saml_result)
                
                # Record fallback attempt
                fallback_tags = [f'user_id:{user_id}', 'fallback_from:saml', 'fallback_to:email']
                statsd.increment('auth.fallback.attempts', tags=fallback_tags)
                
                logger.info(f"SAML failed for {user_id}, attempting email fallback")
                
                email_success, email_result = self.simulate_email_authentication(user_id)
                
                if email_success:
                    auth_span.set_tag("auth.final_method", "email")
                    auth_span.set_tag("auth.result", "success") 
                    auth_span.set_tag("auth.fallback.success", True)
                    
                    fallback_success_tags = fallback_tags + ['status:success']
                    statsd.increment('auth.fallback.success', tags=fallback_success_tags)
                    
                    return True, "email_fallback"
                else:
                    auth_span.set_tag("auth.final_method", "none")
                    auth_span.set_tag("auth.result", "failure")
                    auth_span.set_tag("auth.fallback.success", False)
                    auth_span.error = 1
                    
                    fallback_error_tags = fallback_tags + ['status:failure']
                    statsd.increment('auth.fallback.errors', tags=fallback_error_tags)
                    
                    return False, "all_methods_failed"
    
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
        web_tags = [
            f'endpoint:{endpoint}', 
            f'method:{method}', 
            'service:webapp',
            f'user_id:{user_id}'
        ]
        
        statsd.increment('web.requests.total', tags=web_tags)
        
        with tracer.trace("web.request", service="webapp") as root_span:
            root_span.set_tag("user.id", user_id)
            root_span.set_tag("request.id", request_id)
            root_span.set_tag(http.METHOD, method)
            root_span.set_tag(http.URL, f"https://webapp.example.com{endpoint}")
            root_span.set_tag("span.kind", "server")
            
            try:
                # Simulate authentication with SAML/email flow
                auth_success, auth_method = self.simulate_authentication_flow(user_id, endpoint)
                
                if not auth_success:
                    # Authentication failed completely
                    root_span.set_tag(http.STATUS_CODE, 401)
                    root_span.set_tag("auth.result", "failure")
                    root_span.set_tag("auth.method", "none")
                    
                    # Metrics: Record auth failure
                    duration_actual = (time.time() - timer_start) * 1000
                    auth_error_tags = web_tags + ['status_code:401', 'error_type:auth_failure']
                    statsd.histogram('web.requests.duration', duration_actual, tags=auth_error_tags)
                    statsd.increment('web.requests.errors', tags=auth_error_tags)
                    
                    return 401
                else:
                    # Authentication succeeded
                    root_span.set_tag("auth.result", "success")
                    root_span.set_tag("auth.final_method", auth_method)
                
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
                                self.simulate_database_operation(operation, table, user_id)
                                
                            elif dependency == "cache":
                                cache_key = f"{endpoint}:{user_id}"
                                self.simulate_cache_operation("get", cache_key)
                                
                            elif dependency.endswith("-service"):
                                status = self.simulate_http_request(dependency, "/health", "GET", user_id)
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
                            dep_error_tags = web_tags + ['status_code:500', 'error_type:dependency_failure']
                            statsd.histogram('web.requests.duration', duration_actual, tags=dep_error_tags)
                            statsd.increment('web.requests.errors', tags=dep_error_tags)
                            
                            return 500
                
                # Success
                status_code = 200 if method == "GET" else 201
                root_span.set_tag(http.STATUS_CODE, status_code)
                
                # Metrics: Record successful request
                duration_actual = (time.time() - timer_start) * 1000
                success_tags = web_tags + [f'status_code:{status_code}']
                statsd.histogram('web.requests.duration', duration_actual, tags=success_tags)
                statsd.increment('web.requests.success', tags=success_tags)
                
                return status_code
                
            except Exception as e:
                root_span.set_tag("error.msg", str(e))
                root_span.set_tag("error.type", type(e).__name__)
                root_span.error = 1
                root_span.set_tag(http.STATUS_CODE, 500)
                
                # Metrics: Record error request
                duration_actual = (time.time() - timer_start) * 1000
                internal_error_tags = web_tags + ['status_code:500', 'error_type:internal_error']
                statsd.histogram('web.requests.duration', duration_actual, tags=internal_error_tags)
                statsd.increment('web.requests.errors', tags=internal_error_tags)
                
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