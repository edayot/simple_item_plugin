from dataclasses import dataclass, field
import typing
if typing.TYPE_CHECKING:
    from simple_item_plugin.guide import Page
from simple_item_plugin.types import TextComponent, TextComponent_base, NAMESPACE, TranslatedString, Lang
from beet import Context, FunctionTag, Function, ItemModel, LootTable, Model, Texture, ResourcePack, Generator
from PIL import Image
from typing import Any, Optional, TYPE_CHECKING, Union, Self
from typing_extensions import TypedDict, NotRequired, Literal, Optional
from simple_item_plugin.utils import export_translated_string, SimpleItemPluginOptions, Registry, ItemProtocol
from beet.contrib.vanilla import Vanilla
from model_resolver import Item as ModelResolverItem

from nbtlib.tag import Compound, String, Byte
from nbtlib import serialize_tag
import json
from pydantic import BaseModel
import logging
from copy import deepcopy
from enum import Enum

logger = logging.getLogger("simple_item_plugin")

if TYPE_CHECKING:
    from simple_item_plugin.mineral import Mineral
else:
    Mineral = Any


class ItemGroup(Registry):
    id: str
    name: TranslatedString
    item_icon: Optional[ItemProtocol] = None
    items_list: list[ItemProtocol] = field(default_factory=list)
    page_index: Optional[int] = None

    def __hash__(self) -> int:
        return hash(f"{NAMESPACE}:self.id")
    
    def add_item(self, ctx: Context, item: ItemProtocol) -> Self:
        # assert that the item is not already in an item group
        for item_group in ItemGroup.iter_values(ctx):
            if item_group == self:
                continue
            if item in item_group.items_list:
                raise ValueError(f"Item {item.id} is already in an item group")
        for i in self.items_list:
            if i.id == item.id:
                return self
        self.items_list.append(item)
        return self
    
    def export(self, ctx: Context) -> Self:
        export_translated_string(ctx, self.name)
        return super().export(ctx)
        


class WorldGenerationParams(BaseModel):
    min_y: int
    max_y: int
    min_veins: int
    max_veins: int
    min_vein_size: int
    max_vein_size: int
    ignore_restrictions: Literal[0, 1]
    dimension: Optional[str] = None
    biome: Optional[str] = None
    biome_blacklist: Optional[Literal[0, 1]] = None


    def to_human_string(self, lang: Lang):
        dimension = (self.dimension or "minecraft:overworld").split(":")[-1].capitalize()
        biome = (self.biome or "none").split(":")[-1].capitalize()
        tag = ""
        range_num = f"y={self.min_y}..{self.max_y}"
        if self.biome and self.biome.startswith("#"):
            tag = " tag"
        if lang == Lang.en_us:
            range_num = f"in the range {range_num}"
            if self.biome:
                if self.biome_blacklist:
                    return f"in the all biomes except {biome} biome{tag} in the {dimension}, {range_num}"
                return f"in the {biome} biome{tag} in the {dimension}, {range_num}"
            return f"in the {dimension}, {range_num}"
        elif lang == Lang.fr_fr:
            range_num = f"dans la range {range_num}"
            if self.biome:
                if self.biome_blacklist:
                    return f"dans tous les biomes sauf le biome {biome}{tag} dans la dimension {dimension}, {range_num}"
                return f"dans le biome {biome}{tag} dans la dimension {dimension}, {range_num}"
            return f"dans la dimension {dimension}, {range_num}"
        else:
            raise ValueError(f"Invalid lang {lang}")

class BlockProperties(BaseModel):
    base_block: str
    smart_waterlog: Optional[bool] = False
    all_same_faces: Optional[bool] = True
    world_generation: Optional[list[WorldGenerationParams]] = None

    base_item_placed: Optional[str] = None
    item_model_placed: Optional[str] = None

    @property
    def base_block_tag(self):
        return f"{NAMESPACE}.block.{self.base_block.replace("minecraft:", "")}"
    



