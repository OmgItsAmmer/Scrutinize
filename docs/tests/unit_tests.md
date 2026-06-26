# Unit Tests

**Justification in Pipeline:**
This unit test suite is the foundation of the Scrutinize pipeline's reliability. It ensures that individual components, services, and models operate correctly in isolation. By mocking external dependencies like LLMs, databases, and third-party APIs, these tests provide fast, reliable, and deterministic feedback on core business logic. This guarantees the stability of the system's building blocks and prevents regressions before integration.

## Tests Summary

- **test_api_routes.py**: Tests basic API endpoint routing and responses. Ensures standard HTTP methods return expected status codes.
- **test_audio_processor.py**: Validates audio extraction and processing logic. Ensures audio streams are correctly parsed and chunked.
- **test_cloudinary_utils.py**: Tests the integration utilities for Cloudinary. Verifies asset uploading, fetching, and deletion logic.
- **test_embedding_service.py**: Validates text embedding generation logic. Ensures text chunks are correctly embedded using the local/remote models.
- **test_health.py**: Tests the basic health check endpoints of the application. Ensures the API reports its status correctly.
- **test_job_orchestrator.py**: Validates background job scheduling and state management. Ensures jobs transition correctly between pending, running, and completed states.
- **test_library_api.py**: Tests the media library CRUD operations. Ensures items can be added, updated, retrieved, and deleted from the library.
- **test_local_llm_client.py**: Validates the local LLM client wrapper logic. Ensures requests are formatted correctly and `LlmResponse` objects are properly constructed.
- **test_media_utils.py**: Tests utility functions for media handling and conversion. Ensures file type detection and metadata extraction work as expected.
- **test_openai_retry.py**: Validates the retry mechanisms for external LLM calls. Ensures transient errors from OpenAI are handled gracefully with exponential backoff.
- **test_rate_limit.py**: Tests the application's rate limiting logic. Ensures users cannot exceed their allocated API quota within specific timeframes.
- **test_router_agent.py**: Validates the initial query routing logic. Ensures incoming queries are correctly classified and routed to the appropriate downstream agent.
- **test_search_api.py**: Tests the standard search endpoints. Ensures queries return formatted search results and metadata.
- **test_search_service.py**: Validates the core search logic interacting with the vector store. Ensures semantic searches retrieve the most relevant chunks.
- **test_segment_windowing.py**: Tests text segmentation and windowing logic. Ensures large texts are chunked with appropriate overlap for context preservation.
- **test_synthesis_agent.py**: Validates the V1 synthesis agent's logic. Ensures retrieved context is correctly synthesized into a final answer.
- **test_text_processor.py**: Tests text cleaning and preprocessing utilities. Ensures raw text is sanitized before embedding or LLM processing.
- **test_transcription_service.py**: Validates the audio transcription logic. Ensures audio files are correctly converted to text transcripts.
- **test_upload.py**: Tests the file upload endpoints. Ensures files are correctly received, validated, and stored.
- **test_v2_agents.py**: Validates the generalized behavior of V2 agents. Ensures they follow standard interfaces and return structured data.
- **test_v2_conversation_memory.py**: Tests conversation history management in V2. Ensures past interactions are correctly injected into current prompts.
- **test_v2_decision_agent.py**: Validates the decision-making logic of the V2 Decision Agent. Ensures it correctly evaluates options based on retrieved context.
- **test_v2_llm_health.py**: Tests health checks specific to the LLM connections in V2. Ensures the pipeline can gracefully handle LLM downtime.
- **test_v2_logging.py**: Validates the unified logging schema (pipeline_runs and pipeline_steps). Ensures JSONB tracing of LLM prompts and outputs works correctly.
- **test_v2_pipeline.py**: Tests the core V2 `PipelineOrchestrator`. Ensures the entire flow from query routing to synthesis is executed correctly in sequence.
- **test_v2_rag_synthesis.py**: Validates the specific synthesis logic for RAG in V2. Ensures it correctly cites sources and synthesizes a comprehensive response.
- **test_v2_rrf.py**: Tests the Reciprocal Rank Fusion (RRF) logic. Ensures multiple search results are correctly merged and ranked.
- **test_v2_search_api.py**: Validates the V2 specific search API endpoints. Ensures the V2 pipeline orchestrator is correctly invoked and returns results.
- **test_vector_store.py**: Tests vector database interactions. Ensures embeddings can be inserted, queried, and deleted effectively.
- **test_video_processor.py**: Validates video file handling and frame extraction logic. Ensures video streams are processed correctly.
- **test_vision_service.py**: Tests image processing and analysis logic. Ensures images are correctly passed to vision models and parsed.
