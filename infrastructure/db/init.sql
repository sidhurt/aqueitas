-- Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Projects Table
-- Stores metadata about the repositories being monitored by Aqueitas
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Engineering Logs Table
-- The raw, chronological feed of architectural decisions and diff analysis
CREATE TABLE IF NOT EXISTS engineering_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    commit_hash VARCHAR(40),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    log_content TEXT NOT NULL,
    content_embedding vector(1536), -- Dimension set for text-embedding-3-small
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create HNSW index for high-speed semantic search on logs
CREATE INDEX IF NOT EXISTS engineering_logs_embedding_idx 
ON engineering_logs USING hnsw (content_embedding vector_cosine_ops);

-- 3. Technical Lessons Table
-- Distilled, synthesized lessons learned across sprints
CREATE TABLE IF NOT EXISTS technical_lessons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    lesson_text TEXT NOT NULL,
    vector_embedding vector(1536), -- Dimension set for text-embedding-3-small
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create HNSW index for high-speed semantic search on lessons
CREATE INDEX IF NOT EXISTS technical_lessons_embedding_idx 
ON technical_lessons USING hnsw (vector_embedding vector_cosine_ops);

-- Function to automatically update 'updated_at' timestamp
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for projects table
CREATE TRIGGER update_projects_modtime
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();
