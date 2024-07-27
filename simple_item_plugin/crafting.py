from dataclasses import dataclass, field
from nbtlib import serialize_tag
from nbtlib.tag import (
    String,
    List,
    Compound,
    IntArray,
    Int,
    Byte,
    Short,
    Long,
    Float,
    Double,
)
from typing import Any, Literal, Union, Tuple
from beet import Context, Function, FunctionTag, Recipe
from simple_item_plugin.item import Item
from simple_item_plugin.types import NAMESPACE
import json



@dataclass
class VanillaItem:
    id: str
    def __hash__(self) -> int:
        return hash(self.id)


    def to_nbt(self, i: int):
        return Compound({"id": String(self.id), "Slot": Byte(i)})

    def result_command(self, count: int, type : str = "block", slot : int = 16) -> str:
        if type == "block":
            return f"item replace block ~ ~ ~ container.{slot} with {self.id} {count} "
        elif type == "entity":
            return f"item replace entity @s container.{slot} with {self.id} {count} "
        else:
            raise ValueError(f"Invalid type {type}")
    
    @property
    def model_path(self):
        return f"minecraft:item/{self.id.replace('minecraft:', '')}"
    
    @property
    def minimal_representation(self) -> dict:
        return {"id": self.id}

ItemType = Union[Item, VanillaItem, None]
ItemLine = Tuple[ItemType, ItemType, ItemType]

@dataclass
class ShapedRecipe:
    items: Tuple[ItemLine, ItemLine, ItemLine]
    result: tuple[Item | VanillaItem, int]
    flags: list[str] = field(default_factory=lambda: [])

    def get_command(self, if_data_storage: str):
        if not self.flags:
            return f"""
execute 
    store result score @s smithed.data 
    if entity @s[scores={{smithed.data=0}}] 
    {if_data_storage}
    run {self.result[0].result_command(self.result[1])}
"""
        flags_command = f'data modify storage smithed.crafter:input flags set value {json.dumps(self.flags)}'
        function_name = f"~/{self.result[0].id.removeprefix('minecraft:')}_{self.result[1]}"
        return f"""
execute 
    if entity @s[scores={{smithed.data=0}}] 
    {if_data_storage}
    run function {function_name}:
        {flags_command}
        {self.result[0].result_command(self.result[1])}
        scoreboard players set @s smithed.data 1
"""

    def export(self, ctx: Context):
        """
        This function export the smithed crafter recipes to the ctx variable.
        """
        ctx.meta.setdefault("registry", {}).setdefault("recipes", []).append(self)
        air = lambda i: Compound({"id": String("minecraft:air"), "Slot": Byte(i)})

        smithed_recipe = {}
        for i, item_row in enumerate(self.items):
            row_check_list = [
                x.to_nbt(i) if x is not None else air(i) for i, x in enumerate(item_row)
            ]
            smithed_recipe[String(i)] = List[Compound](row_check_list)

        if_data_storage = f"if data storage smithed.crafter:input recipe{serialize_tag(Compound(smithed_recipe))}"

        if len(self.items) < 3:
            for i in range(len(self.items), 3):
                if_data_storage += (
                    f"\n\tif data storage smithed.crafter:input {{recipe:{{{i}:[]}}}}"
                )

        function_path = f"{NAMESPACE}:impl/smithed.crafter/recipes"
        function_path_calls = f"{NAMESPACE}:impl/calls/smithed.crafter/recipes"
        tag_smithed_crafter_recipes = "smithed.crafter:event/recipes"
        tag_namespace = f"{NAMESPACE}:smithed.crafter/recipes"
        if not tag_smithed_crafter_recipes in ctx.data.function_tags:
            ctx.data.function_tags[tag_smithed_crafter_recipes] = FunctionTag()
        if not tag_namespace in ctx.data.function_tags:
            ctx.data.function_tags[tag_namespace] = FunctionTag()
        if function_path not in ctx.data.functions:
            ctx.data.functions[function_path] = Function("# @public\n\n")
        if f"#{tag_namespace}" not in ctx.data.function_tags[tag_smithed_crafter_recipes].data["values"]:
            ctx.data.function_tags[tag_smithed_crafter_recipes].data["values"].append(
                f"#{tag_namespace}"
            )
        if function_path_calls not in ctx.data.function_tags[tag_namespace].data["values"]:
            ctx.data.function_tags[tag_namespace].data["values"].append(
                function_path_calls
            )

        ctx.data.functions[function_path].append(self.get_command(if_data_storage))


