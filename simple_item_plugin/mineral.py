from beet import Context
from dataclasses import dataclass, field

from typing import Any, Literal
from typing_extensions import TypedDict, NotRequired
from simple_item_plugin.utils import export_translated_string
from simple_item_plugin.types import Lang, TranslatedString, NAMESPACE
from simple_item_plugin.item import Item, BlockProperties
from simple_item_plugin.crafting import ShapedRecipe, ShapelessRecipe, NBTSmelting, VanillaItem, SimpledrawerMaterial

from pydantic import BaseModel

from enum import Enum
import json

Mineral_list: list["Mineral"] = []
ToolType = Literal["pickaxe", "axe", "shovel", "hoe", "sword"]
ArmorType = Literal["helmet", "chestplate", "leggings", "boots"]
BlockType = Literal["ore", "deepslate_ore", "raw_ore_block", "block"]
ItemType = Literal["raw_ore", "ingot", "nugget", "dust"]

TierType = Literal["wooden", "stone", "iron", "golden", "diamond", "netherite"]


class AttributeModifier(TypedDict):
    amount: float
    name: NotRequired[str]
    operation: NotRequired[str]
    slot: str

class TypingSubItem(TypedDict):
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
    translation: TranslatedString
    block_properties: BlockProperties | None = None
    is_cookable: bool = False

    additional_attributes: dict[str, AttributeModifier] = field(default_factory=lambda: {})

    def get_item_name(self, translation: TranslatedString):
        return {
            "translate": self.translation[0],
            "with": [{"translate": translation[0]}],
            "color": "white",
        }

    def get_components(self) -> dict[str, Any]:
        return {
            "minecraft:attribute_modifiers": {
                "modifiers": [
                    {
                        "type": key,
                        "amount": value["amount"],
                        "name": value["name"] if "name" in value else "No name",
                        "operation": value["operation"] if "operation" in value else "add_value",
                        "slot": value["slot"],
                        "id": f"{NAMESPACE}:{key.split('.')[-1]}_{self.translation[0]}",
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


class SubItemBlock(SubItem):
    block_properties: BlockProperties = field(
        default_factory=lambda: BlockProperties(base_block="minecraft:lodestone")
    )

    def get_base_item(self):
        return "minecraft:furnace"


class SubItemDamagable(SubItem):
    max_damage: int

    def get_components(self):
        res = super().get_components()
        res.update({
            "minecraft:max_stack_size": 1,
            "minecraft:max_damage": self.max_damage,
        })
        return res
    

class SubItemArmor(SubItemDamagable):
    type: ArmorType
    armor: float
    armor_toughness: float

    def get_components(self):
        res = super().get_components()
        res["minecraft:attribute_modifiers"]["modifiers"].extend([
            {
                "type": "minecraft:generic.armor",
                "amount": self.armor,
                "name": "Armor modifier",
                "operation": "add_value",
                "slot": "armor",
                "id": f"{NAMESPACE}:armor_{self.translation[0]}",
            },
            {
                "type": "minecraft:generic.armor_toughness",
                "amount": self.armor_toughness,
                "name": "Armor toughness modifier",
                "operation": "add_value",
                "slot": "armor",
                "id": f"{NAMESPACE}:armor_toughness_{self.translation[0]}",
            },
        ])
        return res
    
    def get_base_item(self):
        # get a leather armor item depending on the type
        match self.type:
            case "helmet":
                return "minecraft:leather_helmet"
            case "chestplate":
                return "minecraft:leather_chestplate"
            case "leggings":
                return "minecraft:leather_leggings"
            case "boots":
                return "minecraft:leather_boots"
            case _:
                raise ValueError("Invalid armor type")


class SubItemWeapon(SubItemDamagable):
    attack_damage: float
    attack_speed: float

    def get_components(self):
        res = super().get_components()
        res.update(
            {
                "minecraft:attribute_modifiers": {
                    "modifiers": [
                        {
                            "type": "minecraft:generic.attack_damage",
                            "amount": self.attack_damage,
                            "name": "Tool modifier",
                            "operation": "add_value",
                            "slot": "hand",
                            "id": f"{NAMESPACE}:attack_damage_{self.translation[0]}",
                        },
                        {
                            "type": "minecraft:generic.attack_speed",
                            "amount": self.attack_speed-4,
                            "name": "Tool modifier",
                            "operation": "add_value",
                            "slot": "hand",
                            "id": f"{NAMESPACE}:attack_speed_{self.translation[0]}",
                        },
                    ]
                }
            }
        )
        return res


class SubItemTool(SubItemWeapon):
    type: ToolType
    tier: TierType
    speed: float = 2.0

    def get_components(self):
        res = super().get_components()
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
        return res

    def get_base_item(self):
        return f"minecraft:{self.tier}_{self.type}"


@dataclass
class Mineral:
    id: str
    name: TranslatedString

    items: dict[ToolType | ArmorType | BlockType | ItemType, TypingToolArgs | TypingArmorArgs] = field(default_factory=lambda: {})

    def export(self, ctx: Context):
        export_translated_string(ctx, self.name)
        self.export_subitem(ctx)

    def export_subitem(self, ctx: Context):
        DEFAULT_MINERALS_BLOCK_ARGS: dict[str, TypingSubItemBlock] = {
            "ore": {
                "translation": (
                    f"{NAMESPACE}.mineral_name.ore",
                    {Lang.en_us: "%s Ore", Lang.fr_fr: "Minerai de %s"},
                ),
                "block_properties": BlockProperties(base_block="minecraft:lodestone")
            },
            "deepslate_ore": {
                "translation": (
                    f"{NAMESPACE}.mineral_name.deepslate_ore",
                    {Lang.en_us: "Deepslate %s Ore", Lang.fr_fr: "Minerai de deepslate de %s"},
                ),
                "block_properties": BlockProperties(base_block="minecraft:lodestone")
            },
            "raw_ore_block": {
                "translation": (
                    f"{NAMESPACE}.mineral_name.raw_block",
                    {Lang.en_us: "Raw %s Block", Lang.fr_fr: "Bloc brut de %s"},
                ),
                "block_properties": BlockProperties(base_block="minecraft:lodestone")
            },
            "block": {
                "translation": (
                    f"{NAMESPACE}.mineral_name.block",
                    {Lang.en_us: "%s Block", Lang.fr_fr: "Bloc de %s"},
                ),
                "block_properties": BlockProperties(base_block="minecraft:lodestone")
            },
        }

        DEFAULT_MINERALS_ITEM_ARGS: dict[str, TypingSubItem] = {
            "raw_ore": {
                "translation": (
                    f"{NAMESPACE}.mineral_name.raw_ore",
                    {Lang.en_us: "Raw %s Ore", Lang.fr_fr: "Minerai brut de %s"},
                ),
            },
            "ingot": {
                "translation": (
                    f"{NAMESPACE}.mineral_name.ingot",
                    {Lang.en_us: "%s Ingot", Lang.fr_fr: "Lingot de %s"},
                ),
            },
            "nugget": {
                "translation": (
                    f"{NAMESPACE}.mineral_name.nugget",
                    {Lang.en_us: "%s Nugget", Lang.fr_fr: "Pépite de %s"},
                ),
            },
            "dust": {
                "translation": (
                    f"{NAMESPACE}.mineral_name.dust",
                    {Lang.en_us: "%s Dust", Lang.fr_fr: "Poudre de %s"},
                ),
            },
        }

        DEFAULT_TOOLS_ARGS: dict[ToolType, TypingToolArgs] = {
            "pickaxe": {
                "translation": (
                    f"{NAMESPACE}.mineral_name.pickaxe",
                    {Lang.en_us: "%s Pickaxe", Lang.fr_fr: "Pioche en %s"},
                ),
                "type": "pickaxe",
            },
            "axe": {
                "translation": (
                    f"{NAMESPACE}.mineral_name.axe",
                    {Lang.en_us: "%s Axe", Lang.fr_fr: "Hache en %s"},
                ),
                "type": "axe",
            },
            "shovel": {
                "translation": (
                    f"{NAMESPACE}.mineral_name.shovel",
                    {Lang.en_us: "%s Shovel", Lang.fr_fr: "Pelle en %s"},
                ),
                "type": "shovel",
            },
            "hoe": {
                "translation": (
                    f"{NAMESPACE}.mineral_name.hoe",
                    {Lang.en_us: "%s Hoe", Lang.fr_fr: "Houe en %s"},
                ),
                "type": "hoe",
            },
            "sword": {
                "translation": (
                    f"{NAMESPACE}.mineral_name.sword",
                    {Lang.en_us: "%s Sword", Lang.fr_fr: "Épée en %s"},
                ),
                "type": "sword",
            },
        }


        DEFAULT_ARMOR_ARGS: dict[str, TypingArmorArgs] = {
            "helmet": {
                "translation": (
                    f"{NAMESPACE}.mineral_name.helmet",
                    {Lang.en_us: "%s Helmet", Lang.fr_fr: "Casque en %s"},
                ),
                "type": "helmet"
            },
            "chestplate": {
                "translation": (
                    f"{NAMESPACE}.mineral_name.chestplate",
                    {Lang.en_us: "%s Chestplate", Lang.fr_fr: "Plastron en %s"},
                ),
                "type": "chestplate"
            },
            "leggings": {
                "translation": (
                    f"{NAMESPACE}.mineral_name.leggings",
                    {Lang.en_us: "%s Leggings", Lang.fr_fr: "Jambières en %s"},
                ),
                "type": "leggings"
            },
            "boots": {
                "translation": (
                    f"{NAMESPACE}.mineral_name.boots",
                    {Lang.en_us: "%s Boots", Lang.fr_fr: "Bottes en %s"},
                ),
                "type": "boots"
            },
        }


        for item in self.items.keys():
            if not item in self.items:
                continue
            if item in DEFAULT_MINERALS_BLOCK_ARGS.keys():
                args = DEFAULT_MINERALS_BLOCK_ARGS[item]
                args.update(self.items[item]) # type: ignore
                subitem = SubItemBlock(**args)
            elif item in DEFAULT_MINERALS_ITEM_ARGS.keys():
                args = DEFAULT_MINERALS_ITEM_ARGS[item]
                args.update(self.items[item]) # type: ignore
                subitem = SubItem(**args)
            elif item in DEFAULT_TOOLS_ARGS.keys():
                args = DEFAULT_TOOLS_ARGS[item] # type: ignore
                args.update(self.items[item]) # type: ignore
                subitem = SubItemTool(**args) # type: ignore
            elif item in DEFAULT_ARMOR_ARGS.keys():
                args = DEFAULT_ARMOR_ARGS[item]
                args.update(self.items[item]) # type: ignore
                subitem = SubItemArmor(**args)
            else:
                args = self.items[item]
                subitem = SubItem(**args) # type: ignore
            subitem.export(ctx)
            Item(
                id=f"{self.id}_{item}",
                item_name=subitem.get_item_name(self.name),
                components_extra=subitem.get_components(),
                base_item=subitem.get_base_item(),
                block_properties=subitem.block_properties,
                is_cookable=subitem.is_cookable,
                is_armor=isinstance(subitem, SubItemArmor),
                ).export(ctx)

        self.generate_crafting_recipes(ctx)
        return self

    def get_item(self, ctx: Context, item: str):
        return ctx.meta.get("registry",{}).get("items",{}).get(f"{self.id}_{item}", None)

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
                result=(ingot, 1),
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
            result=(ingot, 2),
            types=["furnace", "blast_furnace"],
        ).export(ctx)

        stick = VanillaItem("minecraft:stick")
        stick = VanillaItem("minecraft:stick")

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
