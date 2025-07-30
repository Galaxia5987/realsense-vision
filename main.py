import app
import logging

try:
    app.run()    
except KeyboardInterrupt:
    app.stop()
    logging.info("Application stopped by user.")
except Exception as e:
    logging.error(f"An unhandled error occurred: {e}")
    
    