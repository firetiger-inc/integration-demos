#!/bin/bash

# Setup script for Firetiger OpenTelemetry Collector
# This script gets Firetiger connection details and generates the OTel collector config

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --platform PLATFORM    Platform: 'gcp' or 'aws' (required unless using --ingest-secret)"
    echo "  --bucket BUCKET_NAME    Firetiger bucket name (required)"
    echo "  --project PROJECT_ID    GCP project ID (required for GCP)"
    echo "  --account ACCOUNT_ID    AWS account ID (required for AWS)"
    echo "  --region AWS_REGION     AWS region (required for AWS)"
    echo "  --ingest-secret SECRET  Firetiger ingest secret (bypasses Secret Manager lookup)"
    echo "  --help                  Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --platform gcp --bucket my-firetiger-bucket --project my-project-123"
    echo "  $0 --platform aws --bucket my-firetiger-bucket --account 123456789012 --region us-west-2"
    echo "  $0 --bucket my-firetiger-bucket --ingest-secret YOUR_SECRET_HERE"
    exit 1
}

# Parse command line arguments
PLATFORM=""
BUCKET_NAME=""
PROJECT_ID=""
ACCOUNT_ID=""
AWS_REGION=""
INGEST_SECRET=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --platform)
            PLATFORM="$2"
            shift 2
            ;;
        --bucket)
            BUCKET_NAME="$2"
            shift 2
            ;;
        --project)
            PROJECT_ID="$2"
            shift 2
            ;;
        --account)
            ACCOUNT_ID="$2"
            shift 2
            ;;
        --region)
            AWS_REGION="$2"
            shift 2
            ;;
        --ingest-secret)
            INGEST_SECRET="$2"
            shift 2
            ;;
        --help)
            usage
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required arguments
if [[ -z "$INGEST_SECRET" && -z "$PLATFORM" ]]; then
    print_error "Either --platform (with cloud credentials) or --ingest-secret is required"
    usage
fi

if [[ -z "$BUCKET_NAME" ]]; then
    print_error "Bucket name is required. Use --bucket BUCKET_NAME"
    usage
fi

if [[ -z "$INGEST_SECRET" ]]; then
    if [[ "$PLATFORM" == "gcp" && -z "$PROJECT_ID" ]]; then
        print_error "Project ID is required for GCP. Use --project PROJECT_ID"
        usage
    fi

    if [[ "$PLATFORM" == "aws" && (-z "$ACCOUNT_ID" || -z "$AWS_REGION") ]]; then
        print_error "Account ID and region are required for AWS. Use --account ACCOUNT_ID --region AWS_REGION"
        usage
    fi
fi

# Function to get GCP credentials
get_gcp_credentials() {
    print_info "Getting Firetiger credentials from GCP..."
    
    # Check if gcloud is available
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed or not in PATH"
        exit 1
    fi
    
    # Check if authenticated
    print_info "Checking gcloud authentication..."
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | head -n1 | grep -q "@"; then
        print_warning "No active gcloud authentication found"
        print_info "Running: gcloud auth login"
        gcloud auth login
        
        print_info "Also refreshing Application Default Credentials..."
        gcloud auth application-default login
    fi
    
    # Verify project access
    print_info "Verifying access to project '$PROJECT_ID'..."
    if ! gcloud projects describe "$PROJECT_ID" &>/dev/null; then
        print_error "Cannot access project '$PROJECT_ID'"
        print_error "Make sure the project exists and you have access"
        print_error "Try: gcloud config set project $PROJECT_ID"
        exit 1
    fi
    
    # Check if secret exists
    print_info "Checking if secret exists..."
    if ! gcloud --project "$PROJECT_ID" secrets describe "$BUCKET_NAME-basic-auth-ingest" &>/dev/null; then
        print_error "Secret '$BUCKET_NAME-basic-auth-ingest' does not exist in project '$PROJECT_ID'"
        print_info "Available secrets:"
        gcloud --project "$PROJECT_ID" secrets list --format="value(name)" | head -5
        exit 1
    fi
    
    # Get the password from Google Secret Manager
    print_info "Retrieving password from Secret Manager..."
    FIRETIGER_PASSWORD=$(gcloud --project "$PROJECT_ID" secrets versions access latest --secret "$BUCKET_NAME-basic-auth-ingest" 2>/dev/null)
    
    if [[ -z "$FIRETIGER_PASSWORD" ]]; then
        print_error "Failed to retrieve password from Secret Manager"
        print_error "This might be an authentication or permissions issue"
        print_info "Try running manually:"
        print_info "  gcloud --project $PROJECT_ID secrets versions access latest --secret $BUCKET_NAME-basic-auth-ingest"
        exit 1
    fi
    
    print_info "Successfully retrieved credentials from GCP"
}

