-- Time Series Commons — PostgreSQL Schema
-- Database: timeseries_db
--
-- Run against timeseries_db after connecting:
--   psql "host=127.0.0.1 port=5432 dbname=timeseries_db user=ts_user password=YOUR_SECURE_PASSWORD"
--   \i /path/to/schema.sql

-- ---------------------------------------------------------------------------
-- datasets
-- ---------------------------------------------------------------------------
-- Each row is one time series dataset discovered by DeepCollector.
-- metadata (JSONB) holds the full structured payload:
--   slug, timePoints, interval, variables, dimensions,
--   description, paperLink, benchmarks {ModelName: bool, ...}
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS datasets (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    domain      TEXT,
    source_url  TEXT,
    metadata    JSONB,
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- models
-- ---------------------------------------------------------------------------
-- Each row is one benchmark / foundation model catalogued in the Commons.
-- The 79 names correspond to the benchmark columns in the source CSV and
-- to the ALL_MODELS list in js/models.js.
-- metadata (JSONB) holds:
--   description, datasetsCount, dominantDomain
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS models (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    architecture TEXT,
    source_url   TEXT,
    metadata     JSONB,
    updated_at   TIMESTAMP DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Trigger function — fires pg_notify on 'catalog_updates' channel
-- Payload shape:
--   {"table":"datasets","action":"INSERT","id":42,"name":"M3 Competition","updated_at":"..."}
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION notify_catalog_update()
RETURNS trigger AS $$
BEGIN
  PERFORM pg_notify(
    'catalog_updates',
    json_build_object(
      'table',      TG_TABLE_NAME,
      'action',     TG_OP,
      'id',         NEW.id,
      'name',       NEW.name,
      'updated_at', NEW.updated_at
    )::text
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- Triggers
-- ---------------------------------------------------------------------------
DROP TRIGGER IF EXISTS datasets_notify ON datasets;
CREATE TRIGGER datasets_notify
AFTER INSERT OR UPDATE ON datasets
FOR EACH ROW EXECUTE FUNCTION notify_catalog_update();

DROP TRIGGER IF EXISTS models_notify ON models;
CREATE TRIGGER models_notify
AFTER INSERT OR UPDATE ON models
FOR EACH ROW EXECUTE FUNCTION notify_catalog_update();
