CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name TEXT
);
INSERT INTO users (name) VALUES ('demo_user');
