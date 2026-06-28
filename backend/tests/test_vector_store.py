import pytest
import uuid
from datetime import UTC, datetime
from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector

from app.core.config import Settings
from app.services.vector_store import VectorStore, VectorSegment


@pytest.fixture
def in_memory_vector_store() -> VectorStore:
    settings = Settings(
        qdrant_url="http://localhost:6333",
        qdrant_collection="test_segments",
        embedding_dimensions=4,  # Use small dimension for fast testing
    )
    store = VectorStore(settings)
    # Directly override the client with an in-memory instance
    store._client = QdrantClient(":memory:")
    # Ensure collection is created in memory
    store.create_collection()
    return store


def test_vector_store_initialization(in_memory_vector_store: VectorStore):
    assert in_memory_vector_store.collection_exists()
    assert in_memory_vector_store.count_points() == 0


def test_upsert_and_retrieve_dense_only(in_memory_vector_store: VectorStore):
    segment_id = uuid.uuid4()
    file_id = uuid.uuid4()
    
    segment = VectorSegment(
        id=segment_id,
        vector=[0.1, 0.2, 0.3, 0.4],
        file_id=file_id,
        modality="text",
        content="This is a test document about artificial intelligence.",
        source_path="http://cloudinary.com/test",
        title="test_file.txt",
        created_at=datetime.now(UTC),
    )
    
    in_memory_vector_store.upsert_segments([segment])
    assert in_memory_vector_store.count_points() == 1
    
    # Retrieve using dense only
    hits = in_memory_vector_store.search(
        query_vector=[0.1, 0.2, 0.3, 0.4],
        top_k=1,
    )
    assert len(hits) == 1
    assert hits[0]["id"] == str(segment_id)
    assert hits[0]["payload"]["content"] == segment.content


def test_upsert_with_sparse_vector_generation(in_memory_vector_store: VectorStore):
    segment_id = uuid.uuid4()
    file_id = uuid.uuid4()
    
    segment = VectorSegment(
        id=segment_id,
        vector=[0.5, 0.5, 0.5, 0.5],
        file_id=file_id,
        modality="text",
        content="Deep learning and machine learning systems.",
        source_path="http://cloudinary.com/test2",
        title="deep_learning.txt",
        created_at=datetime.now(UTC),
    )
    
    # Should automatically trigger fastembed to generate sparse vector
    in_memory_vector_store.upsert_segments([segment])
    assert in_memory_vector_store.count_points() == 1
    
    # Verify the stored point has the sparse vector
    points = in_memory_vector_store._client.retrieve(
        collection_name=in_memory_vector_store._collection,
        ids=[str(segment_id)],
        with_vectors=True,
    )
    assert len(points) == 1
    vectors = points[0].vector
    assert "sparse_vector" in vectors
    assert len(vectors["sparse_vector"].indices) > 0
    assert len(vectors["sparse_vector"].values) > 0


def test_hybrid_search_rrf(in_memory_vector_store: VectorStore):
    segment_id = uuid.uuid4()
    file_id = uuid.uuid4()
    
    segment = VectorSegment(
        id=segment_id,
        vector=[0.1, 0.0, 0.0, 0.9],
        file_id=file_id,
        modality="text",
        content="Search index optimization with hybrid search.",
        source_path="http://cloudinary.com/test3",
        title="optimization.txt",
        created_at=datetime.now(UTC),
    )
    in_memory_vector_store.upsert_segments([segment])
    
    # Define query sparse vector manually for validation
    query_sparse = SparseVector(indices=[1, 2], values=[0.5, 0.8])
    
    hits = in_memory_vector_store.search(
        query_vector=[0.1, 0.0, 0.0, 0.9],
        top_k=5,
        query_sparse_vector=query_sparse,
    )
    
    assert len(hits) == 1
    assert hits[0]["id"] == str(segment_id)
