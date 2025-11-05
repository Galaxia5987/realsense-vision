# Fault Tolerance and Logging Enhancements

## Overview

This update adds comprehensive fault-tolerance mechanisms, structured logging, and automated recovery capabilities to the RealSense Vision system. The goal is to maximize stability, self-healing capabilities, and observability of all system states.

## Key Components

### 1. Structured Logging (`logging_config.py`)

- **ComponentLogger**: Context-aware logger that adds component metadata to all log messages
- **StructuredFormatter**: Formats logs with timestamps, levels, components, operations, and status
- Supports both human-readable and JSON output formats
- File and console logging support

**Usage:**
```python
from logging_config import get_logger

logger = get_logger('my_component')
logger.info("Component started", operation="startup", status="success")
logger.error("Failed to connect", operation="connect", status="error")
```

### 2. Retry Utilities (`retry_utils.py`)

- **retry_with_backoff**: Decorator for automatic retry with exponential backoff
- **safe_init**: Safe component initialization with retry logic and fallback values
- **safe_call**: Safely call functions with automatic error handling

**Usage:**
```python
from retry_utils import retry_with_backoff, safe_init

@retry_with_backoff(max_attempts=5, initial_delay=1.0)
def connect_to_camera():
    # Connection logic that may fail
    pass

camera, error = safe_init(
    "camera",
    RealSenseCamera,
    max_attempts=3,
    width=640,
    height=480
)
```

### 3. Component Supervisor (`supervisor.py`)

- **ComponentSupervisor**: Watchdog that continuously monitors component health
- Automatic recovery attempts when components fail
- Health check scheduling with configurable intervals
- System-wide health status reporting

**Features:**
- Monitors registered components continuously
- Detects failures after consecutive health check failures
- Attempts automatic recovery using registered recovery handlers
- Tracks failure counts and recovery attempts
- Provides system health summaries via `/health` endpoint

**Usage:**
```python
from supervisor import supervisor

# Register a component for monitoring
supervisor.register_component(
    "camera",
    health_check=lambda: camera.is_healthy(),
    recovery_handler=lambda: recover_camera()
)

# Start monitoring
supervisor.start()

# Get health status
health = supervisor.get_system_health_summary()
```

## Updated Components

### Camera Module (`camera.py`)

**Enhancements:**
- Structured logging for all operations (init, start, stop, frame acquisition)
- Retry logic for pipeline initialization
- Graceful error handling in frame update loop
- Health check method (`is_healthy()`)
- Detailed error tracking (frame counts, error counts)
- Automatic recovery from transient errors

### Network Tables (`network_tables.py`)

**Enhancements:**
- Structured logging for connection and publishing
- Retry logic for connection establishment
- Error handling for individual detection publishing
- Publish count tracking
- Health check method

### Pipeline Runner (`detection/pipeline_runner.py`)

**Enhancements:**
- Structured logging for pipeline lifecycle
- Error recovery in processing loop
- Graceful shutdown handling
- Loop iteration and error tracking
- Health check method

### Configuration (`config.py`)

**Enhancements:**
- Retry logic for config file loading
- Detailed error logging for YAML parsing
- Graceful fallback to empty config on failure

### Application (`app.py`)

**Enhancements:**
- Integration with component supervisor
- Safe initialization of all components
- Recovery handlers for each component
- Detailed startup and shutdown logging
- Error collection and reporting

### Routes (`server/routes.py`)

**New Features:**
- `/health` endpoint for system status monitoring
- Returns JSON with component health information
- Useful for external monitoring systems

## Health Monitoring

### Health Endpoint

Access `http://<host>:5000/health` to get system status:

```json
{
  "status": "healthy",
  "total_components": 3,
  "healthy": 3,
  "degraded": 0,
  "failed": 0,
  "components": {
    "camera": {
      "status": "healthy",
      "consecutive_failures": 0,
      "total_failures": 0,
      "recovery_attempts": 0,
      "last_error": null
    },
    "network_tables": {
      "status": "healthy",
      "consecutive_failures": 0,
      "total_failures": 0,
      "recovery_attempts": 0,
      "last_error": null
    },
    "pipeline_runner": {
      "status": "healthy",
      "consecutive_failures": 0,
      "total_failures": 0,
      "recovery_attempts": 0,
      "last_error": null
    }
  }
}
```

### Component Status Values

- `healthy`: Component is operating normally
- `degraded`: Component is experiencing issues but still functional
- `failed`: Component has failed and cannot recover
- `recovering`: Component is attempting recovery
- `unknown`: Component status is unknown
- `initializing`: Component is initializing

## Configuration

### Supervisor Settings

The supervisor can be configured in code:

```python
supervisor = ComponentSupervisor(
    check_interval=5.0,  # Seconds between health checks
    max_recovery_attempts=3  # Max recovery attempts before giving up
)
```

### Retry Settings

Retry behavior can be customized:

```python
@retry_with_backoff(
    max_attempts=5,
    initial_delay=1.0,
    backoff_factor=2.0,
    max_delay=60.0,
    exceptions=(ConnectionError, TimeoutError)
)
def my_function():
    pass
```

## Logging Output

Logs now include structured metadata:

```
[2025-11-05T08:42:29.430934] INFO     [camera] RealSense camera started successfully (component=camera) (operation=start)
[2025-11-05T08:42:30.123456] WARNING  [camera] Error in camera update loop (consecutive: 1): Timeout (component=camera) (operation=update_loop)
[2025-11-05T08:42:35.789012] INFO     [supervisor] Successfully recovered camera (component=supervisor) (operation=recovery)
```

## Benefits

1. **Automatic Recovery**: System automatically detects and recovers from component failures
2. **Clear Observability**: Detailed, structured logging shows exactly what's happening
3. **Graceful Degradation**: Components that fail don't crash the entire system
4. **Easy Debugging**: Rich context in logs makes troubleshooting easier
5. **Health Monitoring**: External systems can monitor application health via `/health` endpoint
6. **Retry Logic**: Transient failures are automatically retried with backoff
7. **Resource Cleanup**: Components are properly stopped and cleaned up

## Testing

A comprehensive test suite is included to verify all fault-tolerance mechanisms:

```bash
python3 /tmp/test_fault_tolerance.py
```

This tests:
- Structured logging
- Retry mechanisms with exponential backoff
- Safe initialization with fallbacks
- Safe function calls with error handling
- Component supervisor with health checks and recovery

## Future Enhancements

Potential improvements for the future:

1. Metrics collection and export (Prometheus, etc.)
2. Alerting system for critical failures
3. Configurable recovery strategies per component
4. Circuit breaker pattern for external dependencies
5. Performance monitoring and profiling
6. Log aggregation and analysis
