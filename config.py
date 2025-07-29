import yaml

class Config():

    def __init__(self, path='config.yaml'):
        self.path = path
        self.config = {}
        self.load_config()

    def load_config(self):
        with open(self.path, 'r') as file:
            self.config = yaml.safe_load(file)

    def save_config(self):
        with open(self.path, 'w') as file:
            yaml.safe_dump(self.config, file)
    
    def get_config(self):
        return self.config
    
config = Config()