# Function to get AWS credentials
get_aws_credentials() {
    print_info "Getting Firetiger credentials from AWS..."
    
    # Check if aws CLI is available
    if ! command -v aws &> /dev/null; then
        print_error "aws CLI is not installed or not in PATH"
        exit 1
    fi
    
    # Check if jq is available
    if ! command -v jq &> /dev/null; then
        print_error "jq is not installed or not in PATH (required for parsing AWS responses)"
        exit 1
    fi
    
    print_info "Assuming cross-account role..."
    
    # Get the credentials from assume-role
    CREDS=$(aws sts assume-role \
        --role-arn "arn:aws:iam::${ACCOUNT_ID}:role/CrossAccountAccessForFiretiger" \
        --role-session-name "firetiger-otel-setup" \
        --output json 2>/dev/null)
    
    if [[ -z "$CREDS" ]]; then
        print_error "Failed to assume cross-account role"
        print_error "Make sure you have permissions to assume role: arn:aws:iam::${ACCOUNT_ID}:role/CrossAccountAccessForFiretiger"
        exit 1
    fi
    
    # Extract credentials
    export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | jq -r .Credentials.AccessKeyId)
    export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | jq -r .Credentials.SecretAccessKey)
    export AWS_SESSION_TOKEN=$(echo "$CREDS" | jq -r .Credentials.SessionToken)
    
    if [[ -z "$AWS_ACCESS_KEY_ID" || -z "$AWS_SECRET_ACCESS_KEY" || -z "$AWS_SESSION_TOKEN" ]]; then
        print_error "Failed to obtain valid credentials from assume-role"
        exit 1
    fi
    
    print_info "Successfully assumed cross-account role"
    
    # Get the secret using the temporary credentials
    print_info "Retrieving password from AWS Secrets Manager..."
    FIRETIGER_PASSWORD=$(aws secretsmanager get-secret-value \
        --secret-id "firetiger/ingest/basic-auth@${BUCKET_NAME}" \
        --query SecretString --output text 2>/dev/null)
    
    if [[ -z "$FIRETIGER_PASSWORD" ]]; then
        print_error "Failed to retrieve password from AWS Secrets Manager"
        print_error "Make sure the secret 'firetiger/ingest/basic-auth@${BUCKET_NAME}' exists"
        exit 1
    fi
    
    print_info "Successfully retrieved credentials from AWS"
}

# Get credentials based on platform
if [[ -n "$INGEST_SECRET" ]]; then
    print_info "Using provided ingest secret (bypassing cloud secret manager)"
    FIRETIGER_PASSWORD="$INGEST_SECRET"
elif [[ "$PLATFORM" == "gcp" ]]; then
    get_gcp_credentials
elif [[ "$PLATFORM" == "aws" ]]; then
    get_aws_credentials
else
    print_error "Invalid platform: $PLATFORM. Must be 'gcp' or 'aws'"
    exit 1
fi

# Generate authorization header and endpoint
print_info "Generating connection details..."

AUTHORIZATION=$(echo -n "$BUCKET_NAME:$FIRETIGER_PASSWORD" | base64)
INGEST_ENDPOINT="https://ingest.$(echo $BUCKET_NAME | sed 's/[^a-zA-Z0-9-]/-/g').firetigerapi.com:443"

print_info "Connection details:"
echo "OTEL Endpoint: ${INGEST_ENDPOINT}"
echo "Authorization: Basic ${AUTHORIZATION}"

# Generate OpenTelemetry Collector configuration
print_info "Generating OpenTelemetry Collector configuration..."

cat > ../generated/otel-config.yaml << EOF
receivers:
  # Receive traces from DDTrace on port 8126 (DataDog agent port)
  datadog:
    endpoint: 0.0.0.0:8126
    read_timeout: 60s

