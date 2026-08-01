import hashlib
import json
import logging
from openai import OpenAI
from app.core.config import Settings
from app.services.openai_retry import call_with_retry

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Wraps OpenAI text-embedding-3-small with Redis caching and basic batching."""

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key.strip():
            raise RuntimeError("OPENAI_API_KEY is required for embedding generation.")
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.embedding_model
        self._batch_size = settings.embedding_batch_size
        self._settings = settings
        
        # Initialize Redis connection
        self._redis = None
        if settings.redis_url:
            try:
                from redis import Redis
                self._redis = Redis.from_url(settings.redis_url)
                self._redis.ping()
                logger.info("EmbeddingService Redis cache initialized.")
            except Exception as e:
                logger.warning("EmbeddingService Redis cache connection failed: %s", e)

    def embed_texts(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        if not texts:
            return []

        # Generate cache keys
        keys = []
        for t in texts:
            h = hashlib.sha256(t.encode("utf-8")).hexdigest()
            keys.append(f"emb:{self._model}:{h}")

        # Check Redis cache
        cached_results = [None] * len(texts)
        if self._redis:
            try:
                cached_results = self._redis.mget(keys)
            except Exception as e:
                logger.warning("Redis mget failed: %s", e)

        vectors = [None] * len(texts)
        uncached_indices = []
        uncached_texts = []

        for i, val in enumerate(cached_results):
            if val is not None:
                try:
                    vectors[i] = json.loads(val)
                except Exception:
                    uncached_indices.append(i)
                    uncached_texts.append(texts[i])
            else:
                uncached_indices.append(i)
                uncached_texts.append(texts[i])

        # Batch embed uncached texts
        if uncached_texts:
            uncached_vectors = self._embed_texts_raw(uncached_texts)
            
            # Save to Redis cache
            if self._redis:
                try:
                    ttl = 86400 if is_query else 604800
                    pipe = self._redis.pipeline()
                    for idx, vec in zip(uncached_indices, uncached_vectors):
                        pipe.setex(keys[idx], ttl, json.dumps(vec))
                    pipe.execute()
                except Exception as e:
                    logger.warning("Failed to cache embeddings in Redis: %s", e)

            # Merge back
            for idx, vec in zip(uncached_indices, uncached_vectors):
                vectors[idx] = vec

        return vectors

    def _embed_texts_raw(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            response = call_with_retry(
                lambda b=batch: self._client.embeddings.create(model=self._model, input=b),
                max_retries=self._settings.openai_max_retries,
                min_delay_seconds=self._settings.openai_retry_min_delay_seconds,
                label="embeddings",
            )
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend(item.embedding for item in ordered)
        return vectors
