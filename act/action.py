from dataclasses import dataclass
from typing import Union


@dataclass
class Action:
    name: str
    value: Union[str, float]
    message: str
    source: str = "Unknown"
