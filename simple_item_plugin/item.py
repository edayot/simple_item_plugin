from dataclasses import dataclass, field
from simple_item_plugin.types import TextComponent, TextComponent_base, NAMESPACE, TranslatedString
from beet import Context, FunctionTag, Function, LootTable, Model
from typing import Any
from typing_extensions import TypedDict, NotRequired, Literal
from simple_item_plugin.utils import export_translated_string
from beet.contrib.vanilla import Vanilla

from nbtlib.tag import Compound, String, Byte
from nbtlib import serialize_tag
import json


Registry: dict[str, "Item"] = {}


class WorldGenerationParams(TypedDict):
    min_y: int
    max_y: int
    min_veins: int
    max_veins: int
    min_vein_size: int
    max_vein_size: int
    ignore_restrictions: Literal[0, 1]
    dimension: NotRequired[str]
    biome: NotRequired[str]
    biome_blacklist: NotRequired[Literal[0, 1]]

class BlockProperties(TypedDict):
    base_block: str
    smart_waterlog: NotRequired[bool]
    all_same_faces: NotRequired[bool]
    world_generation: NotRequired[list[WorldGenerationParams]]

    base_item_placed: NotRequired[str]
    custom_model_data_placed: NotRequired[int]
    


@dataclass
class Item:
    id: str
    # the translation key, the
    item_name: TextComponent | TranslatedString
    lore: list[TextComponent_base] = field(default_factory=list)

    components_extra: dict[str, Any] = field(default_factory=dict)

    base_item: str = "minecraft:jigsaw"
    custom_model_data: int = 1430000

    block_properties: BlockProperties = None
    is_cookable: bool = False
    is_armor: bool = False

    char_index: int = 0
    page_index: int = -1

    @property
    def loot_table_path(self):
        return f"{NAMESPACE}:impl/items/{self.id}"
    
    @property
    def namespace_id(self):
        return f"{NAMESPACE}:{self.id}"
    
    @property
    def model_path(self):
        return f"{NAMESPACE}:item/{self.id}"
    
    @property
    def minimal_representation(self) -> dict:
        return {
            "id": self.base_item,
            "components": {
                "minecraft:item_name": json.dumps(self.get_item_name()),
            }
        }
    
    def __hash__(self):
        return hash(self.id)
    


    def __post_init__(self):
        assert self.id not in Registry, f"Item {self.id} already exists"
        Registry[self.id] = self

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

    def to_nbt(self, i: int) -> Compound:
        # return the nbt tag of the item smithed id "SelectedItem.components."minecraft:custom_data".smithed.id"
        return Compound(
            {
                "components": Compound(
                    {
                        "minecraft:custom_data": Compound(
                            {
                                "smithed": Compound(
                                    {"id": String(self.namespace_id)}
                                )
                            }
                        )
                    }
                ),
                "Slot": Byte(i),
            }
        )

    def create_translation(self, ctx: Context):
        # add the translations to the languages files for item_name
        if not isinstance(self.item_name, dict):
            export_translated_string(ctx, self.item_name)

        # add the translations to the languages files for lore
        for lore_line in self.lore:
            export_translated_string(ctx, lore_line)

    def create_lore(self):
        lore = []
        if self.lore:
            lore.append(*self.lore)
        lore.append({"translate": f"{NAMESPACE}.name", "color": "blue", "italic": True})
        return lore

    def create_custom_data(self):
        res = {
            "smithed": {"id": self.namespace_id},
        }
        if self.is_cookable:
            res["nbt_smelting"] = Byte(1)
        if self.block_properties:
            res["smithed"]["block"] = {"id": self.namespace_id}
        return res

    def create_custom_block(self, ctx: Context):
        if not self.block_properties:
            return
        self.create_custom_block_placement(ctx)
        self.create_custom_block_destroy(ctx)
        self.handle_world_generation(ctx)

    def handle_world_generation(self, ctx: Context):
        if not self.block_properties.get("world_generation", None):
            return
        for i, world_gen in enumerate(self.block_properties["world_generation"]):
            registry = f"{NAMESPACE}:impl/load_worldgen"
            if registry not in ctx.data.functions:
                ctx.data.functions[registry] = Function()
            
            args = Compound()
            command = ""
            if "dimension" in world_gen:
                args["dimension"] = String(world_gen["dimension"])
            if "biome" in world_gen:
                args["biome"] = String(world_gen["biome"])
            if "biome_blacklist" in world_gen:
                args["biome_blacklist"] = Byte(world_gen["biome_blacklist"])
            if len(args.keys()) > 0:
                command = f"data modify storage chunk_scan.ores:registry input set value {serialize_tag(args)}"


            ctx.data.functions[registry].append(f"""
scoreboard players set #registry.min_y chunk_scan.ores.data {world_gen["min_y"]}
scoreboard players set #registry.max_y chunk_scan.ores.data {world_gen["max_y"]}
scoreboard players set #registry.min_veins chunk_scan.ores.data {world_gen["min_veins"]}
scoreboard players set #registry.max_veins chunk_scan.ores.data {world_gen["max_veins"]}
scoreboard players set #registry.min_vein_size chunk_scan.ores.data {world_gen["min_vein_size"]}
scoreboard players set #registry.max_vein_size chunk_scan.ores.data {world_gen["max_vein_size"]}
scoreboard players set #registry.ignore_restrictions chunk_scan.ores.data {world_gen["ignore_restrictions"]}

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
        

    
    def create_custom_block_placement(self, ctx: Context):
        smithed_function_tag_id = f"custom_block_ext:event/on_place"
        internal_function_id = f"{NAMESPACE}:impl/custom_block_ext/on_place"
        if smithed_function_tag_id not in ctx.data.function_tags:
            ctx.data.function_tags[smithed_function_tag_id] = FunctionTag()
        ctx.data.function_tags[smithed_function_tag_id].data["values"].append(
            f"#{NAMESPACE}:calls/custom_block_ext/on_place"
        )

        if internal_function_id not in ctx.data.functions:
            ctx.data.functions[internal_function_id] = Function("# @public\n\n")
        
        placement_code = f"setblock ~ ~ ~ {self.block_properties['base_block']}"
        if self.block_properties.get("smart_waterlog", False):
            placement_code = f"setblock ~ ~ ~ {self.block_properties['base_block']}[waterlogged=false]"

        ctx.data.functions[internal_function_id].append(
            f"""
execute
    if data storage custom_block_ext:main {{blockApi:{{id:"{NAMESPACE}:{self.id}"}}}}
    run function ./on_place/{self.id}:
        setblock ~ ~ ~ air
        {placement_code}
        execute 
            align xyz positioned ~.5 ~.5 ~.5
            summon item_display
            run function ./on_place/{self.id}/place_entity

prepend function ./on_place/{self.id}/place_entity:
    tag @s add {NAMESPACE}.{self.id}
    tag @s add {NAMESPACE}.block
    tag @s add {NAMESPACE}.block.{self.block_properties["base_block"].replace("minecraft:", "")}
    tag @s add smithed.block
    tag @s add smithed.strict
    tag @s add smithed.entity

    data modify entity @s item set value {{
        id:"{self.block_properties.get("base_item_placed") or self.base_item}",
        count:1,
        components:{{"minecraft:custom_model_data":{self.block_properties.get("custom_model_data_placed") or self.custom_model_data}}}
    }}

    data merge entity @s {{transformation:{{scale:[1.001f,1.001f,1.001f]}}}}
    data merge entity @s {{brightness:{{sky:10,block:15}}}}
"""
        )
    
    def create_custom_block_destroy(self, ctx: Context):
        destroy_function_id = f"{NAMESPACE}:impl/blocks/destroy/{self.id}"
        if destroy_function_id not in ctx.data.functions:
            ctx.data.functions[destroy_function_id] = Function()
        ctx.data.functions[destroy_function_id].prepend(f"""
execute
    as @e[type=item,nbt={{Item:{{id:"{self.block_properties["base_block"]}",count:1}}}},limit=1,sort=nearest,distance=..3]
    run function ~/spawn_item:
        loot spawn ~ ~ ~ loot {self.loot_table_path}
        kill @s

kill @s

""")
        all_same_function_id = f"{NAMESPACE}:impl/blocks/destroy_{self.block_properties['base_block'].replace('minecraft:', '')}"
        if all_same_function_id not in ctx.data.functions:
            ctx.data.functions[all_same_function_id] = Function()
        ctx.data.functions[all_same_function_id].append(
            f"execute if entity @s[tag={NAMESPACE}.{self.id}] run function {destroy_function_id}"
        )

    def set_components(self):
        res = []
        for key, value in self.components_extra.items():
            res.append(
                {"function": "minecraft:set_components", "components": {key: value}}
            )
        return res

    def create_loot_table(self, ctx: Context):
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
                                            "minecraft:custom_model_data": self.custom_model_data,
                                            "minecraft:custom_data": self.create_custom_data(),
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
        }

    def create_assets(self, ctx: Context):
        key = f"minecraft:item/{self.base_item.split(':')[1]}"
        if not key in ctx.assets.models:
            vanilla = ctx.inject(Vanilla).releases[ctx.meta["minecraft_version"]]
            # get the default model for this item
            ctx.assets.models[key] = Model(vanilla.assets.models[key].data.copy())
            ctx.assets.models[key].data["overrides"] = []

        # add the custom model data to the model
        ctx.assets.models[key].data["overrides"].append(
            {
                "predicate": {"custom_model_data": self.custom_model_data},
                "model": self.model_path,
            }
        )
        # create the custom model
        if self.model_path in ctx.assets.models:
            return
        if not self.block_properties and not self.is_armor:
            ctx.assets.models[self.model_path] = Model(
                {"parent": "item/generated", "textures": {"layer0": self.model_path}}
            )
        elif not self.block_properties and self.is_armor:
            ctx.assets.models[self.model_path] = Model(
                {
                    "parent": "item/generated",
                    "textures": {
                        "layer0": f"{NAMESPACE}:item/clear",
                        "layer1": self.model_path,
                    },
                }
            )
        elif self.block_properties.get("all_same_faces", True):
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

    def export(self, ctx: Context):
        self.create_loot_table(ctx)
        self.create_translation(ctx)
        self.create_custom_block(ctx)
        self.create_assets(ctx)
