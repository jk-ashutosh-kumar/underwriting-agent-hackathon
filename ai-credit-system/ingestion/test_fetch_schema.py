from db import fetch_schema
import json
def test_fetch():
    doc_type = "bank_statement"

    schema = fetch_schema(doc_type)

    if schema:
        print("✅ Schema fetched successfully")
        print("Document type:", doc_type)

        print("\n--- Full Schema ---")
        print(json.dumps(schema, indent=2))   # 👈 THIS FIX

    else:
        print("❌ No schema found for:", doc_type)




if __name__ == "__main__":
    test_fetch()