import json
import re

from bin.handlers.logger import logger
import utils.paths as paths
from functools import lru_cache

path = paths.Paths()
supported_languages = ['uk', 'en']

class Instruction:
    @staticmethod
    @lru_cache(maxsize=1)
    def _load_patterns():
        with open(path.patterns_path, 'r', encoding='UTF-8') as f:
            patterns_map = json.load(f)

        compiled_patterns = []
        for pattern, instruction_filename in patterns_map.items():
            try:
                regex = re.compile(pattern, re.IGNORECASE)
                compiled_patterns.append((regex, instruction_filename))

            except re.error:
                pass

        return compiled_patterns

    @classmethod
    def _search_patterns(cls, user_input : str):
        logger.info(f'performing pattern search with input: {user_input}')
        for pattern, func_name in cls._load_patterns():
            if re.search(pattern, user_input):
                return func_name

        return "handle_undefined"
    @classmethod
    def load(cls, user_input : str, lang: str = 'uk'):
        file_name = cls._search_patterns(user_input)
        lang = lang if lang in supported_languages else 'uk'
        file_path = path.data_path / 'instructions' / lang / f"{file_name}.md"
        with open(file_path, 'r', encoding='UTF-8') as f:
            logger.info(f"instruction file path: <{file_path}>")
            instruction = f.read()

        return instruction