@dataclass
class ShapelessRecipe:
    items: list[tuple[Item | VanillaItem, int]]
    result: tuple[Item | VanillaItem, int]

    def export(self, ctx: Context):
        """
        This function export the smithed crafter recipes to the ctx variable.
        """
        global_count = len(self.items)

        recipe = List[Compound]([])
        for i, (item, count) in enumerate(self.items):
            nbt = item.to_nbt(i)
            nbt["count"] = Int(count)
            del nbt["Slot"]
            recipe.append(nbt)

        result_command = self.result[0].result_command(self.result[1])

        command = f"""
execute 
    store result score @s smithed.data 
    if entity @s[scores={{smithed.data=0}}] 
    if score count smithed.data matches {global_count} 
    if data storage smithed.crafter:input {{recipe:{serialize_tag(recipe)}}}
    run {result_command}
"""
        function_path = f"{NAMESPACE}:impl/smithed.crafter/shapeless_recipes"
        function_path_calls = f"{NAMESPACE}:impl/calls/smithed.crafter/shapeless_recipes"
        tag_smithed_crafter_shapeless_recipes = (
            "smithed.crafter:event/shapeless_recipes"
        )
        tag_namespace = f"{NAMESPACE}:smithed.crafter/shapeless_recipes"
        if not tag_smithed_crafter_shapeless_recipes in ctx.data.function_tags:
            ctx.data.function_tags[
                tag_smithed_crafter_shapeless_recipes
            ] = FunctionTag()
        if not tag_namespace in ctx.data.function_tags:
            ctx.data.function_tags[tag_namespace] = FunctionTag()
        if function_path not in ctx.data.functions:
            ctx.data.functions[function_path] = Function("# @public\n\n")
        if f"#{tag_namespace}" not in ctx.data.function_tags[tag_smithed_crafter_shapeless_recipes].data["values"]:
            ctx.data.function_tags[tag_smithed_crafter_shapeless_recipes].data[
                "values"
            ].append(f"#{tag_namespace}")
        if function_path_calls not in ctx.data.function_tags[tag_namespace].data["values"]:
            ctx.data.function_tags[tag_namespace].data[
                "values"
            ].append(function_path_calls)

        ctx.data.functions[function_path].append(command)


@dataclass
class NBTSmelting:
    item: Item | VanillaItem
    result: tuple[Item | VanillaItem, int]
    types: list[Literal["furnace", "blast_furnace", "smoker"]] = field(
        default_factory=lambda: ["furnace"]
    )

    def export(self, ctx: Context):
        """
        This function export the NBTSmelting recipes to the ctx variable.
        """
        for type in self.types:
            self.export_type(ctx, type)

    def type_to_crafting_type(self, type: str):
        if type == "furnace":
            return "smelting"
        if type == "blast_furnace":
            return "blasting"
        if type == "smoker":
            return "smoking"
        return "smelting"

    def export_type(self, ctx: Context, type: str):
        recipe = self.item.to_nbt(0)
        del recipe["Slot"]
        recipe = serialize_tag(recipe)

        result_command = self.result[0].result_command(self.result[1])

        command = f"""
execute 
    if data storage nbt_smelting:io item{recipe} 
    run function ~/{self.item.id}:
        execute positioned -30000000 23 1610 run {result_command}
        item replace block ~ ~ ~ container.2 from block -30000000 23 1610 container.16
"""
        function_path = f"{NAMESPACE}:impl/nbt_smelting/{type}"
        tag_nbt_smelting_furnace = f"nbt_smelting:v1/{type}"
        if not tag_nbt_smelting_furnace in ctx.data.function_tags:
            ctx.data.function_tags[tag_nbt_smelting_furnace] = FunctionTag()
        if function_path not in ctx.data.functions:
            ctx.data.functions[function_path] = Function("# @public\n\n")
            ctx.data.function_tags[tag_nbt_smelting_furnace].data["values"].append(
                f"#{NAMESPACE}:calls/nbt_smelting/{type}"
            )

        ctx.data.functions[function_path].append(command)

        if isinstance(self.item, Item):
            ctx.data.recipes[
                f"{NAMESPACE}:{self.item.base_item.replace('minecraft:','')}/{self.type_to_crafting_type(type)}"
            ] = Recipe(
                {
                    "type": f"minecraft:{self.type_to_crafting_type(type)}",
                    "ingredient": {"item": self.item.base_item},
                    "result": {
                        "id": self.item.base_item,
                    },
                }
            )


