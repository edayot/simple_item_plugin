from beet import Context, Texture, ResourcePack, Model
from dataclasses import dataclass, field

from typing import Any, Literal, get_args, Optional
from typing_extensions import TypedDict, NotRequired
from simple_item_plugin.utils import export_translated_string, Registry
from simple_item_plugin.types import Lang, TranslatedString, NAMESPACE
from simple_item_plugin.item import Item, BlockProperties, ItemGroup
from simple_item_plugin.crafting import ShapedRecipe, ShapelessRecipe, NBTSmelting, VanillaItem, SimpledrawerMaterial

from PIL import Image
from pydantic import BaseModel

from enum import Enum
import json
import pathlib
import random
import logging

logger = logging.getLogger("simple_item_plugin")


Mineral_list: list["Mineral"] = []
ToolType = Literal["pickaxe", "axe", "shovel", "hoe", "sword"]
ArmorType = Literal["helmet", "chestplate", "leggings", "boots"]
BlockType = Literal["ore", "deepslate_ore", "raw_ore_block", "block"]
ItemType = Literal["raw_ore", "ingot", "nugget", "dust"]
ToolTypeList = set(get_args(ToolType))
ArmorTypeList = set(get_args(ArmorType))
BlockTypeList = set(get_args(BlockType))
ItemTypeList = set(get_args(ItemType))


AllItemTypes = ToolType | ArmorType | BlockType | ItemType
AllItemTypesList = set([*ToolTypeList, *ArmorTypeList, *BlockTypeList, *ItemTypeList])

TierType = Literal["wooden", "stone", "iron", "golden", "diamond", "netherite"]


class AttributeModifier(TypedDict):
    amount: float
    operation: NotRequired[str]
    slot: str

class TypingSubItem(TypedDict):
    type: AllItemTypes
    translation: TranslatedString
    is_cookable: NotRequired[bool]
    additional_attributes: NotRequired[dict[str, AttributeModifier]]


class TypingDamagable(TypingSubItem):
    max_damage: NotRequired[int]

class TypingToolArgs(TypingDamagable):
    type: ToolType
    attack_damage: NotRequired[float]
    attack_speed: NotRequired[float]
    speed: NotRequired[float]
    tier: NotRequired[TierType]

class TypingArmorArgs(TypingDamagable):
    armor: NotRequired[float]
    armor_toughness: NotRequired[float]
    type: ArmorType

class TypingSubItemBlock(TypingSubItem):
    block_properties: BlockProperties



class SubItem(BaseModel):
    type: AllItemTypes
    translation: TranslatedString
    block_properties: BlockProperties | None = None
    is_cookable: bool = False
    mineral : "Mineral"

    additional_attributes: dict[str, AttributeModifier] = field(default_factory=lambda: {})

    def get_item_name(self, translation: TranslatedString):
        return {
            "translate": self.translation[0],
            "with": [{"translate": translation[0]}],
            "color": "white",
            "fallback": self.translation[1][Lang.en_us].replace("%s", translation[1][Lang.en_us])
        }

    def get_components(self, ctx: Context) -> dict[str, Any]:
        return {
            "minecraft:attribute_modifiers": {
                "modifiers": [
                    {
                        "type": key,
                        "amount": value["amount"],
                        "operation": value["operation"] if "operation" in value else "add_value",
                        "slot": value["slot"],
                        "id": f"{key.split('.')[-1]}_{NAMESPACE}_{self.translation[0]}",
                    }
                    for key, value in self.additional_attributes.items()
                ],
                "show_in_tooltip": False
            }
        }

    def get_base_item(self):
        return "minecraft:jigsaw"

    def export(self, ctx: Context):
        export_translated_string(ctx, self.translation)

    def get_guide_description(self, ctx: Context) -> Optional[TranslatedString]:
        return None
    
    def get_id(self):
        return f"{self.mineral.id}_{self.type}"



