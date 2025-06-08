import random
from beet import Context, Language, Generator
from simple_item_plugin.types import Lang, TranslatedString, NAMESPACE
from typing import Union, Optional, Self, Iterable, Protocol, Any, runtime_checkable
from pydantic import BaseModel
from nbtlib import Compound
from model_resolver import Item as ModelResolverItem
import logging

logger = logging.getLogger("simple_item_plugin")


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
    generate_guide: bool = True
    disable_guide_cache: bool = False
    add_give_all_function: bool = True
    item_for_pack_png: Optional[str] = None
    license_path: Optional[str] = None
    readme_path: Optional[str] = None
    items_on_first_page: bool = False
    creator: Optional[str] = None
    prefix_namespace_with_creator: bool = False
    tick_function: str = f"impl/tick"
    load_function: str = f"impl/load"


def real_ctx(ctx: Union[Context, Generator]) -> Context:
    if isinstance(ctx, Generator):
        return ctx.ctx
    return ctx


_DEFAULT = object()

class Registry(BaseModel):
    class Config: 
        arbitrary_types_allowed = True
        protected_namespaces = ()
    id: str
    __soft_new__ = False

    @classmethod
    def _registry_bases_class(cls) -> set[type]:
        res = []
        res.append(cls)
        for base in cls.__mro__:
            res.append(base)
            if base is Registry:
                break
        return set(res)
    
    @classmethod
    def _registry_base_class(cls) -> type:
        for base in cls.__mro__:
            if Registry in base.__bases__:
                return base
        raise TypeError(f"{cls} is not a subclass of {Registry}")

    def export(self, ctx: Union[Context, Generator]) -> Self:
        ctx = real_ctx(ctx)
        bases_cls = self._registry_bases_class()
        for base_cls in bases_cls:
            ctx.meta.setdefault("registry", {}).setdefault(id(base_cls), {})
            if self.__soft_new__ and self.id in ctx.meta["registry"][id(base_cls)]:
                return ctx.meta["registry"][id(base_cls)][self.id]
            assert self.id not in ctx.meta["registry"][id(base_cls)], f"Registry {self.id} already exists"
            ctx.meta["registry"][id(base_cls)][self.id] = self
        return self
    
    @classmethod
    def get(cls, ctx: Union[Context, Generator], id_: str, *, default: object = _DEFAULT) -> Self:
        ctx = real_ctx(ctx)
        base_cls = cls._registry_base_class()
        ctx.meta.setdefault("registry", {}).setdefault(id(base_cls), {})
        if default is _DEFAULT:
            return ctx.meta["registry"][id(base_cls)][id_]
        return ctx.meta["registry"][id(base_cls)].get(id_, default)
    
    @classmethod
    def iter_items(cls, ctx: Union[Context, Generator]) -> Iterable[tuple[str, Self]]:
        ctx = real_ctx(ctx)
        ctx.meta.setdefault("registry", {}).setdefault(id(cls._registry_base_class()), {})
        return ctx.meta["registry"][id(cls._registry_base_class())].items()
    
    @classmethod
    def iter_values(cls, ctx: Union[Context, Generator]) -> Iterable[Self]:
        return list(v for _, v in cls.iter_items(ctx))
    
    @classmethod
    def iter_keys(cls, ctx: Union[Context, Generator]) -> Iterable[str]:
        return list(k for k, _ in cls.iter_items(ctx))
        
@runtime_checkable
class ItemProtocol(Protocol):
    id: str
    page_index: Optional[int] = None
    char_index: Optional[int] = None
    
    additional_pages: Optional[list[Any]] = None

    @property
    def guide_description(self) -> Optional[TranslatedString]: ...

    @property
    def minimal_representation(self) -> dict[str, Any]: raise NotImplementedError()


    def to_nbt(self, ctx: Context, i: int) -> Compound: raise NotImplementedError()

    def result_command(self, count: int, type : str = "block", slot : int = 16) -> str: raise NotImplementedError()

    def to_model_resolver(self, ctx: Context) -> ModelResolverItem: raise NotImplementedError

        
