from typing import TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from .models import ModelMeta


@dataclass()
class ModelManager:
    supports_file: bool = False
    supports_streaming: bool = True

    def __init__(self, model: "ModelMeta"):
        self.model = model

    def prepare_file(self, media_type: str, data):
        return None