processors:
  # Batch traces for efficient export
  batch:
    timeout: 1s
    send_batch_size: 1024
    send_batch_max_size: 2048
  
  # Add resource attributes
  resource:
    attributes:
      - key: deployment.environment
        value: demo
        action: upsert
      - key: service.namespace
        value: ddtrace-demo
        action: upsert

exporters:
  # Export to Firetiger via OTLP HTTP
  otlphttp/firetiger:
    endpoint: ${INGEST_ENDPOINT}
    tls:
      insecure: false
    headers:
      "User-Agent": "opentelemetry-collector-ddtrace-demo"
      "Authorization": "Basic ${AUTHORIZATION}"
    retry_on_failure:
      enabled: true
      initial_interval: 1s
      max_interval: 30s
      max_elapsed_time: 300s
  
  # Debug output to see converted traces
  debug:
    verbosity: detailed

service:
  pipelines:
    traces:
      receivers: [datadog]
      processors: [resource, batch]
      exporters: [otlphttp/firetiger, debug]
    
    metrics:
      receivers: [datadog]
      processors: [resource, batch]
      exporters: [otlphttp/firetiger]

  # Collector telemetry
  telemetry:
    logs:
      level: "info"
EOF

print_info "OpenTelemetry Collector configuration written to: ../generated/otel-config.yaml"

# Generate environment file for DDTrace
print_info "Generating environment configuration for DDTrace..."

cat > ../generated/.env << EOF
# DDTrace configuration - sends traces to localhost:8126 by default
DD_SERVICE=ddtrace-webapp
DD_ENV=demo  
DD_VERSION=1.0.0

# Firetiger connection details (for reference)
FIRETIGER_ENDPOINT=${INGEST_ENDPOINT}
FIRETIGER_AUTH=Basic ${AUTHORIZATION}
EOF

print_info "Environment configuration written to: ../generated/.env"

# Generate startup script
print_info "Generating startup script..."

cat > ../generated/start-demo.sh << 'EOF'
#!/bin/bash

# Start the DDTrace + OpenTelemetry demo

set -e

print_info() {
    echo -e "\033[0;32m[INFO]\033[0m $1"
}

print_error() {
    echo -e "\033[0;31m[ERROR]\033[0m $1"
}

# Check if otel-config.yaml exists
if [[ ! -f "../generated/otel-config.yaml" ]]; then
    print_error "../generated/otel-config.yaml not found. Run ../src/setup-firetiger-otel.sh first."
    exit 1
fi

# Check if OpenTelemetry Collector is available
if ! command -v otelcol-contrib &> /dev/null; then
    print_error "OpenTelemetry Collector (otelcol-contrib) is not installed"
    print_error "Install it from: https://github.com/open-telemetry/opentelemetry-collector-releases/releases"
    exit 1
fi

print_info "Starting OpenTelemetry Collector..."
otelcol-contrib --config=../generated/otel-config.yaml &
OTEL_PID=$!

# Wait for collector to start
sleep 3

print_info "Starting DDTrace application..."
print_info "DDTrace will send traces to localhost:8126 where OTel collector is listening"
ddtrace-run python3 ../src/ddtrace_app.py --requests 50 --workers 3 --interval 200ms --users 20

print_info "Demo completed. Stopping OpenTelemetry Collector..."
kill $OTEL_PID

print_info "Demo finished successfully!"
EOF

chmod +x ../generated/start-demo.sh

print_info "Startup script written to: ../generated/start-demo.sh"

print_info ""
print_info "Setup complete! To run the demo:"
print_info "1. Install OpenTelemetry Collector: https://github.com/open-telemetry/opentelemetry-collector-releases/releases"
print_info "2. Install Python dependencies: pip install -r requirements.txt"
print_info "3. Run the demo: cd ../generated && ./start-demo.sh"
print_info ""
print_info "How it works:"
print_info "- DDTrace app sends traces to localhost:8126 (DataDog agent port)"
print_info "- OpenTelemetry collector DataDog receiver listens on port 8126"
print_info "- Collector converts DD traces to OpenTelemetry format"
print_info "- Collector forwards traces to Firetiger via OTLP"
print_info ""
print_warning "Note: Keep your credentials secure and do not commit .env to version control"