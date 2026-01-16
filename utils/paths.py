from pathlib import Path as PipiPupu

class Paths:
    def __init__(self):
        self.root_path = PipiPupu(__file__).parents[1]
        self.data_path = self.root_path / 'bot-data'
        self.db_path = self.data_path / 'main.db'
        self.config_path = self.data_path / 'config.json'
        self.users_path = self.data_path / 'users.json'
        self.patterns_path = self.data_path / 'patterns.json'
        self.messages_path = self.data_path / 'messages.json'
