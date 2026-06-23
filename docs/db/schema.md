[{
  "table_name": "files",
  "column_name": "id",
  "data_type": "uuid"
}, {
  "table_name": "files",
  "column_name": "filename",
  "data_type": "character varying"
}, {
  "table_name": "files",
  "column_name": "modality",
  "data_type": "USER-DEFINED"
}, {
  "table_name": "files",
  "column_name": "storage_path",
  "data_type": "character varying"
}, {
  "table_name": "files",
  "column_name": "duration_seconds",
  "data_type": "double precision"
}, {
  "table_name": "files",
  "column_name": "size_bytes",
  "data_type": "integer"
}, {
  "table_name": "files",
  "column_name": "status",
  "data_type": "USER-DEFINED"
}, {
  "table_name": "files",
  "column_name": "uploaded_at",
  "data_type": "timestamp without time zone"
}, {
  "table_name": "processing_jobs",
  "column_name": "id",
  "data_type": "uuid"
}, {
  "table_name": "processing_jobs",
  "column_name": "file_id",
  "data_type": "uuid"
}, {
  "table_name": "processing_jobs",
  "column_name": "stage",
  "data_type": "character varying"
}, {
  "table_name": "processing_jobs",
  "column_name": "status",
  "data_type": "USER-DEFINED"
}, {
  "table_name": "processing_jobs",
  "column_name": "error_message",
  "data_type": "character varying"
}, {
  "table_name": "processing_jobs",
  "column_name": "created_at",
  "data_type": "timestamp without time zone"
}, {
  "table_name": "processing_jobs",
  "column_name": "updated_at",
  "data_type": "timestamp without time zone"
}, {
  "table_name": "segments",
  "column_name": "id",
  "data_type": "uuid"
}, {
  "table_name": "segments",
  "column_name": "file_id",
  "data_type": "uuid"
}, {
  "table_name": "segments",
  "column_name": "modality",
  "data_type": "USER-DEFINED"
}, {
  "table_name": "segments",
  "column_name": "content",
  "data_type": "character varying"
}, {
  "table_name": "segments",
  "column_name": "start_time",
  "data_type": "double precision"
}, {
  "table_name": "segments",
  "column_name": "end_time",
  "data_type": "double precision"
}, {
  "table_name": "segments",
  "column_name": "created_at",
  "data_type": "timestamp without time zone"
}, {
  "table_name": "pipeline_runs",
  "column_name": "id",
  "data_type": "uuid"
}, {
  "table_name": "pipeline_runs",
  "column_name": "query",
  "data_type": "character varying"
}, {
  "table_name": "pipeline_runs",
  "column_name": "modality_filter",
  "data_type": "USER-DEFINED"
}, {
  "table_name": "pipeline_runs",
  "column_name": "conversation_context",
  "data_type": "character varying"
}, {
  "table_name": "pipeline_runs",
  "column_name": "start_time",
  "data_type": "timestamp with time zone"
}, {
  "table_name": "pipeline_runs",
  "column_name": "end_time",
  "data_type": "timestamp with time zone"
}, {
  "table_name": "pipeline_runs",
  "column_name": "final_route",
  "data_type": "character varying"
}, {
  "table_name": "pipeline_runs",
  "column_name": "final_answer",
  "data_type": "character varying"
}, {
  "table_name": "pipeline_runs",
  "column_name": "final_confidence",
  "data_type": "double precision"
}, {
  "table_name": "pipeline_runs",
  "column_name": "attempts_count",
  "data_type": "integer"
}, {
  "table_name": "pipeline_runs",
  "column_name": "disclaimer_appended",
  "data_type": "boolean"
}, {
  "table_name": "pipeline_runs",
  "column_name": "created_at",
  "data_type": "timestamp with time zone"
}, {
  "table_name": "pipeline_steps",
  "column_name": "id",
  "data_type": "uuid"
}, {
  "table_name": "pipeline_steps",
  "column_name": "run_id",
  "data_type": "uuid"
}, {
  "table_name": "pipeline_steps",
  "column_name": "step_type",
  "data_type": "character varying"
}, {
  "table_name": "pipeline_steps",
  "column_name": "attempt",
  "data_type": "integer"
}, {
  "table_name": "pipeline_steps",
  "column_name": "created_at",
  "data_type": "timestamp with time zone"
}, {
  "table_name": "step_rewrites",
  "column_name": "step_id",
  "data_type": "uuid"
}, {
  "table_name": "step_rewrites",
  "column_name": "input_query",
  "data_type": "character varying"
}, {
  "table_name": "step_rewrites",
  "column_name": "prev_feedback",
  "data_type": "character varying"
}, {
  "table_name": "step_rewrites",
  "column_name": "rewritten_query",
  "data_type": "character varying"
}, {
  "table_name": "step_gates",
  "column_name": "step_id",
  "data_type": "uuid"
}, {
  "table_name": "step_gates",
  "column_name": "route",
  "data_type": "character varying"
}, {
  "table_name": "step_gates",
  "column_name": "reason",
  "data_type": "character varying"
}, {
  "table_name": "step_gates",
  "column_name": "reply",
  "data_type": "character varying"
}, {
  "table_name": "step_retrievals",
  "column_name": "step_id",
  "data_type": "uuid"
}, {
  "table_name": "step_retrievals",
  "column_name": "query",
  "data_type": "character varying"
}, {
  "table_name": "step_retrievals",
  "column_name": "rewritten_query",
  "data_type": "character varying"
}, {
  "table_name": "retrieved_sources",
  "column_name": "id",
  "data_type": "uuid"
}, {
  "table_name": "retrieved_sources",
  "column_name": "step_id",
  "data_type": "uuid"
}, {
  "table_name": "retrieved_sources",
  "column_name": "segment_id",
  "data_type": "uuid"
}, {
  "table_name": "retrieved_sources",
  "column_name": "file_id",
  "data_type": "uuid"
}, {
  "table_name": "retrieved_sources",
  "column_name": "modality",
  "data_type": "USER-DEFINED"
}, {
  "table_name": "retrieved_sources",
  "column_name": "title",
  "data_type": "character varying"
}, {
  "table_name": "retrieved_sources",
  "column_name": "content",
  "data_type": "character varying"
}, {
  "table_name": "retrieved_sources",
  "column_name": "source_path",
  "data_type": "character varying"
}, {
  "table_name": "retrieved_sources",
  "column_name": "start_time",
  "data_type": "double precision"
}, {
  "table_name": "retrieved_sources",
  "column_name": "end_time",
  "data_type": "double precision"
}, {
  "table_name": "retrieved_sources",
  "column_name": "score",
  "data_type": "double precision"
}, {
  "table_name": "retrieved_sources",
  "column_name": "rank",
  "data_type": "integer"
}, {
  "table_name": "step_syntheses",
  "column_name": "step_id",
  "data_type": "uuid"
}, {
  "table_name": "step_syntheses",
  "column_name": "answer",
  "data_type": "character varying"
}, {
  "table_name": "step_evaluations",
  "column_name": "step_id",
  "data_type": "uuid"
}, {
  "table_name": "step_evaluations",
  "column_name": "verdict",
  "data_type": "character varying"
}, {
  "table_name": "step_evaluations",
  "column_name": "confidence",
  "data_type": "double precision"
}, {
  "table_name": "step_evaluations",
  "column_name": "correct_route",
  "data_type": "character varying"
}, {
  "table_name": "step_evaluations",
  "column_name": "feedback",
  "data_type": "character varying"
}]
