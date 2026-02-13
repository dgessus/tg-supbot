class Events:
    _instance = None
    def __new__(cls):
        if not cls._instance:
            instance = super().__new__(cls)

        return cls._instance

    def __init__(self):
        
