-- This file is automatically executed when the PostgreSQL container starts for the first time

-- Create feedback table
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    feedback INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    session_id TEXT
);

-- Create conversations table for monitoring
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    relevance TEXT,
    relevance_explanation TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    eval_prompt_tokens INTEGER,
    eval_completion_tokens INTEGER,
    eval_total_tokens INTEGER,
    openai_cost DECIMAL(10, 6),
    response_time DECIMAL(10, 3),
    timestamp TIMESTAMP NOT NULL,
    session_id TEXT
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback(timestamp);
CREATE INDEX IF NOT EXISTS idx_feedback_session ON feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp);
CREATE INDEX IF NOT EXISTS idx_conversations_relevance ON conversations(relevance);
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);