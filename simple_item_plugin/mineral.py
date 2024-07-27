from beet import Context, Texture, ResourcePack
from dataclasses import dataclass, field

from typing import Any, Literal, get_args, Optional
from typing_extensions import TypedDict, NotRequired
from simple_item_plugin.utils import export_translated_string
from simple_item_plugin.types import Lang, TranslatedString, NAMESPACE
from simple_item_plugin.item import Item, BlockProperties, MergeOverridesPolicy
from simple_item_plugin.crafting import ShapedRecipe, ShapelessRecipe, NBTSmelting, VanillaItem, SimpledrawerMaterial

from PIL import Image
from pydantic import BaseModel

from enum import Enum
import json
import pathlib
import random

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

    @property
    def merge_overrides_policy(self) -> dict[str, MergeOverridesPolicy]:
        return {}


class SubItemBlock(SubItem):
    block_properties: BlockProperties = field(
        default_factory=lambda: BlockProperties(base_block="minecraft:lodestone")
    )

    def get_base_item(self):
        return "minecraft:lodestone"


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
                "type": "minecraft:generic.armor",
                "amount": self.armor,
                "operation": "add_value",
                "slot": "armor",
                "id": f"{NAMESPACE}:armor_{self.translation[0]}",
            },
            {
                "type": "minecraft:generic.armor_toughness",
                "amount": self.armor_toughness,
                "operation": "add_value",
                "slot": "armor",
                "id": f"{NAMESPACE}:armor_toughness_{self.translation[0]}",
            },
        ])
        color = self.mineral.get_fancyPants_color(ctx)
        rgb = 256*256*color[0] + 256*color[1] + color[2]
        res["minecraft:dyed_color"] = {
            "rgb": rgb,
            "show_in_tooltip": False,
        }
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

    @property
    def merge_overrides_policy(self) -> dict[str, MergeOverridesPolicy]:
        return {
            "layer0": MergeOverridesPolicy.clear,
            "layer1": MergeOverridesPolicy.use_model_path,
            "layer2": MergeOverridesPolicy.use_vanilla,
        }

class SubItemWeapon(SubItemDamagable):
    attack_damage: float
    attack_speed: float

    def get_components(self, ctx: Context):
        res = super().get_components(ctx)
        res.setdefault("minecraft:attribute_modifiers", {}).setdefault("modifiers", [])
        res["minecraft:attribute_modifiers"]["modifiers"].extend([
            {
                "type": "minecraft:generic.attack_damage",
                "amount": self.attack_damage,
                "operation": "add_value",
                "slot": "hand",
                "id": f"{NAMESPACE}:attack_damage_{self.translation[0]}",
            },
            {
                "type": "minecraft:generic.attack_speed",
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
@dataclass
class Mineral:
    id: str
    name: TranslatedString

    overrides: dict[AllItemTypes, dict[str, Any]] = field(default_factory=lambda: {})

    armor_additional_attributes: dict[str, AttributeModifier] = field(default_factory=lambda: {})

    def export(self, ctx: Context):
        export_translated_string(ctx, self.name)
        self.export_armor(ctx)
        self.export_subitem(ctx)
    
    def get_fancyPants_color(self, ctx: Context):
        armor_color_cache = ctx.meta["simple_item_plugin"]["stable_cache"].setdefault("armor_color", {})
        if not self.id in armor_color_cache:
            armor_color_cache[self.id] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        return armor_color_cache[self.id]

    @staticmethod
    def merge_layer(original: Image.Image, new: Image.Image) -> Image.Image:
        new_size = (original.width+new.width, max(original.height, new.height))
        new_image = Image.new("RGBA", new_size)
        new_image.paste(original, (0, 0))
        new_image.paste(new, (original.width, 0))
        return new_image

    def export_armor(self, ctx: Context):
        if not any(item in ArmorTypeList for item in self.overrides):
            return
        color = self.get_fancyPants_color(ctx)
        layer_1_path = f"{NAMESPACE}:models/armor/{self.id}_layer_1"
        layer_2_path = f"{NAMESPACE}:models/armor/{self.id}_layer_2"
        clear_path = f"{NAMESPACE}:models/armor/clear"

        assert layer_1_path in ctx.assets.textures
        assert layer_2_path in ctx.assets.textures
        if clear_path not in ctx.assets.textures:
            ctx.assets.textures[clear_path] = Texture(Image.new("RGBA", (64, 32), (0, 0, 0, 0)))

        layer_1 : Image.Image = ctx.assets.textures[layer_1_path].image
        layer_2 : Image.Image = ctx.assets.textures[layer_2_path].image
        layer_1 = layer_1.copy().convert("RGBA")
        layer_2 = layer_2.copy().convert("RGBA")

        layer_1.putpixel((0, 0), (*color, 255))
        layer_2.putpixel((0, 0), (*color, 255))

        minecraft_layer_1_path = "minecraft:models/armor/leather_layer_1"
        minecraft_layer_2_path = "minecraft:models/armor/leather_layer_2"

        fancyPants_layer_1_path = pathlib.Path(__file__).parent / "assets" / "fancyPants" / "leather_layer_1.png"
        fancyPants_layer_2_path = pathlib.Path(__file__).parent / "assets" / "fancyPants" / "leather_layer_2.png"
        fancyPants_layer_1 = Image.open(fancyPants_layer_1_path).convert("RGBA")
        fancyPants_layer_2 = Image.open(fancyPants_layer_2_path).convert("RGBA")


        new_layer_1 = self.merge_layer(fancyPants_layer_1, layer_1)
        new_layer_2 = self.merge_layer(fancyPants_layer_2, layer_2)
        
        rp = ResourcePack()
        rp.textures[minecraft_layer_1_path] = Texture(new_layer_1)
        rp.textures[minecraft_layer_2_path] = Texture(new_layer_2)
        ctx.assets.merge(rp)        



    def export_subitem(self, ctx: Context):
        for item, item_args in self.overrides.items():
            item_args["translation"] = get_default_translated_string(item)
            item_args["type"] = item
            item_args["mineral"] = self
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
            Item(
                id=f"{self.id}_{item}",
                item_name=subitem.get_item_name(self.name),
                components_extra=subitem.get_components(ctx),
                base_item=subitem.get_base_item(),
                block_properties=subitem.block_properties,
                is_cookable=subitem.is_cookable,
                is_armor=isinstance(subitem, SubItemArmor),
                merge_overrides_policy=subitem.merge_overrides_policy,
                ).export(ctx)
        self.generate_crafting_recipes(ctx)
        return self

    def get_item(self, ctx: Context, id: str) -> Item:
        item = Item.get_from_id(ctx, f"{self.id}_{id}")
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
