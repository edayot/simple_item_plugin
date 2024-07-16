from simple_item_plugin.item import Registry
from beet import Context






def export(ctx: Context):
    """
    We need to export items in custom_model_data order
    """
    items = Registry.values()
    items = sorted(items, key=lambda x: x.custom_model_data)
    for item in items:
        item.export(ctx)

    
    