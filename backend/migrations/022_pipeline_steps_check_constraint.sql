-- Drop legacy CHECK constraint on pipeline_steps to allow precheck, assess_evidence, verify_citations, evaluate_groundedness, etc.
ALTER TABLE pipeline_steps DROP CONSTRAINT IF EXISTS pipeline_steps_step_type_check;
