#!/usr/bin/env python3
"""
Introspect specific type to see its fields
"""

import requests
import json

SUBGRAPH_URL = "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/orderbook-subgraph/0.0.1/gn"

# Get fields for OrdersMatchedEvent type
introspection_query = """
{
  __type(name: "OrdersMatchedEvent") {
    name
    fields {
      name
      type {
        name
        kind
        ofType {
          name
          kind
        }
      }
    }
  }
}
"""

response = requests.post(
    SUBGRAPH_URL,
    json={"query": introspection_query},
    headers={"Content-Type": "application/json"}
)

response.raise_for_status()
data = response.json()

print("OrdersMatchedEvent Fields:")
print("=" * 80)

if "data" in data and "__type" in data["data"]:
    type_info = data["data"]["__type"]
    print(f"\nType: {type_info['name']}\n")
    for field in type_info["fields"]:
        field_name = field["name"]
        type_info_inner = field["type"]
        type_name = type_info_inner.get("name") or type_info_inner.get("kind")
        if type_info_inner.get("ofType"):
            type_name = type_info_inner["ofType"].get("name") or type_info_inner["ofType"].get("kind")
        print(f"  {field_name}: {type_name}")
else:
    print("Could not retrieve type info")
    print(json.dumps(data, indent=2))