class Item(Registry):
    id: str
    page_index: Optional[int] = None
    char_index: Optional[int] = None
    # the translation key, the
    item_name: TextComponent_base | TranslatedString
    lore: list[TranslatedString | Any] = field(default_factory=list)

    components_extra: dict[str, Any] = field(default_factory=dict)

    base_item: str = "minecraft:jigsaw"
        
    block_properties: BlockProperties | None = None
    is_cookable: bool = False
    is_armor: bool = False

    mineral: Optional[Mineral] = None

    guide_description: Optional[TranslatedString] = None
    additional_pages: Optional[list[Any]] = field(default_factory=list)

    @property
    def clear_texture_path(self):
        return f"{NAMESPACE}:item/clear"

    @property
    def loot_table_path(self):
        return f"{NAMESPACE}:impl/items/{self.id}"
    
    def namespace_id(self, ctx: Context) -> str:
        opts = ctx.validate("simple_item_plugin", SimpleItemPluginOptions)
        if opts.prefix_namespace_with_creator:
            return f"{opts.creator}:{NAMESPACE}/{self.id}"
        return f"{NAMESPACE}:{self.id}"
    
    @property
    def model_path(self):
        return f"{NAMESPACE}:item/{self.id}"
    
    @property
    def item_model(self):
        return f"{NAMESPACE}:{self.id}"
    
    @property
    def minimal_representation(self) -> dict[str, Any]:
        return {
            "id": self.base_item,
            "components": {
                "minecraft:item_name": self.get_item_name(),
                "minecraft:lore": self.create_lore(),
            }
        }
    
    def to_model_resolver(self, ctx: Context) -> ModelResolverItem: 
        return ModelResolverItem(
            id=self.id,
            count=1,
            components={
                "minecraft:item_model": self.item_model,
                "minecraft:custom_data": self.create_custom_data(ctx),
                **self.components_extra,
            },
        )
    
    def __hash__(self):
        return hash(f"{NAMESPACE}:self.id")
    

    def result_command(self, count: int, type : str = "block", slot : int = 16) -> str:
        if count == 1:
            if type == "block":
                return f"loot replace block ~ ~ ~ container.{slot} loot {self.loot_table_path}"
            elif type == "entity":
                return f"loot replace entity @s container.{slot} loot {self.loot_table_path}"
            else:
                raise ValueError(f"Invalid type {type}")
        loot_table_inline = {
            "pools": [
                {
                    "rolls": 1,
                    "entries": [
                        {
                            "type": "minecraft:loot_table",
                            "value": self.loot_table_path,
                            "functions": [
                                {"function": "minecraft:set_count", "count": count}
                            ],
                        }
                    ],
                }
            ]
        }
        if type == "block":
            return f"loot replace block ~ ~ ~ container.{slot} loot {json.dumps(loot_table_inline)}"
        elif type == "entity":
            return f"loot replace entity @s container.{slot} loot {json.dumps(loot_table_inline)}"
        else:
            raise ValueError(f"Invalid type {type}")

    def to_nbt(self, ctx: Context, i: int) -> Compound:
        # return the nbt tag of the item smithed id "SelectedItem.components."minecraft:custom_data".smithed.id"
        return Compound(
            {
                "components": Compound(
                    {
                        "minecraft:custom_data": Compound(
                            {
                                "smithed": Compound(
                                    {"id": String(self.namespace_id(ctx))}
                                )
                            }
                        )
                    }
                ),
                "Slot": Byte(i),
            }
        )

    def create_translation(self, ctx: Union[Context, Generator]):
        # add the translations to the languages files for item_name
        if isinstance(self.item_name, tuple):
            export_translated_string(ctx, self.item_name)

        # add the translations to the languages files for lore
        for lore_line in self.lore:
            export_translated_string(ctx, lore_line)

    def create_lore(self):
        lore = []
        if self.lore:
            for i, lore_line in enumerate(self.lore):
                if isinstance(lore_line, tuple):
                    lore.append(
                        {
                            "translate": lore_line[0],
                            "color": "gray",
                            "italic": True,
                        }
                    )
                else:
                    lore.append(lore_line)
        lore.append({"translate": f"{NAMESPACE}.name", "color": "blue", "italic": True})
        return lore

    def create_custom_data(self, ctx: Union[Context, Generator]):
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        res : dict[str, Any] = {
            "smithed": {"id": self.namespace_id(real_ctx)},
        }
        if self.is_cookable:
            if real_ctx:
                real_ctx.meta["required_deps"].add("nbtsmelting")
            res["nbt_smelting"] = 1
        if self.block_properties:
            res["smithed"]["block"] = {"id": self.namespace_id(real_ctx)}
        return res

    def create_custom_block(self, ctx: Union[Context, Generator]):
        if not self.block_properties:
            return
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        deps_needed = ["custom_block_ext"]
        real_ctx.meta["required_deps"].update(deps_needed)

        self.create_custom_block_placement(ctx)
        self.create_custom_block_destroy(ctx)
        self.handle_world_generation(ctx)

    def handle_world_generation(self, ctx: Union[Context, Generator]):
        if not self.block_properties or not self.block_properties.world_generation:
            return
        deps_needed = ["%20chunk_scan.ores", "chunk_scan"]
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        real_ctx.meta["required_deps"].update(deps_needed)
        
        registry = f"{NAMESPACE}:impl/load_worldgen"
        registry_call = f"{NAMESPACE}:impl/calls/load_worldgen"
        registry_tag = f"{NAMESPACE}:post_load"
        post_load_tag = "load:post_load"
        for i, world_gen in enumerate(self.block_properties.world_generation):
            # init function
            if registry not in ctx.data.functions:
                ctx.data.functions[registry] = Function("# @public\n\n")
            if not post_load_tag in ctx.data.function_tags:
                ctx.data.function_tags[post_load_tag] = FunctionTag()
            if f"#{registry_tag}" not in ctx.data.function_tags[post_load_tag].data["values"]:
                ctx.data.function_tags[post_load_tag].data["values"].append(f"#{registry_tag}")
            if registry_tag not in ctx.data.function_tags:
                ctx.data.function_tags[registry_tag] = FunctionTag()
            if registry_call not in ctx.data.function_tags[registry_tag].data["values"]:
                ctx.data.function_tags[registry_tag].data["values"].append(registry_call)
            args = Compound()
            command = ""
            if world_gen.dimension:
                args["dimension"] = String(world_gen.dimension)
            if world_gen.biome:
                args["biome"] = String(world_gen.biome)
            if world_gen.biome_blacklist:
                args["biome_blacklist"] = Byte(world_gen.biome_blacklist)
            if len(args.keys()) > 0:
                command = f"data modify storage chunk_scan.ores:registry input set value {serialize_tag(args)}"


            ctx.data.functions[registry].append(f"""
scoreboard players set #registry.min_y chunk_scan.ores.data {world_gen.min_y}
scoreboard players set #registry.max_y chunk_scan.ores.data {world_gen.max_y}
scoreboard players set #registry.min_veins chunk_scan.ores.data {world_gen.min_veins}
scoreboard players set #registry.max_veins chunk_scan.ores.data {world_gen.max_veins}
scoreboard players set #registry.min_vein_size chunk_scan.ores.data {world_gen.min_vein_size}
scoreboard players set #registry.max_vein_size chunk_scan.ores.data {world_gen.max_vein_size}
scoreboard players set #registry.ignore_restrictions chunk_scan.ores.data {world_gen.ignore_restrictions}

{command}

function chunk_scan.ores:v1/api/register_ore

execute 
    if score #registry.result_id chunk_scan.ores.data matches -1
    run tellraw @a "Failed to register ore {self.id}_{i}"
execute
    unless score #registry.result_id chunk_scan.ores.data matches -1
    run scoreboard players operation #{self.id}_{i} {NAMESPACE}.data = #registry.result_id chunk_scan.ores.data

""")
        
            place_function_id_block = f"{NAMESPACE}:impl/custom_block_ext/on_place/{self.id}"
            place_function_tag_id_call = f"#{NAMESPACE}:calls/chunk_scan.ores/place_ore"
            place_function_id = f"{NAMESPACE}:impl/chunk_scan.ores/place_ore"
            chunk_scan_function_tag_id = f"chunk_scan.ores:v1/place_ore"
            if chunk_scan_function_tag_id not in ctx.data.function_tags:
                ctx.data.function_tags[chunk_scan_function_tag_id] = FunctionTag()
            if place_function_id not in ctx.data.functions:
                ctx.data.functions[place_function_id] = Function("# @public\n\n")
                ctx.data.function_tags[chunk_scan_function_tag_id].data["values"].append(place_function_tag_id_call)
            
            ctx.data.functions[place_function_id].append(f"""
execute
    if score #{self.id}_{i} {NAMESPACE}.data = #gen.id chunk_scan.ores.data
    run function {place_function_id_block}
""")
        

    
    def create_custom_block_placement(self, ctx: Union[Context, Generator]):
        if not self.block_properties:
            return
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        smithed_function_tag_id = f"custom_block_ext:event/on_place"
        internal_function_id = f"{NAMESPACE}:impl/custom_block_ext/on_place"
        ctx.data.function_tags.setdefault(smithed_function_tag_id).add(
            f"#{NAMESPACE}:calls/custom_block_ext/on_place"
        )

        ctx.data.functions.setdefault(internal_function_id, Function("# @public\n\n"))
        
        placement_code = f"setblock ~ ~ ~ {self.block_properties.base_block}"
        if self.block_properties.smart_waterlog:
            placement_code = f"setblock ~ ~ ~ {self.block_properties.base_block}[waterlogged=false]"

        ctx.data.functions[internal_function_id].append(
            f"""
execute
    if data storage custom_block_ext:main {{blockApi:{{id:"{self.namespace_id(real_ctx)}"}}}}
    run function ./on_place/{self.id}:
        scoreboard players set #facing {NAMESPACE}.math 0
        execute if block ~ ~ ~ furnace[facing=north] run scoreboard players set #facing {NAMESPACE}.math 0
        execute if block ~ ~ ~ furnace[facing=south] run scoreboard players set #facing {NAMESPACE}.math 1
        execute if block ~ ~ ~ furnace[facing=east] run scoreboard players set #facing {NAMESPACE}.math 2
        execute if block ~ ~ ~ furnace[facing=west] run scoreboard players set #facing {NAMESPACE}.math 3
        setblock ~ ~ ~ air
        {placement_code}

        execute 
            if score #facing {NAMESPACE}.math matches 0 
            summon item_display
            rotated 180 0 
            align xyz positioned ~.5 ~.5 ~.5 
            run function ./on_place/{self.id}/place_entity
        execute 
            if score #facing {NAMESPACE}.math matches 1 
            summon item_display
            rotated 0 0 
            align xyz positioned ~.5 ~.5 ~.5 
            run function ./on_place/{self.id}/place_entity
        execute 
            if score #facing {NAMESPACE}.math matches 2 
            summon item_display
            rotated -90 0 align xyz positioned ~.5 ~.5 ~.5 
            run function ./on_place/{self.id}/place_entity
        execute 
            if score #facing {NAMESPACE}.math matches 3 
            summon item_display
            rotated 90 0 
            align xyz positioned ~.5 ~.5 ~.5 
            run function ./on_place/{self.id}/place_entity


prepend function ./on_place/{self.id}/place_entity:
    tag @s add {NAMESPACE}.{self.id}
    tag @s add {NAMESPACE}.block
    tag @s add {self.block_properties.base_block_tag}
    tag @s add smithed.block
    tag @s add smithed.strict
    tag @s add smithed.entity

    data modify entity @s item set value {{
        id:"{self.block_properties.base_item_placed or self.base_item}",
        count:1,
        components:{{"minecraft:item_model":"{self.block_properties.item_model_placed or self.item_model}"}}
    }}

    data merge entity @s {{transformation:{{scale:[1.001f,1.001f,1.001f]}}}}
    data merge entity @s {{brightness:{{sky:10,block:15}}}}
    tp @s ~ ~ ~ ~ ~
"""
        )
    
    def create_custom_block_destroy(self, ctx: Union[Context, Generator]):
        if not self.block_properties:
            return
        destroy_function_id = f"{NAMESPACE}:impl/custom_block_ext/destroy/{self.id}"
        if destroy_function_id not in ctx.data.functions:
            ctx.data.functions[destroy_function_id] = Function()
        ctx.data.functions[destroy_function_id].prepend(f"""
execute
    as @e[type=item,nbt={{Item:{{id:"{self.block_properties.base_block}",count:1}}}},limit=1,sort=nearest,distance=..3]
    run function ~/spawn_item:
        loot spawn ~ ~ ~ loot {self.loot_table_path}
        kill @s

""")
        ctx.data.functions[destroy_function_id].append("kill @s")
        all_same_function_id = f"{NAMESPACE}:impl/custom_block_ext/destroy_{self.block_properties.base_block.replace('minecraft:', '')}"
        if all_same_function_id not in ctx.data.functions:
            ctx.data.functions[all_same_function_id] = Function()
        ctx.data.functions[all_same_function_id].append(
            f"execute if entity @s[tag={NAMESPACE}.{self.id}] run function {destroy_function_id}"
        )
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        opts = real_ctx.validate("simple_item_plugin", SimpleItemPluginOptions)

        predicate_path = f"{NAMESPACE}:block/destroy_{self.block_properties.base_block.replace('minecraft:', '')}"

        ctx.data.functions.setdefault(opts.tick_function).prepend(f"""
execute 
    as @e[type=item_display,tag={self.block_properties.base_block_tag},predicate=!{predicate_path}] 
    at @s
    run function {all_same_function_id}
""")
        ctx.data.predicates.setdefault(predicate_path).data = {
            "condition": "minecraft:location_check",
            "predicate": {
                "block": {
                    "blocks": self.block_properties.base_block,
                }
            }
        }



    def set_components(self) -> list[dict[str, Any]]:
        res = []
        for key, value in self.components_extra.items():
            if key == "minecraft:custom_data":
                res.append(
                    {"function": "minecraft:set_custom_data", "tag": value}
                )
            elif key == "special:item_modifier":
                if isinstance(value, str):
                    res.append({"function": "minecraft:reference", "name": value})
                elif isinstance(value, tuple):
                    for v in value:
                        res.append({"function": "minecraft:reference", "name": v})
                else:
                    raise ValueError(f"Invalid value for special:item_modifier {value}")
            else:
                res.append(
                    {"function": "minecraft:set_components", "components": {key: value}}
                )
                
        return res

    def create_loot_table(self, ctx: Union[Context, Generator]):
        ctx.data.loot_tables[self.loot_table_path] = LootTable(
            {
                "pools": [
                    {
                        "rolls": 1,
                        "entries": [
                            {
                                "type": "minecraft:item",
                                "name": self.base_item,
                                "functions": [
                                    {
                                        "function": "minecraft:set_components",
                                        "components": {
                                            "minecraft:item_model": self.item_model,
                                            "minecraft:custom_data": self.create_custom_data(ctx),
                                        },
                                    },
                                    {
                                        "function": "minecraft:set_name",
                                        "entity": "this",
                                        "target": "item_name",
                                        "name": self.get_item_name(),
                                    },
                                    {
                                        "function": "minecraft:set_lore",
                                        "entity": "this",
                                        "lore": self.create_lore(),
                                        "mode": "replace_all",
                                    },
                                    *self.set_components(),
                                ],
                            }
                        ],
                    }
                ]
            }
        )

    def get_item_name(self):
        if not isinstance(self.item_name, tuple):
            return self.item_name
        return {
            "translate": self.item_name[0],
            "color": "white",
            "fallback": self.item_name[1].get(Lang.en_us, self.item_name[0]),
        }

    def create_assets(self, ctx: Union[Context, Generator]):
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        
        
        if self.item_model in real_ctx.assets.item_models:
            return
        ctx.assets.item_models[self.item_model] = ItemModel({
            "model": {
                "type": "model",
                "model": self.model_path,
            }
        })

        # create the custom model
        if self.model_path in ctx.assets.models:
            return

        if not self.block_properties:
            if not self.is_armor:
                ctx.assets.models[self.model_path] = Model(
                    {"parent": "item/generated", "textures": {"layer0": self.model_path}}
                )
            else:
                ctx.assets.models[self.model_path] = Model(
                    {
                        "parent": "item/generated",
                        "textures": {
                            "layer0": self.clear_texture_path,
                            "layer1": self.model_path,
                        },
                    }
                )
            if not self.model_path in real_ctx.assets.textures:
                logger.warning(f"Texture {self.model_path} not found in the resource pack")
        elif self.block_properties.all_same_faces:
            ctx.assets.models[self.model_path] = Model(
                {
                    "parent": "minecraft:block/cube_all",
                    "textures": {"all": f"{NAMESPACE}:block/{self.id}"},
                }
            )
        else:
            ctx.assets.models[self.model_path] = Model(
                {
                    "parent": "minecraft:block/orientable_with_bottom",
                    "textures": {
                        "top": f"{NAMESPACE}:block/{self.id}_top",
                        "side": f"{NAMESPACE}:block/{self.id}_side",
                        "bottom": f"{NAMESPACE}:block/{self.id}_bottom",
                        "front": f"{NAMESPACE}:block/{self.id}_front",
                    },
                }
            )

    def export(self, ctx: Union[Context, Generator]) -> Self:
        self.create_loot_table(ctx)
        self.create_translation(ctx)
        self.create_custom_block(ctx)
        self.create_assets(ctx)

        return super().export(ctx)
