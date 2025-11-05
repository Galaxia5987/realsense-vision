import app
import logging_config

# Setup structured logging
logger = logging_config.get_logger('main')

try:
    logger.info("Starting RealSense Vision system", operation="startup")
    app.run()    
except KeyboardInterrupt:
    logger.info("Application stopped by user (KeyboardInterrupt)", operation="shutdown")
    app.stop()
except Exception as e:
    logger.exception(f"An unhandled error occurred: {e}", operation="error_handler")
    app.stop()
finally:
    logger.info("RealSense Vision system shutdown complete", operation="shutdown")
    
    