class SubItemBlock(SubItem):
    block_properties: BlockProperties = field(
        default_factory=lambda: BlockProperties(base_block="minecraft:lodestone")
    )

    def get_base_item(self):
        return "minecraft:furnace"
    
    def get_guide_description(self, ctx: Context) -> Optional[TranslatedString]:
        if not self.block_properties.world_generation:
            return None
        
        translated_string = (
            f"{NAMESPACE}.guide_description.world_generation.{self.get_id()}", {
                Lang.en_us: f""" \
This block can be found :
{"\n".join(["- " + where.to_human_string(Lang.en_us).capitalize() for where in self.block_properties.world_generation])}
""",
                Lang.fr_fr: f""" \
Ce bloc peut être trouvé :
{"\n".join(["- " + where.to_human_string(Lang.fr_fr).capitalize() for where in self.block_properties.world_generation])}
""",
            }
        )
        return translated_string


class SubItemDamagable(SubItem):
    max_damage: int

    def get_components(self, ctx: Context):
        res = super().get_components(ctx)
        res.update({
            "minecraft:max_stack_size": 1,
            "minecraft:max_damage": self.max_damage,
        })
        return res
    

class SubItemArmor(SubItemDamagable):
    type: ArmorType
    armor: float
    armor_toughness: float

    def get_components(self, ctx: Context):
        res = super().get_components(ctx)
        res.setdefault("minecraft:attribute_modifiers", {}).setdefault("modifiers", [])
        res["minecraft:attribute_modifiers"]["modifiers"].extend([
            {
                "type": "minecraft:armor",
                "amount": self.armor,
                "operation": "add_value",
                "slot": "armor",
                "id": f"{NAMESPACE}:armor_{self.translation[0]}",
            },
            {
                "type": "minecraft:armor_toughness",
                "amount": self.armor_toughness,
                "operation": "add_value",
                "slot": "armor",
                "id": f"{NAMESPACE}:armor_toughness_{self.translation[0]}",
            },
        ])
        res["minecraft:equippable"] = {
            "slot": {
                "helmet": "head",
                "chestplate": "chest",
                "leggings": "legs",
                "boots": "feet",
            }.get(self.type),
            "model": f"{NAMESPACE}:{self.mineral.id}"
        }
    
        return res
    
    def get_base_item(self):
        return f"minecraft:jigsaw"

class SubItemWeapon(SubItemDamagable):
    attack_damage: float
    attack_speed: float

    def get_components(self, ctx: Context):
        res = super().get_components(ctx)
        res.setdefault("minecraft:attribute_modifiers", {}).setdefault("modifiers", [])
        res["minecraft:attribute_modifiers"]["modifiers"].extend([
            {
                "type": "minecraft:attack_damage",
                "amount": self.attack_damage,
                "operation": "add_value",
                "slot": "hand",
                "id": f"{NAMESPACE}:attack_damage_{self.translation[0]}",
            },
            {
                "type": "minecraft:attack_speed",
                "amount": self.attack_speed-4,
                "operation": "add_value",
                "slot": "hand",
                "id": f"{NAMESPACE}:attack_speed_{self.translation[0]}",
            },
        ])
        return res


class SubItemTool(SubItemWeapon):
    type: ToolType
    tier: TierType
    speed: float = 2.0

    def get_components(self, ctx: Context):
        res = super().get_components(ctx)
        if not self.type == "sword":
            res.update(
                {
                    "minecraft:tool": {
                        "rules": [
                            {
                                "blocks": f"#minecraft:incorrect_for_{self.tier}_tool",
                                "correct_for_drops": False,
                            },
                            {
                                "blocks": f"#minecraft:mineable/{self.type}",
                                "correct_for_drops": True,
                                "speed": self.speed,
                            },
                        ],
                        "damage_per_block": 1,
                    }
                }
            )
        else:
            res.update(
                {
                    "minecraft:tool": {
                        "rules": [
                            {
                                "blocks": "minecraft:cobweb",
                                "correct_for_drops": True,
                                "speed": 15.0
                            },
                            {
                                "blocks": "#minecraft:sword_efficient",
                                "speed": 1.5
                            }
                        ],
                        "damage_per_block": 2,
                    }
                }
            )
        return res

    def get_base_item(self):
        return f"minecraft:{self.tier}_{self.type}"



