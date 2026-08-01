import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    KeywordIndexParams,
    KeywordIndexType,
    PayloadSchemaType,
    PointStruct,
)
from app.core.config import get_settings

def migrate():
    settings = get_settings()
    client = QdrantClient(
        url=settings.qdrant_url.rstrip("/"),
        api_key=settings.qdrant_api_key or None,
        check_compatibility=False,
    )
    
    alias_name = settings.qdrant_collection  # default: segments
    print(f"Target collection/alias: {alias_name}")
    
    # 1. Determine if target is a real collection, an alias, or doesn't exist
    collections_response = client.get_collections()
    existing_collections = [c.name for c in collections_response.collections]
    
    is_real_collection = False
    is_alias = False
    old_collection_name = None
    
    # Check aliases
    aliases_response = client.get_aliases()
    for alias in aliases_response.aliases:
        if alias.alias_name == alias_name:
            is_alias = True
            old_collection_name = alias.collection_name
            break
            
    if not is_alias and alias_name in existing_collections:
        is_real_collection = True
        old_collection_name = alias_name
        
    print(f"Is Alias: {is_alias}, Is Real Collection: {is_real_collection}, Old Collection: {old_collection_name}")
    
    if old_collection_name is None:
        print("No existing collection/alias found. Running standard VectorStore initialization.")
        from app.services.vector_store import VectorStore
        vs = VectorStore(settings)
        vs.ensure_collection()
        print("Done.")
        return
        
    # 2. Create the new collection with new settings
    new_collection_name = f"{alias_name}_v2"
    # Ensure new name doesn't conflict with any existing collection
    if new_collection_name in existing_collections:
        new_collection_name = f"{alias_name}_v2_{int(time.time())}"
        
    print(f"Creating new collection: {new_collection_name}")
    client.create_collection(
        collection_name=new_collection_name,
        vectors_config={
            "text_vector": VectorParams(
                size=settings.embedding_dimensions,
                distance=Distance.COSINE,
            )
        },
        sparse_vectors_config={
            "sparse_vector": SparseVectorParams(
                index=SparseIndexParams(
                    on_disk=True,
                )
            )
        },
        quantization_config=ScalarQuantization(
            scalar=ScalarQuantizationConfig(
                type=ScalarType.INT8,
                always_ram=True,
            )
        ),
    )
    
    # Create indexes on the new collection
    for field_name in ("file_id", "modality", "project_id", "conversation_id"):
        schema = PayloadSchemaType.KEYWORD
        if field_name == "project_id":
            schema = KeywordIndexParams(
                type=KeywordIndexType.KEYWORD,
                is_tenant=True,
            )
        client.create_payload_index(
            collection_name=new_collection_name,
            field_name=field_name,
            field_schema=schema,
        )
        
    # 3. Copy points from old_collection_name to new_collection_name
    print(f"Copying points from {old_collection_name} to {new_collection_name}...")
    offset = None
    copied_count = 0
    
    while True:
        res, next_offset = client.scroll(
            collection_name=old_collection_name,
            limit=100,
            with_payload=True,
            with_vectors=True,
            offset=offset,
        )
        
        if not res:
            break
            
        points = []
        for p in res:
            # Reconstruct vector dictionary correctly
            vectors = {}
            if isinstance(p.vector, dict):
                vectors = p.vector
            else:
                # If vector was not a dictionary, map it to the default text_vector
                vectors["text_vector"] = p.vector
                
            points.append(
                PointStruct(
                    id=p.id,
                    vector=vectors,
                    payload=p.payload,
                )
            )
            
        client.upsert(collection_name=new_collection_name, points=points)
        copied_count += len(points)
        print(f"Copied {copied_count} points...")
        
        offset = next_offset
        if next_offset is None:
            break
            
    print(f"Finished copying {copied_count} points.")
    
    # 4. Atomic alias swap
    from qdrant_client import models
    
    if is_alias:
        print(f"Swapping alias '{alias_name}' to point from '{old_collection_name}' to '{new_collection_name}'")
        client.update_aliases(
            change_actions=[
                models.DeleteAliasAction(
                    delete_alias=models.DeleteAlias(alias_name=alias_name)
                ),
                models.CreateAliasAction(
                    create_alias=models.CreateAlias(
                        collection_name=new_collection_name,
                        alias_name=alias_name,
                    )
                ),
            ]
        )
        print(f"Deleting old collection {old_collection_name}...")
        client.delete_collection(old_collection_name)
    else:
        # If it was a real collection, we delete the real collection, and create the alias
        print(f"Deleting old real collection '{old_collection_name}'...")
        client.delete_collection(old_collection_name)
        print(f"Creating alias '{alias_name}' pointing to '{new_collection_name}'")
        client.update_aliases(
            change_actions=[
                models.CreateAliasAction(
                    create_alias=models.CreateAlias(
                        collection_name=new_collection_name,
                        alias_name=alias_name,
                    )
                )
            ]
        )
        
    print("Migration completed successfully!")

if __name__ == "__main__":
    migrate()
