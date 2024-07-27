from dataclasses import dataclass, field
from simple_item_plugin.types import TextComponent, TextComponent_base, NAMESPACE, TranslatedString, Lang
from beet import Context, FunctionTag, Function, LootTable, Model, Texture, ResourcePack, Generator
from PIL import Image
from typing import Any, Optional, TYPE_CHECKING, Union
from typing_extensions import TypedDict, NotRequired, Literal, Optional
from simple_item_plugin.utils import export_translated_string, SimpleItemPluginOptions
from beet.contrib.vanilla import Vanilla

from nbtlib.tag import Compound, String, Byte
from nbtlib import serialize_tag
import json
from pydantic import BaseModel
import logging
from copy import deepcopy
from weld_deps.main import WeldDepsConfig
from enum import Enum

logger = logging.getLogger("simple_item_plugin")

if TYPE_CHECKING:
    from simple_item_plugin.mineral import Mineral
else:
    Mineral = Any


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

class BlockProperties(BaseModel):
    base_block: str
    smart_waterlog: Optional[bool] = False
    all_same_faces: Optional[bool] = True
    world_generation: Optional[list[WorldGenerationParams]] = None

    base_item_placed: Optional[str] = None
    custom_model_data_placed: Optional[int] = None
    

class MergeOverridesPolicy(Enum):
    clear = "clear"
    generate_new = "generate_new"
    use_model_path = "use_model_path"
    use_vanilla = "use_vanilla"
    delete = "delete"
    replace_from_layer0 = "layer0"
    replace_from_layer1 = "layer1"
    replace_from_layer2 = "layer2"
    replace_from_layer3 = "layer3"
    replace_from_layer4 = "layer4"
    replace_from_layer5 = "layer5"
    replace_from_layer6 = "layer6"


class Item(BaseModel):
    id: str
    # the translation key, the
    item_name: TextComponent | TranslatedString | None = None
    lore: list[TranslatedString] = field(default_factory=list)

    components_extra: dict[str, Any] = field(default_factory=dict)

    base_item: str = "minecraft:jigsaw"

    def custom_model_data(self, ctx: Union[Context, Generator]):
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        cmd_cache = real_ctx.meta["simple_item_plugin"]["stable_cache"].setdefault("cmd", {})
        if self.id not in cmd_cache:
            opts = real_ctx.validate("simple_item_plugin", SimpleItemPluginOptions)
            cmd_cache[self.id] = max(cmd_cache.values(), default=opts.custom_model_data) + 1
        return cmd_cache[self.id]
        
    block_properties: BlockProperties | None = None
    is_cookable: bool = False
    is_armor: bool = False
    merge_overrides_policy: Optional[dict[str, MergeOverridesPolicy]] = None

    mineral: Optional[Mineral] = None

    @property
    def clear_texture_path(self):
        return f"{NAMESPACE}:item/clear"

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
            lore.append(*self.lore)
        lore.append({"translate": f"{NAMESPACE}.name", "color": "blue", "italic": True})
        return lore

    def create_custom_data(self):
        res : dict[str, Any] = {
            "smithed": {"id": self.namespace_id},
        }
        if self.is_cookable:
            res["nbt_smelting"] = 1
        if self.block_properties:
            res["smithed"]["block"] = {"id": self.namespace_id}
        return res

    def create_custom_block(self, ctx: Union[Context, Generator]):
        if not self.block_properties:
            return
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        deps = real_ctx.validate("weld_deps", WeldDepsConfig)
        assert deps
        assert deps.deps
        my_deps = ["custom_block_ext", "%20chunk_scan.ores", "chunk_scan"]
        for dep in my_deps:
            assert dep in [d.id for d in deps.deps], f"Missing dependency {dep} in the beet config file"

        self.create_custom_block_placement(ctx)
        self.create_custom_block_destroy(ctx)
        self.handle_world_generation(ctx)

    def handle_world_generation(self, ctx: Union[Context, Generator]):
        if not self.block_properties or not self.block_properties.world_generation:
            return
        for i, world_gen in enumerate(self.block_properties.world_generation):
            registry = f"{NAMESPACE}:impl/load_worldgen"
            if registry not in ctx.data.functions:
                ctx.data.functions[registry] = Function()
            
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
        smithed_function_tag_id = f"custom_block_ext:event/on_place"
        internal_function_id = f"{NAMESPACE}:impl/custom_block_ext/on_place"
        if smithed_function_tag_id not in ctx.data.function_tags:
            ctx.data.function_tags[smithed_function_tag_id] = FunctionTag()
        ctx.data.function_tags[smithed_function_tag_id].data["values"].append(
            f"#{NAMESPACE}:calls/custom_block_ext/on_place"
        )

        if internal_function_id not in ctx.data.functions:
            ctx.data.functions[internal_function_id] = Function("# @public\n\n")
        
        placement_code = f"setblock ~ ~ ~ {self.block_properties.base_block}"
        if self.block_properties.smart_waterlog:
            placement_code = f"setblock ~ ~ ~ {self.block_properties.base_block}[waterlogged=false]"

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
    tag @s add {NAMESPACE}.block.{self.block_properties.base_block.replace("minecraft:", "")}
    tag @s add smithed.block
    tag @s add smithed.strict
    tag @s add smithed.entity

    data modify entity @s item set value {{
        id:"{self.block_properties.base_item_placed or self.base_item}",
        count:1,
        components:{{"minecraft:custom_model_data":{self.block_properties.custom_model_data_placed or self.custom_model_data(ctx)}}}
    }}

    data merge entity @s {{transformation:{{scale:[1.001f,1.001f,1.001f]}}}}
    data merge entity @s {{brightness:{{sky:10,block:15}}}}
