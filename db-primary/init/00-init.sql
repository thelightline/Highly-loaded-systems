-- Роль для репликации
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='repl') THEN
    CREATE ROLE repl WITH REPLICATION LOGIN PASSWORD 'repl';
  END IF;
END$$;

-- Пользователь приложения
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app') THEN
    CREATE USER app WITH PASSWORD 'app';
  END IF;
END$$;

-- База данных приложения
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='trading') THEN
    CREATE DATABASE trading;
  END IF;
END$$;

GRANT ALL PRIVILEGES ON DATABASE trading TO app;
