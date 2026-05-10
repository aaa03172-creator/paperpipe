
import json
from pathlib import Path

def inspect():
    path = Path("storage/zotero_export.json")
    with open(path) as f:
        data = json.load(f)
        items = data.get("items", [])
        
    print(f"Total items: {len(items)}")
    
    # 1. Check a known item
    target_key = "arnstenNeuromodulationThoughtFlexibilities2012"
    
    parent_map = {} # itemKey -> item
    
    for item in items:
        # Map itemKey if available
        if "itemKey" in item:
            parent_map[item["itemKey"]] = item
        elif "key" in item:
            parent_map[item["key"]] = item
            
    # Find the target
    target_item = None
    for item in items:
        if item.get("citationKey") == target_key:
            target_item = item
            break
            
    if target_item:
        print(f"\n--- Target Item ({target_key}) ---")
        print(json.dumps(target_item, indent=2))
        
        # Check if it has a path directly
        if "path" in target_item:
            print(f"\n[DIRECT PATH FOUND]: {target_item['path']}")
            
        # Check if there are attachments linking to it
        # The key of target is?
        t_key = target_item.get("itemKey") or target_item.get("key")
        print(f"\nTarget Key: {t_key}")
        
        if t_key:
            # Search for children
            print("\n--- Searching for children (attachments) ---")
            for item in items:
                # Some formats use 'parentItem', others might nest
                # Check known possibilities
                p_key = item.get("parentItem")
                if p_key == t_key:
                    print(f"Child found! Type: {item.get('itemType')}")
                    print(json.dumps(item, indent=2))
    else:
        print("Target not found.")

if __name__ == "__main__":
    inspect()
