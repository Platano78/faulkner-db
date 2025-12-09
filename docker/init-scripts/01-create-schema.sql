-- Initialize Graphiti metadata schema
CREATE TABLE IF NOT EXISTS graph_metadata (
    id SERIAL PRIMARY KEY,
    graph_name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    graph_schema JSONB
);

CREATE INDEX IF NOT EXISTS idx_graph_name ON graph_metadata(graph_name);
