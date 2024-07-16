from enum import Enum

class _NAMESPACE:
    id : str | None = None
    def __str__(self) -> str:
        if self.id is None:
            raise ValueError("Namespace not set")
        return self.id
    def set(self, id: str):
        self.id = id
NAMESPACE = _NAMESPACE()

class _AUTHOR:
    name : str | None = None
    def __str__(self) -> str:
        if self.name is None:
            raise ValueError("Author not set")
        return self.name
    def set(self, name: str):
        self.name = name
AUTHOR = _AUTHOR()




class Lang(Enum):
    en_us = "en_us"
    fr_fr = "fr_fr"

    @property
    def namespaced(self):
        return f"{NAMESPACE}:{self.value}"


class Rarity(Enum):
    common = "white"
    uncommon = "yellow"
    rare = "aqua"
    epic = "magenta"


TranslatedString = tuple[str, dict[Lang, str]]

TextComponent_base = str | dict
TextComponent = TextComponent_base | list[TextComponent_base]
