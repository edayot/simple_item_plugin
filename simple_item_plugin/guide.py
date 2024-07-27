from simple_item_plugin.item import Item
from simple_item_plugin.crafting import VanillaItem
from beet import Context, Texture, Font, ItemModifier, LootTable, Generator, configurable
from model_resolver import beet_default as model_resolver
from PIL import Image, ImageDraw, ImageFont
from simple_item_plugin.utils import NAMESPACE, Lang, SimpleItemPluginOptions
import json
import pathlib
from dataclasses import dataclass
from typing import Iterable

@dataclass
class GuideItem:
    item : Item | VanillaItem
    char_index : int = 0
    page_index : int = -1

    def __hash__(self):
        return hash(self.item)


def get_item_list(ctx: Context) -> dict[str, GuideItem]:
    items = dict()
    items["minecraft:air"] = GuideItem(VanillaItem("minecraft:air"))
    for recipe in ctx.meta["registry"].get("recipes", []):
        for row in recipe.items:
            for item in row:
                if item:
                    items[item.id] = GuideItem(item)
        items[recipe.result[0].id] = GuideItem(recipe.result[0])
    return items

def search_item(ctx: Context, item: GuideItem):
    for recipe in ctx.meta["registry"].get("recipes", []):
        if recipe.result[0].id == item.item.id:
            return recipe
    return None



CHAR_OFFSET = 0x4
def char_index_number():
    global CHAR_INDEX_NUMBER
    CHAR_INDEX_NUMBER += CHAR_OFFSET
    return CHAR_INDEX_NUMBER

@configurable("simple_item_plugin", validator=SimpleItemPluginOptions)
def guide(ctx: Context, opts: SimpleItemPluginOptions):
    global CHAR_INDEX_NUMBER, COUNT_TO_CHAR
    CHAR_INDEX_NUMBER = 0x0030
    COUNT_TO_CHAR = {}

    if not opts.generate_guide:
        return
    with ctx.generate.draft() as draft:
        draft.cache("guide", "guide")
        generate_guide(ctx, draft)
    
def generate_guide(ctx: Context, draft: Generator):
    air = VanillaItem("minecraft:air")
    # Render the registry
    all_items= get_item_list(ctx)
    ctx.meta["model_resolver"]["filter"] = [i.item.model_path for i in all_items.values()]
    ctx.require(model_resolver)
    for item in all_items.values():
        model_path = item.item.model_path
        path = f"{NAMESPACE}:render/{model_path.replace(':', '/')}"
        if not path in ctx.assets.textures:
            img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        else:
            img : Image.Image = ctx.assets.textures[path].image
        img = img.copy()
        img.putpixel((0,0),(137,137,137,255))
        img.putpixel((img.width-1,img.height-1),(137,137,137,255))
        draft.assets.textures[path] = Texture(img.copy())
    create_font(draft, all_items.values())
    pages = []
    page_index = 0
    for id, item in all_items.items():
        if not (craft := search_item(ctx, item)):
            continue
        item.page_index = page_index
        page_index += 1
        items_craft = [
            [
                all_items[i.id] if i else all_items["minecraft:air"]
                for i in row
            ]
            for row in craft.items
        ]
        if (n := len(items_craft)) < 3:
            for i in range(3-n):
                items_craft.append([all_items["minecraft:air"]]*3)
        item_result = all_items[craft.result[0].id]
        pages.append(generate_craft(
            items_craft,
            item_result,
            craft.result[1]
        ))
    create_guide(draft, pages)




def create_font(draft: Generator, items: Iterable[GuideItem]):
    global CHAR_INDEX_NUMBER
    font_path = f"{NAMESPACE}:pages"
    release = '_release'
    if False:
        release = ''
    draft.assets.fonts[font_path] = Font({
        "providers": [
        {
            "type": "reference",
            "id": "minecraft:include/space"
        },
        { "type": "bitmap", "file": f"{NAMESPACE}:item/font/none_2{release}.png",				"ascent": 7, "height": 8, "chars": ["\uef00"] },
        { "type": "bitmap", "file": f"{NAMESPACE}:item/font/none_3{release}.png",				"ascent": 7, "height": 8, "chars": ["\uef01"] },
        { "type": "bitmap", "file": f"{NAMESPACE}:item/font/none_4{release}.png",				"ascent": 7, "height": 8, "chars": ["\uef02"] },
        { "type": "bitmap", "file": f"{NAMESPACE}:item/font/none_5{release}.png",				"ascent": 7, "height": 8, "chars": ["\uef03"] },
        { "type": "bitmap", "file": f"{NAMESPACE}:item/font/template_craft.png",				"ascent": -3, "height": 68, "chars": ["\uef13"] },
        { "type": "bitmap", "file": f"{NAMESPACE}:item/font/template_result.png",				"ascent": -20, "height": 34, "chars": ["\uef14"] },

        { "type": "bitmap", "file": f"{NAMESPACE}:item/logo/github.png",				        "ascent": 7, "height": 25, "chars": ["\uee01"] },
        { "type": "bitmap", "file": f"{NAMESPACE}:item/logo/pmc.png",				            "ascent": 7, "height": 25, "chars": ["\uee02"] },
        { "type": "bitmap", "file": f"{NAMESPACE}:item/logo/smithed.png",				        "ascent": 7, "height": 25, "chars": ["\uee03"] },
        { "type": "bitmap", "file": f"{NAMESPACE}:item/logo/modrinth.png",				        "ascent": 7, "height": 25, "chars": ["\uee04"] },
        ],
    })
    for item in items:
        if not item.char_index:
            item.char_index = char_index_number()
        render = f"{NAMESPACE}:render/{item.item.model_path.replace(':','/')}"
        for i in range(3):
            char_item = f"\\u{item.char_index+i:04x}".encode().decode("unicode_escape")
            draft.assets.fonts[font_path].data["providers"].append(
                {
                    "type": "bitmap",
                    "file": f"{render}.png",
                    "ascent": {0: 8, 1: 7, 2: 6}.get(i),
                    "height": 16,
                    "chars": [char_item]
                }
            )
    for count in range(2,100):
        # Create the image
        img = image_count(count)
        img.putpixel((0,0),(137,137,137,255))
        img.putpixel((img.width-1,img.height-1),(137,137,137,255))
        tex_path = f"{NAMESPACE}:item/font/number/{count}"
        draft.assets.textures[tex_path] = Texture(img)
        char_count = CHAR_INDEX_NUMBER
        CHAR_INDEX_NUMBER += 1
        char_index = f"\\u{char_count:04x}".encode().decode("unicode_escape")
        draft.assets.fonts[font_path].data["providers"].append(
            {
                "type": "bitmap",
                "file": tex_path + ".png",
                "ascent": 10,
                "height": 24,
                "chars": [char_index]
            }
        )
        COUNT_TO_CHAR[count] = char_index

        




