-- Migration: Add scenario_id column to workflows table
-- Date: 2026-04-16

-- Add scenario_id column
ALTER TABLE workflows 
ADD COLUMN IF NOT EXISTS scenario_id VARCHAR NOT NULL DEFAULT 'research_assistant_v1';

-- Add index for scenario_id
CREATE INDEX IF NOT EXISTS idx_workflows_scenario_id 
ON workflows(scenario_id);

-- Comment on the column
COMMENT ON COLUMN workflows.scenario_id IS '场景标识符，用于标识工作流所属的业务场景';