def get_default_translated_string(name: AllItemTypes):
    match name:
        case "ore":
            return (f"{NAMESPACE}.mineral_name.ore", {Lang.en_us: "%s Ore", Lang.fr_fr: "Minerai de %s"})
        case "deepslate_ore":
            return (f"{NAMESPACE}.mineral_name.deepslate_ore", {Lang.en_us: "Deepslate %s Ore", Lang.fr_fr: "Minerai de deepslate de %s"})
        case "raw_ore_block":
            return (f"{NAMESPACE}.mineral_name.raw_block", {Lang.en_us: "Raw %s Block", Lang.fr_fr: "Bloc brut de %s"})
        case "block":
            return (f"{NAMESPACE}.mineral_name.block", {Lang.en_us: "%s Block", Lang.fr_fr: "Bloc de %s"})
        case "raw_ore":
            return (f"{NAMESPACE}.mineral_name.raw_ore", {Lang.en_us: "Raw %s Ore", Lang.fr_fr: "Minerai brut de %s"})
        case "ingot":
            return (f"{NAMESPACE}.mineral_name.ingot", {Lang.en_us: "%s Ingot", Lang.fr_fr: "Lingot de %s"})
        case "nugget":
            return (f"{NAMESPACE}.mineral_name.nugget", {Lang.en_us: "%s Nugget", Lang.fr_fr: "Pépite de %s"})
        case "dust":
            return (f"{NAMESPACE}.mineral_name.dust", {Lang.en_us: "%s Dust", Lang.fr_fr: "Poudre de %s"})
        case "pickaxe":
            return (f"{NAMESPACE}.mineral_name.pickaxe", {Lang.en_us: "%s Pickaxe", Lang.fr_fr: "Pioche en %s"})
        case "axe":
            return (f"{NAMESPACE}.mineral_name.axe", {Lang.en_us: "%s Axe", Lang.fr_fr: "Hache en %s"})
        case "shovel":
            return (f"{NAMESPACE}.mineral_name.shovel", {Lang.en_us: "%s Shovel", Lang.fr_fr: "Pelle en %s"})
        case "hoe":
            return (f"{NAMESPACE}.mineral_name.hoe", {Lang.en_us: "%s Hoe", Lang.fr_fr: "Houe en %s"})
        case "sword":
            return (f"{NAMESPACE}.mineral_name.sword", {Lang.en_us: "%s Sword", Lang.fr_fr: "Épée en %s"})
        case "helmet":
            return (f"{NAMESPACE}.mineral_name.helmet", {Lang.en_us: "%s Helmet", Lang.fr_fr: "Casque en %s"})
        case "chestplate":
            return (f"{NAMESPACE}.mineral_name.chestplate", {Lang.en_us: "%s Chestplate", Lang.fr_fr: "Plastron en %s"})
        case "leggings":
            return (f"{NAMESPACE}.mineral_name.leggings", {Lang.en_us: "%s Leggings", Lang.fr_fr: "Jambières en %s"})
        case "boots":
            return (f"{NAMESPACE}.mineral_name.boots", {Lang.en_us: "%s Boots", Lang.fr_fr: "Bottes en %s"})
        case _:
            raise ValueError("Invalid item type")
