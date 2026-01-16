import json
from utils.paths import Paths

class Load_config:
    def __init__(self):
        path = Paths()
        self._path = path.config_path
        self._load()

    def _load(self):
        with open(self._path, 'r') as f:
            self._data = json.load(f)

    def __getattr__(self, attr):
        if attr in self._data:
            return self._data[attr]
        else:
            raise AttributeError
