#!/usr/bin/env python3
"""
OTEL Telemetry Generator for Firetiger - Productivity Tool Simulation

This script generates and sends telemetry logs to a Firetiger OTEL endpoint.
It simulates a productivity tool with multiple customers and dependencies,
with configurable failure patterns based on time and customer ID.
"""

import os
import time
import random
import logging
import threading
import uuid
import requests
import argparse
import hashlib
from datetime import datetime
from dotenv import load_dotenv
import base64

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("firetiger-telemetry")

class ProductivityToolSimulator:
    """Simulate a productivity tool generating telemetry logs with customer-specific patterns"""
    
    # Define endpoints that the productivity tool supports
    ENDPOINTS = [
        "/api/v1/documents",
        "/api/v1/workspaces",
        "/api/v1/users",
        "/api/v1/teams",
        "/api/v1/projects",
        "/api/v1/tasks",
        "/api/v1/comments",
        "/api/v1/notifications",
        "/api/v1/search",
        "/api/v1/analytics"
    ]
    
    # Define HTTP methods
    HTTP_METHODS = ["GET", "POST", "PUT", "DELETE"]
    
    # Define common HTTP status codes
    SUCCESS_CODES = [200, 201, 204]
    CLIENT_ERROR_CODES = [400, 401, 403, 404, 429]
    SERVER_ERROR_CODES = [500, 502, 503, 504]
    
    def __init__(self):
        """Initialize the simulator with configuration from environment variables"""
        # Load environment variables from .env file
        load_dotenv()
        
        # Get environment variables
        self.project = os.getenv("FT_PROJECT", "firetiger-demo")
        self.bucket = os.getenv("FT_BUCKET", "firetiger-demo")
        self.auth_password = os.getenv("FT_BASIC_AUTH_PASSWORD")
        self.auth_header = os.getenv("FT_DEMO_BASIC_AUTH_HEADER")
        
        # If FT_DEMO_BASIC_AUTH_HEADER is not provided, generate it
        if self.auth_header == "placeholder" and self.auth_password != "placeholder":
            auth_string = f"{self.bucket}:{self.auth_password}"
            self.auth_header = base64.b64encode(auth_string.encode()).decode()
        
        # Configure the HTTP endpoint
        self.endpoint = f"https://ingest.{self.bucket}.firetigerapi.com/v1/logs"
        self.headers = {
            "Authorization": f"Basic {self.auth_header}",
            "Content-Type": "application/json"
        }
        
        # Default configuration
        self.customer_ids = []
        self.num_customers = 10
        self.db_failure_rate = 0.05  # 5% chance of database failure
        self.payment_failure_rate = 0.03  # 3% chance of payment system failure
        self.tls_failure_rate = 0.02  # 2% chance of TLS/network issues
        
        # Log configuration (redact sensitive info)
        logger.info(f"Configured for project: {self.project}")
        logger.info(f"Using endpoint: {self.endpoint}")
        
    def configure_simulation(self, num_customers, db_failure_rate, payment_failure_rate, tls_failure_rate):
        """Configure the simulation parameters"""
        self.num_customers = num_customers
        self.db_failure_rate = db_failure_rate
        self.payment_failure_rate = payment_failure_rate
        self.tls_failure_rate = tls_failure_rate
        
        # Generate customer IDs
        self.customer_ids = [f"cust_{i:04d}" for i in range(1, num_customers + 1)]
        
        logger.info(f"Configured simulation with {num_customers} customers")
        logger.info(f"Failure rates - DB: {db_failure_rate*100}%, Payments: {payment_failure_rate*100}%, TLS: {tls_failure_rate*100}%")
    
    def should_component_fail(self, component, customer_id, timestamp):
        """
        Determine if a specific component should fail based on customer ID and time
        
        Args:
            component (str): Component name ('db', 'payment', 'tls')
            customer_id (str): Customer ID
            timestamp (float): Current timestamp
            
        Returns:
            bool: True if the component should fail, False otherwise
        """
        # Create a deterministic but seemingly random pattern based on customer_id and time
        hour_of_day = datetime.fromtimestamp(timestamp).hour
        minute_of_hour = datetime.fromtimestamp(timestamp).minute
        
        # Use a hash of the customer ID and current hour to create deterministic failures
        hash_input = f"{customer_id}:{hour_of_day}:{component}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16) % 1000 / 1000.0
        
        # Special cases: certain customers have higher failure rates at specific times
        if component == 'db':
            # Customers with IDs ending in '1' experience DB issues during 9-10 AM
            if customer_id.endswith('1') and hour_of_day == 9:
                return hash_value < 0.5  # 50% chance of failure
            return hash_value < self.db_failure_rate
        
        elif component == 'payment':
            # Customers with IDs ending in '5' experience payment issues during 2-3 PM
            if customer_id.endswith('5') and hour_of_day == 14:
                return hash_value < 0.4  # 40% chance of failure
            return hash_value < self.payment_failure_rate
        
        elif component == 'tls':
            # All customers experience elevated TLS issues at the top of each hour
            if minute_of_hour < 5:
                return hash_value < (self.tls_failure_rate * 3)  # 3x normal failure rate
            return hash_value < self.tls_failure_rate
        
        return False
    
    def generate_request_log(self, customer_id, timestamp):
        """
        Generate a log record simulating an HTTP request to the productivity tool
        
        Args:
            customer_id (str): Customer ID
            timestamp (float): Timestamp for the log
            
        Returns:
            tuple: (log_record, severity, status_code, endpoint, http_method)
        """
        trace_id = uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]
        request_id = uuid.uuid4().hex[:8]
        
        # Select random endpoint and HTTP method
        endpoint = random.choice(self.ENDPOINTS)
        http_method = random.choice(self.HTTP_METHODS)
        
        # Determine if any component fails
        db_fails = self.should_component_fail('db', customer_id, timestamp)
        payment_fails = self.should_component_fail('payment', customer_id, timestamp)
        tls_fails = self.should_component_fail('tls', customer_id, timestamp)
        
        # Determine response code and message based on failures
        if tls_fails:
            status_code = random.choice([502, 503, 504])
            message = f"TLS handshake failed for customer {customer_id} on request {request_id}"
            severity = "ERROR"
        elif db_fails:
            if random.random() < 0.7:  # 70% of DB failures are server errors
                status_code = 500
                message = f"Database connection timeout for customer {customer_id} on request {request_id}"
            else:
                status_code = 404
                message = f"Resource not found in database for customer {customer_id} on request {request_id}"
            severity = "ERROR"
        elif payment_fails and endpoint == "/api/v1/projects" and http_method in ["POST", "PUT"]:
            status_code = random.choice([400, 402])
            message = f"Payment processing failed for customer {customer_id} on request {request_id}"
            severity = "ERROR"
        else:
            # No failures - successful request
            status_code = random.choice(self.SUCCESS_CODES)
            message = f"Successfully processed {http_method} request to {endpoint} for customer {customer_id}"
            severity = "INFO"
        
        # Calculate random but realistic response time
        # Base response time depends on endpoint complexity
        base_response_time = {
            "/api/v1/search": random.uniform(200, 800),
            "/api/v1/analytics": random.uniform(300, 900),
            "/api/v1/documents": random.uniform(100, 400),
        }.get(endpoint, random.uniform(50, 200))
        
        # Add delay for failures
        if status_code >= 500:
            response_time = base_response_time * random.uniform(3, 10)  # Much slower for server errors
        elif status_code >= 400:
            response_time = base_response_time * random.uniform(1, 2.5)  # Slightly slower for client errors
        else:
            response_time = base_response_time
        
        # Create attributes for the log
        attributes = {
            "customer.id": customer_id,
            "http.method": http_method,
            "http.url": f"https://productivity-tool.example.com{endpoint}",
            "http.status_code": str(status_code),
            "http.response_time_ms": str(int(response_time)),
            "service.name": "productivity-service",
            "request.id": request_id,
            "trace.id": trace_id,
            "span.id": span_id,
            "timestamp": str(timestamp)
        }
        
        # Add component-specific attributes based on failures
        if db_fails:
            attributes["component.failed"] = "database"
            attributes["database.error"] = "connection_timeout" if status_code == 500 else "record_not_found"
            attributes["database.host"] = f"db-{random.randint(1,5)}.internal"
        elif payment_fails and status_code in [400, 402]:
            attributes["component.failed"] = "payment_processor"
            attributes["payment.error"] = "insufficient_funds" if status_code == 402 else "invalid_payment_details"
            attributes["payment.provider"] = "stripe"
            attributes["payment.transaction_id"] = f"tx_{uuid.uuid4().hex[:10]}"
        elif tls_fails:
            attributes["component.failed"] = "tls"
            attributes["network.error"] = "handshake_failure"
            attributes["tls.version"] = "1.3"
            attributes["network.client_ip"] = f"192.168.{random.randint(0,255)}.{random.randint(0,255)}"
        
        # Map severity to OTLP severity number
        severity_map = {
            "TRACE": 1,
            "DEBUG": 5,
            "INFO": 9,
            "WARN": 13,
            "ERROR": 17,
            "FATAL": 21
        }
        severity_num = severity_map.get(severity, 9)
        
        # Create the log record according to OTLP format
        log_record = {
            "timeUnixNano": int(timestamp * 1e9),
            "severityNumber": severity_num,
            "severityText": severity,
            "body": {
                "stringValue": message
            },
            "attributes": [
                {"key": k, "value": {"stringValue": str(v)}} for k, v in attributes.items()
            ],
            "droppedAttributesCount": 0,
            "traceId": trace_id,
            "spanId": span_id
        }
        
        return (log_record, severity, status_code, endpoint, http_method)
    
    def send_logs(self, log_records):
        """
        Send a batch of logs to the OTLP endpoint
        
        Args:
            log_records (list): List of log records to send
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create the OTLP payload structure according to the spec
            payload = {
                "resourceLogs": [
                    {
                        "resource": {
                            "attributes": [
                                {"key": "service.name", "value": {"stringValue": "productivity-tool"}},
                                {"key": "service.version", "value": {"stringValue": "2.0.0"}},
                                {"key": "deployment.environment", "value": {"stringValue": "demo"}}
                            ]
                        },
                        "scopeLogs": [
                            {
                                "scope": {
                                    "name": "http-request-logger"
                                },
                                "logRecords": log_records
                            }
                        ]
                    }
                ]
            }
            
            # Send the request
            response = requests.post(self.endpoint, headers=self.headers, json=payload)
            
            # Check if the request was successful
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Failed to send logs: {response.status_code}, {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Exception when sending logs: {str(e)}")
            return False
    
    def generate_logs_worker(self, worker_id, num_logs, interval, batch_size=10):
        """
        Worker function to generate and send logs
        
        Args:
            worker_id (int): Identifier for this worker
            num_logs (int): Number of logs to generate
            interval (float): Interval between logs in seconds
            batch_size (int): Number of logs to batch together
        """
        log_records = []
        successful_logs = 0
        error_logs = 0
        client_error_logs = 0
        server_error_logs = 0
        
        for i in range(num_logs):
            # Generate timestamp with slight randomization to simulate real-world variation
            timestamp = time.time() - random.uniform(0, 10)
            
            # Select a random customer ID
            customer_id = random.choice(self.customer_ids)
            
            # Generate a log record
            log_record, severity, status_code, endpoint, http_method = self.generate_request_log(customer_id, timestamp)
            log_records.append(log_record)
            
            # Track error counts for reporting
            if status_code >= 500:
                server_error_logs += 1
                error_logs += 1
            elif status_code >= 400:
                client_error_logs += 1
                error_logs += 1
            
            # Send logs in batches to reduce HTTP overhead
            if len(log_records) >= batch_size:
                success = self.send_logs(log_records)
                if success:
                    successful_logs += len(log_records)
                log_records = []
            
            # Add a small delay to simulate work
            time.sleep(interval)
        
        # Send any remaining logs
        if log_records:
            success = self.send_logs(log_records)
            if success:
                successful_logs += len(log_records)
        
        logger.info(f"Worker {worker_id} completed: {successful_logs}/{num_logs} logs sent successfully")
        logger.info(f"Worker {worker_id} errors: {error_logs} total ({client_error_logs} client, {server_error_logs} server)")
    
    def generate_logs(self, num_logs=100, num_workers=10, interval_ms=10, batch_size=10, 
                      num_customers=None, db_failure_rate=None, payment_failure_rate=None, tls_failure_rate=None):
        """
        Generate and send logs using multiple worker threads
        
        Args:
            num_logs (int): Number of logs per worker
            num_workers (int): Number of worker threads
            interval_ms (int): Interval between logs in milliseconds
            batch_size (int): Number of logs to batch together
            num_customers (int): Number of customer IDs to simulate
            db_failure_rate (float): Rate of database failures
            payment_failure_rate (float): Rate of payment system failures
            tls_failure_rate (float): Rate of TLS/network failures
        """
        # Apply configuration if provided
        if num_customers is not None:
            self.configure_simulation(
                num_customers,
                db_failure_rate or self.db_failure_rate,
                payment_failure_rate or self.payment_failure_rate,
                tls_failure_rate or self.tls_failure_rate
            )
        
        interval_seconds = interval_ms / 1000.0
        
        logger.info(f"Starting productivity tool simulation with {num_workers} workers, {num_logs} logs per worker")
        logger.info(f"Interval: {interval_ms}ms, Batch size: {batch_size}")
        logger.info(f"Simulating {len(self.customer_ids)} customers with deterministic failure patterns")
        
        # Create and start worker threads
        threads = []
        for worker_id in range(num_workers):
            thread = threading.Thread(
                target=self.generate_logs_worker,
                args=(worker_id, num_logs, interval_seconds, batch_size)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        logger.info("Telemetry generation completed")

def main():
    """Parse command line arguments and run the telemetry generator"""
    parser = argparse.ArgumentParser(description='Simulate a productivity tool generating telemetry logs')
    parser.add_argument('--logs', type=int, default=100, help='Number of logs to generate per worker')
    parser.add_argument('--workers', type=int, default=10, help='Number of worker threads')
    parser.add_argument('--interval', type=str, default='10ms', help='Interval between logs (e.g., 10ms, 1s)')
    parser.add_argument('--batch-size', type=int, default=10, help='Number of logs to batch together')
    parser.add_argument('--customers', type=int, default=10, help='Number of customers to simulate')
    parser.add_argument('--db-failure-rate', type=float, default=0.05, help='Database failure rate (0.0-1.0)')
    parser.add_argument('--payment-failure-rate', type=float, default=0.03, help='Payment system failure rate (0.0-1.0)')
    parser.add_argument('--tls-failure-rate', type=float, default=0.02, help='TLS/network failure rate (0.0-1.0)')
    
    args = parser.parse_args()
    
    # Parse interval
    if args.interval.endswith('ms'):
        interval_ms = int(args.interval[:-2])
    elif args.interval.endswith('s'):
        interval_ms = int(float(args.interval[:-1]) * 1000)
    else:
        interval_ms = int(args.interval)
    
    # Create and run productivity tool simulator
    simulator = ProductivityToolSimulator()
    simulator.generate_logs(
        num_logs=args.logs,
        num_workers=args.workers,
        interval_ms=interval_ms,
        batch_size=args.batch_size,
        num_customers=args.customers,
        db_failure_rate=args.db_failure_rate,
        payment_failure_rate=args.payment_failure_rate,
        tls_failure_rate=args.tls_failure_rate
    )

if __name__ == "__main__":
    main()