class Mineral(Registry):
    id: str
    name: TranslatedString

    overrides: dict[AllItemTypes, dict[str, Any]] = field(default_factory=lambda: {})

    armor_additional_attributes: dict[str, AttributeModifier] = field(default_factory=lambda: {})

    item_group : Optional[ItemGroup] = None

    def export(self, ctx: Context):
        export_translated_string(ctx, self.name)
        self.export_armor(ctx)
        self.export_subitem(ctx)
    

    def export_armor(self, ctx: Context):
        if not any(item in ArmorTypeList for item in self.overrides):
            return
        ctx.assets.models[f"{NAMESPACE}:equipment/{self.id}"] = Model({
            "layers": {
                "humanoid": [
                    {
                        "texture": f"{NAMESPACE}:{self.id}"
                    },
                    
                ],
                "humanoid_leggings": [
                    {
                        "texture": f"{NAMESPACE}:{self.id}"
                    }
                ],
            }
        })
        real_texture_path = f"{NAMESPACE}:entity/equipment/humanoid/{self.id}"
        if not real_texture_path in ctx.assets.textures:
            logger.warning(f"Texture {real_texture_path} not found")
        real_texture_path_leggings = f"{NAMESPACE}:entity/equipment/humanoid_leggings/{self.id}"
        if not real_texture_path_leggings in ctx.assets.textures:
            logger.warning(f"Texture {real_texture_path_leggings} not found")
        



    def export_subitem(self, ctx: Context):
        self.item_group = ItemGroup(
            id=f"{self.id}_group",
            name=self.name,
        )
        for item, item_args in self.overrides.items():
            item_args["translation"] = get_default_translated_string(item)
            item_args["type"] = item
            item_args["mineral"] = self
            is_cookable = False
            if item in ["raw_ore", "ore", "deepslate_ore", "dust"]:
                is_cookable = True
            if "is_cookable" in item_args:
                is_cookable = item_args["is_cookable"]
                del item_args["is_cookable"]
            
            if item in ToolTypeList:
                subitem = SubItemTool(**item_args)
            elif item in ArmorTypeList:
                item_args["additional_attributes"] = self.armor_additional_attributes
                subitem = SubItemArmor(**item_args)
            elif item in BlockTypeList:
                subitem = SubItemBlock(**item_args)
            elif item in ItemTypeList:
                subitem = SubItem(**item_args)
            else:
                raise ValueError("Invalid item type")
            subitem.export(ctx)
            new_item = Item(
                id=f"{self.id}_{item}",
                item_name=subitem.get_item_name(self.name),
                components_extra=subitem.get_components(ctx),
                base_item=subitem.get_base_item(),
                block_properties=subitem.block_properties,
                is_cookable=is_cookable,
                is_armor=isinstance(subitem, SubItemArmor),
                guide_description=subitem.get_guide_description(ctx),
                ).export(ctx)
            self.item_group.add_item(ctx, new_item)
        for item_part in ["ingot", "raw_ore", "raw_ore_block", "block"]:
            if item:=self.get_item(ctx, item_part):
                self.item_group.item_icon = item
                break
        if not self.item_group.item_icon:
            raise ValueError("No item icon found")
        self.item_group.export(ctx)
        self.generate_crafting_recipes(ctx)
        return self

    def get_item(self, ctx: Context, id: str) -> Item:
        item = Item.get(ctx, f"{self.id}_{id}")
        if item is None:
            raise ValueError(f"Item {id} not found")
        return item
    
    def generate_crafting_recipes(self, ctx: Context):
        block = self.get_item(ctx, "block")
        raw_ore_block = self.get_item(ctx, "raw_ore_block")
        ingot = self.get_item(ctx, "ingot")
        nugget = self.get_item(ctx, "nugget")
        raw_ore = self.get_item(ctx, "raw_ore")
        ore = self.get_item(ctx, "ore")
        deepslate_ore = self.get_item(ctx, "deepslate_ore")
        dust = self.get_item(ctx, "dust")

        SimpledrawerMaterial(
            block=block,
            ingot=ingot,
            nugget=nugget,
            material_id=f'{NAMESPACE}.{self.id}',
            material_name=f'{json.dumps({"translate": self.name[0]})}',
        ).export(ctx)

        if raw_ore_block and raw_ore and ore and deepslate_ore and dust:
            SimpledrawerMaterial(
                block=raw_ore_block,
                ingot=raw_ore,
                nugget=None,
                material_id=f'{NAMESPACE}.{self.id}_raw',
                material_name=f'{json.dumps({"translate": self.name[0]})}',
            ).export(ctx)

            ShapedRecipe(
                items=(
                    (raw_ore, raw_ore, raw_ore),
                    (raw_ore, raw_ore, raw_ore),
                    (raw_ore, raw_ore, raw_ore),
                ),
                result=(raw_ore_block, 1),
            ).export(ctx)

            ShapelessRecipe(
                items=[(raw_ore_block, 1)],
                result=(raw_ore, 9),
            ).export(ctx)

            NBTSmelting(
                item=raw_ore,
                result=(ingot, 2),
                types=["furnace", "blast_furnace"],
            ).export(ctx)

            NBTSmelting(
                item=ore,
                result=(ingot, 1),
                types=["furnace", "blast_furnace"],
            ).export(ctx)

            NBTSmelting(
                item=deepslate_ore,
                result=(ingot, 1),
                types=["furnace", "blast_furnace"],
            ).export(ctx)

        ShapedRecipe(
            items=(
                (ingot, ingot, ingot),
                (ingot, ingot, ingot),
                (ingot, ingot, ingot),
            ),
            result=(block, 1),
        ).export(ctx)

        ShapedRecipe(
            items=(
                (nugget, nugget, nugget),
                (nugget, nugget, nugget),
                (nugget, nugget, nugget),
            ),
            result=(ingot, 1),
        ).export(ctx)

        ShapelessRecipe(
            items=[(ingot, 1)],
            result=(nugget, 9),
        ).export(ctx)

        ShapelessRecipe(
            items=[(block, 1)],
            result=(ingot, 9),
        ).export(ctx)

        NBTSmelting(
            item=dust,
            result=(ingot, 1),
            types=["furnace", "blast_furnace"],
        ).export(ctx)

        stick = VanillaItem(id="minecraft:stick").export(ctx)
        stick = VanillaItem(id="minecraft:stick").export(ctx)

        if pickaxe := self.get_item(ctx, "pickaxe"):
            ShapedRecipe(
                items=(
                    (ingot, ingot, ingot),
                    (None, stick, None),
                    (None, stick, None),
                ),
                result=(pickaxe, 1),
            ).export(ctx)
        if axe := self.get_item(ctx, "axe"):
            ShapedRecipe(
                items=(
                    (ingot, ingot, None),
                    (ingot, stick, None),
                    (None, stick, None),
                ),
                result=(axe, 1),
            ).export(ctx)
        if shovel := self.get_item(ctx, "shovel"):
            ShapedRecipe(
                items=(
                    (ingot, None, None),
                    (stick, None, None),
                    (stick, None, None),
                ),
                result=(shovel, 1),
            ).export(ctx)
        if hoe := self.get_item(ctx, "hoe"):
            ShapedRecipe(
                items=(
                    (ingot, ingot, None),
                    (None, stick, None),
                    (None, stick, None),
                ),
                result=(hoe, 1),
            ).export(ctx)
        if sword := self.get_item(ctx, "sword"):
            ShapedRecipe(
                items=(
                    (ingot, None, None),
                    (ingot, None, None),
                    (stick, None, None),
                ),
                result=(sword, 1),
            ).export(ctx)
        if helmet := self.get_item(ctx, "helmet"):
            ShapedRecipe(
                items=(
                    (ingot, ingot, ingot),
                    (ingot, None, ingot),
                    (None, None, None),
                ),
                result=(helmet, 1),
            ).export(ctx)
        if chestplate := self.get_item(ctx, "chestplate"):
            ShapedRecipe(
                items=(
                    (ingot, None, ingot),
                    (ingot, ingot, ingot),
                    (ingot, ingot, ingot),
                ),
                result=(chestplate, 1),
            ).export(ctx)
        if leggings := self.get_item(ctx, "leggings"):
            ShapedRecipe(
                items=(
                    (ingot, ingot, ingot),
                    (ingot, None, ingot),
                    (ingot, None, ingot),
                ),
                result=(leggings, 1),
            ).export(ctx)
        if boots := self.get_item(ctx, "boots"):
            ShapedRecipe(
                items=(
                    (ingot, None, ingot),
                    (ingot, None, ingot),
                    (None, None, None),
                ),
                result=(boots, 1),
            ).export(ctx)