def get_item_json(item: GuideItem, font_path: str, char : str = "\uef01"):
    if item.item.minimal_representation.get("id") == "minecraft:air":
        return {
            "text":char,
            "font":font_path,
            "color":"white"
        }
    if item.page_index == -1:
        return {
            "text":char,
            "font":font_path,
            "color":"white",
            "hoverEvent":{"action":"show_item","contents": item.item.minimal_representation}
        }
    return {
        "text":char,
        "font":font_path,
        "color":"white",
        "hoverEvent":{"action":"show_item","contents": item.item.minimal_representation},
        "clickEvent":{"action":"change_page","value":f"{item.page_index}"}
    }

def generate_craft(craft: list[list[GuideItem]], result: GuideItem, count: int):
    # Create a font for the page
    font_path = f'{NAMESPACE}:pages'
    page : list[str | dict] = [""]
    page.append({
        "text":f"\n\uef13 \uef14\n",
        "font":font_path,
        "color":"white"
    })
    page.append("\n")
    for i in range(3):
        for e in range(2):
            page.append({"text":"\uef00\uef00","font":font_path,"color":"white"})
            for j in range(3):
                item = craft[i][j]
                char_item = f"\\u{item.char_index + i:04x}".encode().decode("unicode_escape")
                page.append(get_item_json(item, font_path, f'\uef03{char_item}\uef03' if e == 0 else "\uef01"))
            if (i == 0 and e == 1) or (i == 2 and e == 0):
                page.append({"text":"\uef00\uef00\uef00\uef00","font":font_path,"color":"white"})
                char_space = "\uef02\uef02"
                page.append(get_item_json(result, font_path, char_space))
            if i == 1 and e == 0:
                page.append({"text":"\uef00\uef00\uef00\uef00","font":font_path,"color":"white"})
                char_result = f"\\u{result.char_index:04x}".encode().decode("unicode_escape")
                char_space = "\uef00\uef00\uef03"
                page.append(get_item_json(result, font_path, f'{char_space}{char_result}{char_space}\uef00'))
            if i == 1 and e == 1:
                page.append({"text":"\uef00\uef00\uef00\uef00","font":font_path,"color":"white"})
                char_space = "\uef02\uef02"
                if count > 1:
                    char_count = COUNT_TO_CHAR[count]
                    char_space = f"\uef00\uef00\uef00{char_count}"
                page.append(get_item_json(result, font_path, char_space))
            page.append("\n")
    return json.dumps(page)


def image_count(count: int) -> Image.Image:
    """ Generate an image showing the result count
    Args:
        count (int): The count to show
    Returns:
        Image: The image with the count
    """
    # Create the image
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font_size = 24
    ttf_path = pathlib.Path(__file__).parent / "assets" / "minecraft_font.ttf"
    font = ImageFont.truetype(ttf_path, size = font_size)

    # Calculate text size and positions of the two texts
    text_width = draw.textlength(str(count), font = font)
    text_height = font_size + 6
    pos_1 = (45-text_width), (0)
    pos_2 = (pos_1[0]-2, pos_1[1]-2)
    
    # Draw the count
    draw.text(pos_1, str(count), (50, 50, 50), font = font)
    draw.text(pos_2, str(count), (255, 255, 255), font = font)
    return img



def create_guide(draft: Generator, pages: Iterable[str]):
    Item(
        id="guide",
        item_name=(
            f"{NAMESPACE}.item.guide",
            {Lang.en_us: "Guide", Lang.fr_fr: "Guide"},
        ),
        components_extra={
            "minecraft:written_book_content": {
                "title": "Guide",
                "author": "AirDox_",
                "pages": pages,
                "resolved": True
            },
            "minecraft:enchantment_glint_override": False,
        },
    ).export(draft)