"""
        )
    
    def create_custom_block_destroy(self, ctx: Union[Context, Generator]):
        if not self.block_properties:
            return
        destroy_function_id = f"{NAMESPACE}:impl/blocks/destroy/{self.id}"
        if destroy_function_id not in ctx.data.functions:
            ctx.data.functions[destroy_function_id] = Function()
        ctx.data.functions[destroy_function_id].prepend(f"""
execute
    as @e[type=item,nbt={{Item:{{id:"{self.block_properties.base_block}",count:1}}}},limit=1,sort=nearest,distance=..3]
    run function ~/spawn_item:
        loot spawn ~ ~ ~ loot {self.loot_table_path}
        kill @s

kill @s

""")
        all_same_function_id = f"{NAMESPACE}:impl/blocks/destroy_{self.block_properties.base_block.replace('minecraft:', '')}"
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
                                            "minecraft:custom_model_data": self.custom_model_data(ctx),
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
            "fallback": self.item_name[1][Lang.en_us],
        }

    def create_assets(self, ctx: Union[Context, Generator]):
        key = f"minecraft:item/{self.base_item.split(':')[1]}"
        current_model = ctx.assets.models.get(key, None)
        rp = ResourcePack()
        
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        vanilla = real_ctx.inject(Vanilla).releases[real_ctx.meta["minecraft_version"]]
        # get the default model for this item
        model = Model(vanilla.assets.models[key].data.copy())
        if "overrides" in model.data:
            self.create_overrides(ctx, model, rp, key)
            ctx.assets.merge(rp)
            return
                
        model.data["overrides"] = []
        # add the custom model data to the model
        model.data["overrides"].append(
            {
                "predicate": {"custom_model_data": self.custom_model_data(ctx)},
                "model": self.model_path,
            }
        )
        rp.models[key] = model
        ctx.assets.merge(rp)
        
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
            if not self.model_path in ctx.assets.textures:
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

    def get_new_texture_path(self, model: Model, texture_key: str, texture_path: str, merge_policy: MergeOverridesPolicy) -> tuple[str | None, bool]:
        match merge_policy:
            case MergeOverridesPolicy.clear:
                new_texture_path = self.clear_texture_path
                trow_warning = False
            case MergeOverridesPolicy.generate_new:
                new_texture_path = self.model_path + "/" + texture_path.split("/")[-1]
                trow_warning = True
            case MergeOverridesPolicy.use_model_path:
                new_texture_path = self.model_path
                trow_warning = True
            case MergeOverridesPolicy.use_vanilla:
                new_texture_path = texture_path
                trow_warning = False
            case MergeOverridesPolicy.delete:
                new_texture_path = None
                trow_warning = False
            case MergeOverridesPolicy.replace_from_layer0 | MergeOverridesPolicy.replace_from_layer1 | MergeOverridesPolicy.replace_from_layer2 | MergeOverridesPolicy.replace_from_layer3 | MergeOverridesPolicy.replace_from_layer4 | MergeOverridesPolicy.replace_from_layer5 | MergeOverridesPolicy.replace_from_layer6:
                new_layer = merge_policy.value
                new_merge_policy = MergeOverridesPolicy.generate_new
                if self.merge_overrides_policy and new_layer in self.merge_overrides_policy:
                    new_merge_policy = self.merge_overrides_policy[new_layer]
                if new_merge_policy == MergeOverridesPolicy.delete:
                    new_merge_policy = MergeOverridesPolicy.use_vanilla
                new_texture_path, trow_warning = self.get_new_texture_path(model, new_layer, model.data["textures"][new_layer], new_merge_policy)
                trow_warning = False
            case _:
                raise ValueError(f"Invalid merge policy {merge_policy}")
        return new_texture_path, trow_warning

    def create_overrides(self, ctx: Union[Context, Generator], model: Model, rp: ResourcePack, key: str):
        if any([
            o["predicate"].get("custom_model_data", None) == self.custom_model_data(ctx)
            for o in ctx.assets.models.get(key, Model()).data.get("overrides", [])
        ]):
            # user defined override already exists, no need to create a new one
            return
        model.data["overrides"].append({
            "predicate": {"custom_model_data": self.custom_model_data(ctx)},
            "model": self.model_path,
        })
        if not self.is_armor:
            rp.models[self.model_path] = Model(
                {"parent": "item/generated", "textures": {"layer0": self.model_path}}
            )
        else:
            rp.models[self.model_path] = Model(
                {
                    "parent": "item/generated",
                    "textures": {
                        "layer0": f"{NAMESPACE}:item/clear",
                        "layer1": self.model_path,
                    },
                }
            )
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        vanilla = real_ctx.inject(Vanilla)
        release = vanilla.releases[real_ctx.meta["minecraft_version"]]
        new_overrides = []
        for override in list(model.data["overrides"]):
            o = deepcopy(override)
            if "custom_model_data" in o["predicate"]:
                continue
            o["predicate"]["custom_model_data"] = self.custom_model_data(ctx)
            namespace_model_path = self.model_path + "/" + o["model"].split("/")[-1]
            minecraft_model_path = o["model"]
            minecraft_model_path = f"minecraft:{minecraft_model_path}" if ":" not in minecraft_model_path else minecraft_model_path

            # create the model
            minecraft_model = Model(release.assets.models[minecraft_model_path].data.copy())
            for texture_key, texture_path in list(minecraft_model.data["textures"].items()):
                merge_policy = MergeOverridesPolicy.generate_new
                if self.merge_overrides_policy and texture_key in self.merge_overrides_policy:
                    merge_policy = self.merge_overrides_policy[texture_key]
                new_texture_path, trow_warning = self.get_new_texture_path(minecraft_model, texture_key, texture_path, merge_policy)
                if new_texture_path:
                    minecraft_model.data["textures"][texture_key] = new_texture_path
                    if trow_warning and new_texture_path not in ctx.assets.textures:
                        logger.warning(f"Texture {new_texture_path} not found in the resource pack")
            for texture_key, texture_path in list(minecraft_model.data["textures"].items()):
                # test if we have to delete the texture
                merge_policy = MergeOverridesPolicy.generate_new
                if self.merge_overrides_policy and texture_key in self.merge_overrides_policy:
                    merge_policy = self.merge_overrides_policy[texture_key]
                if merge_policy == MergeOverridesPolicy.delete:
                    del minecraft_model.data["textures"][texture_key]



            rp.models[namespace_model_path] = minecraft_model
            o["model"] = namespace_model_path
            new_overrides.append(o)
        model.data["overrides"].extend(new_overrides)
        rp.models[key] = model
        
    def export(self, ctx: Union[Context, Generator]):
        self.create_loot_table(ctx)
        self.create_translation(ctx)
        self.create_custom_block(ctx)
        self.create_assets(ctx)

        # add the item to the registry
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        assert self.id not in real_ctx.meta.setdefault("registry", {}).setdefault("items", {})
        real_ctx.meta["registry"]["items"][self.id] = self
        return self

    @classmethod
    def get_from_id(cls, ctx: Context, id: str) -> Optional["Item"]:
        return ctx.meta.get("registry", {}).get("items", {}).get(id, None)