@dataclass
class SimpledrawerMaterial:
    block: Item | VanillaItem
    ingot: Item | VanillaItem
    nugget: Item | VanillaItem | None

    material_id: str 
    material_name: str

    ingot_in_block: int = 9
    nugget_in_ingot: int = 9

    def generate_test(self, nbt: Compound, type: str):
        match type:
            case "block":
                type_id = 0
            case "ingot":
                type_id = 1
            case "nugget":
                type_id = 2
            case _:
                raise ValueError(f"Invalid type {type}")
        
        return f"""
execute
    unless score #success_material simpledrawer.io matches 1
    if data storage simpledrawer:io item_material{serialize_tag(nbt)}
    run function ~/{self.material_id}/{type}:
        scoreboard players set #type simpledrawer.io {type_id}
        function ~/..
"""

    def export(self, ctx: Context):
        """
        This function export the simple drawer materials to the ctx variable.
        """
        simpledrawer_tag = "simpledrawer:material"
        function_tag_impl = f"{NAMESPACE}:simpledrawer/material"
        function_path = f"{NAMESPACE}:impl/simpledrawer/material"
        function_path_calls = f"{NAMESPACE}:impl/calls/simpledrawer/material"
        if simpledrawer_tag not in ctx.data.function_tags:
            ctx.data.function_tags[simpledrawer_tag] = FunctionTag()
        if not function_path in ctx.data.functions:
            ctx.data.functions[function_path] = Function("# @public\n\n")
            ctx.data.function_tags[simpledrawer_tag].data["values"].append(f"#{function_tag_impl}")
        if not function_tag_impl in ctx.data.function_tags:
            ctx.data.function_tags[function_tag_impl] = FunctionTag()
            ctx.data.function_tags[function_tag_impl].data["values"].append(function_path_calls)
        
        block_nbt = self.block.to_nbt(0)
        del block_nbt["Slot"]
        ingot_nbt = self.ingot.to_nbt(0)
        del ingot_nbt["Slot"]
        nugget_nbt = self.nugget.to_nbt(0) if self.nugget is not None else None
        if nugget_nbt is not None:
            del nugget_nbt["Slot"]

        block_command = self.generate_test(block_nbt, "block")
        ingot_command = self.generate_test(ingot_nbt, "ingot")
        nugget_command = self.generate_test(nugget_nbt, "nugget") if nugget_nbt is not None else ""

        if self.nugget is not None:
            nugget_nbt_command = f"""
    execute
        summon item_display 
        run function ~/get_nugget_nbt:
            {self.nugget.result_command(1, "entity", 0)}
            data modify storage simpledrawer:io material.nugget.item set from entity @s item
            kill @s
"""
        else:
            nugget_nbt_command = ""

        commands = f"""
{block_command}
{ingot_command}
{nugget_command}

function ~/{self.material_id}:
    scoreboard players set #success_material simpledrawer.io 1

    scoreboard players set #ingot_in_block simpledrawer.io {self.ingot_in_block}
    scoreboard players set #nugget_in_ingot simpledrawer.io {self.nugget_in_ingot}

    data modify storage simpledrawer:io material.material set value {self.material_id}
    data modify storage simpledrawer:io material.material_name set value {self.material_name}

    execute 
        summon item_display 
        run function ~/get_block_nbt:
            {self.block.result_command(1, "entity", 0)}
            data modify storage simpledrawer:io material.block.item set from entity @s item
            kill @s
    execute
        summon item_display 
        run function ~/get_ingot_nbt:
            {self.ingot.result_command(1, "entity", 0)}
            data modify storage simpledrawer:io material.ingot.item set from entity @s item
            kill @s
{nugget_nbt_command}
    

"""

        ctx.data.functions[function_path].append(commands)
        

