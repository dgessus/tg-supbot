import json
from functools import lru_cache
from utils.paths import Paths


path = Paths()


class Auth:
    def __init__(self, userid, contact: str):
        self.userid = userid
        self.contact = contact
        self._load_users()

    @staticmethod
    @lru_cache(maxsize=1)
    def _load_users():
        with open(path.users_path, mode='r', encoding='utf-8') as f:
            data = json.load(f)
            return data

    def check(self):
        users = self._load_users()['users']
        admins = self._load_users()['admins']
        if self.contact in users:
            return {'role': 'user', 'shop_name': users[self.contact]}
        elif self.contact in admins:
            return {'role': 'admin', 'shop_name': admins[self.contact]}
        else:
            return False
