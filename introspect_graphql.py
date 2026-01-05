#!/usr/bin/env python3
"""
Introspect GraphQL schema to find available entities
"""

import requests
import json

SUBGRAPH_URL = "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/orderbook-subgraph/0.0.1/gn"

# Introspection query to get all available types
introspection_query = """
{
  __schema {
    queryType {
      fields {
        name
        description
        type {
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

print("Available Query Fields in Activity Subgraph:")
print("=" * 80)

if "data" in data and "__schema" in data["data"]:
    fields = data["data"]["__schema"]["queryType"]["fields"]
    for field in fields:
        field_name = field["name"]
        field_type = field["type"]["name"] if field["type"]["name"] else field["type"]["kind"]
        description = field.get("description", "")
        print(f"\n{field_name}")
        print(f"  Type: {field_type}")
        if description:
            print(f"  Description: {description}")
else:
    print("Could not retrieve schema")
    print(json.dumps(data, indent=2))
