import yaml
import logging_config
from retry_utils import retry_with_backoff

logger = logging_config.get_logger('config')

class Config():

    def __init__(self, path='config.yaml'):
        self.path = path
        self.config = {}
        logger.info(f"Initializing config from {path}", operation="init")
        try:
            self.load_config()
        except Exception as e:
            logger.exception(f"Failed to load initial config: {e}", operation="init")
            # Set default empty config
            self.config = {}

    @retry_with_backoff(max_attempts=3, initial_delay=0.5)
    def load_config(self):
        """Load configuration from YAML file with retry logic."""
        logger.info(f"Loading config from {self.path}", operation="load_config")
        
        try:
            with open(self.path, 'r') as file:
                self.config = yaml.safe_load(file)
                
            if not self.config:
                logger.warning("Loaded config is empty", operation="load_config")
                self.config = {}
            
            logger.info(
                f"Config loaded successfully with {len(self.config)} top-level keys",
                operation="load_config", status="success"
            )
        except FileNotFoundError:
            logger.error(
                f"Config file not found: {self.path}",
                operation="load_config", status="error"
            )
            raise
        except yaml.YAMLError as e:
            logger.exception(
                f"YAML parsing error in config file: {e}",
                operation="load_config"
            )
            raise
        except Exception as e:
            logger.exception(
                f"Unexpected error loading config: {e}",
                operation="load_config"
            )
            raise

    def save_config(self):
        """Save configuration to YAML file."""
        logger.info(f"Saving config to {self.path}", operation="save_config")
        
        try:
            with open(self.path, 'w') as file:
                yaml.safe_dump(self.config, file)
            
            logger.info(
                "Config saved successfully",
                operation="save_config", status="success"
            )
        except Exception as e:
            logger.exception(
                f"Error saving config: {e}",
                operation="save_config"
            )
            raise
    
    def get_config(self):
        """Get the current configuration dictionary."""
        return self.config
    
config = Config()


