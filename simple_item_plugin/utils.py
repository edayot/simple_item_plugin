import random
from beet import Context, Language, Generator
from pydantic._internal._generics import PydanticGenericMetadata
from simple_item_plugin.types import Lang, TranslatedString, NAMESPACE
from typing import Union, Optional, Self, Iterable, Protocol, Any, runtime_checkable
from pydantic import BaseModel
from nbtlib import Compound


def generate_uuid() -> list[int]:
    return [
        random.randint(0, 0xFFFFFFFF),
        random.randint(0, 0xFFFFFFFF),
        random.randint(0, 0xFFFFFFFF),
        random.randint(0, 0xFFFFFFFF),
    ]


def export_translated_string(ctx: Union[Context, Generator], translation: TranslatedString):
    # create default languages files if they don't exist
    for lang in Lang:
        if lang.namespaced not in ctx.assets.languages:
            ctx.assets.languages[lang.namespaced] = Language({})

    for lang, translate in translation[1].items():
        ctx.assets.languages[f"{NAMESPACE}:{lang.value}"].data[
            translation[0]
        ] = translate


class SimpleItemPluginOptions(BaseModel):
    custom_model_data: int
    generate_guide: bool = True
    disable_guide_cache: bool = False
    add_give_all_function: bool = True
    render_path_for_pack_png: Optional[str] = None
    license_path: Optional[str] = None
    readme_path: Optional[str] = None
    items_on_first_page: bool = False





class Registry(BaseModel):
    class Config: 
        arbitrary_types_allowed = True
        protected_namespaces = ()
    id: str
    __soft_new__ = False
    def export(self, ctx: Union[Context, Generator]) -> Self:
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        real_ctx.meta.setdefault("registry", {}).setdefault(self.__class__.__name__, {})
        if self.__soft_new__ and self.id in real_ctx.meta["registry"][self.__class__.__name__]:
            return real_ctx.meta["registry"][self.__class__.__name__][self.id]
        assert self.id not in real_ctx.meta["registry"][self.__class__.__name__], f"Registry {self.id} already exists"
        real_ctx.meta["registry"][self.__class__.__name__][self.id] = self
        return self
    
    @classmethod
    def get(cls, ctx: Union[Context, Generator], id: str) -> Self:
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        real_ctx.meta.setdefault("registry", {}).setdefault(cls.__name__, {})
        return real_ctx.meta["registry"][cls.__name__][id]
    
    @classmethod
    def iter_items(cls, ctx: Union[Context, Generator]) -> Iterable[tuple[str, Self]]:
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        real_ctx.meta.setdefault("registry", {}).setdefault(cls.__name__, {})
        return real_ctx.meta["registry"][cls.__name__].items()
    
    @classmethod
    def iter_values(cls, ctx: Union[Context, Generator]) -> Iterable[Self]:
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        real_ctx.meta.setdefault("registry", {}).setdefault(cls.__name__, {})
        return real_ctx.meta["registry"][cls.__name__].values()
    
    @classmethod
    def iter_keys(cls, ctx: Union[Context, Generator]) -> Iterable[str]:
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        real_ctx.meta.setdefault("registry", {}).setdefault(cls.__name__, {})
        return real_ctx.meta["registry"][cls.__name__].keys()
        


@runtime_checkable
class ItemProtocol(Protocol):
    id: str
    page_index: Optional[int] = None
    char_index: Optional[int] = None

    @property
    def guide_description(self) -> Optional[TranslatedString]: ...

    @property
    def minimal_representation(self) -> dict[str, Any]: raise NotImplementedError()

    @property
    def model_path(self) -> str: raise NotImplementedError()

    def to_nbt(self, i: int) -> Compound: raise NotImplementedError()

    def result_command(self, count: int, type : str = "block", slot : int = 16) -> str: raise NotImplementedError()

        
