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
-- domain_canonical  — one of the 15 canonical domain names (e.g. "Energy")
--                     resolved by the broker from data/domain-config.json keywords
-- domain_image      — relative image path (e.g. "pics/domains/energy.jpg")
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS datasets (
    id               SERIAL PRIMARY KEY,
    name             TEXT NOT NULL UNIQUE,
    domain           TEXT,
    domain_canonical TEXT,
    domain_image     TEXT,
    source_url       TEXT,
    metadata         JSONB,
    updated_at       TIMESTAMP DEFAULT NOW()
);

-- Migrate existing tables: add columns if this schema is re-applied to an
-- already-provisioned database (safe to run multiple times).
ALTER TABLE datasets ADD COLUMN IF NOT EXISTS domain_canonical TEXT;
ALTER TABLE datasets ADD COLUMN IF NOT EXISTS domain_image     TEXT;

-- ---------------------------------------------------------------------------
-- models
-- ---------------------------------------------------------------------------
-- Each row is one benchmark / foundation model catalogued in the Commons.
-- The 79 names correspond to the benchmark columns in the source CSV and
-- to the ALL_MODELS list in js/models.js.
-- metadata (JSONB) holds:
--   description, datasetsCount, dominantDomain
-- domain_canonical / domain_image — same enrichment as datasets,
--   derived from the model's dominantDomain or an explicit domain hint.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS models (
    id               SERIAL PRIMARY KEY,
    name             TEXT NOT NULL UNIQUE,
    architecture     TEXT,
    domain_canonical TEXT,
    domain_image     TEXT,
    source_url       TEXT,
    metadata         JSONB,
    updated_at       TIMESTAMP DEFAULT NOW()
);

ALTER TABLE models ADD COLUMN IF NOT EXISTS domain_canonical TEXT;
ALTER TABLE models ADD COLUMN IF NOT EXISTS domain_image     TEXT;

-- ---------------------------------------------------------------------------
-- Trigger function — INSERT / UPDATE
-- Fires on two channels:
--   'catalog_updates'         — backwards-compatible generic channel
--   'catalog_<table>'         — per-type channel (catalog_datasets, catalog_models)
-- Payload shape:
--   {"table":"datasets","action":"INSERT","id":42,"name":"...","updated_at":"..."}
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION notify_catalog_update()
RETURNS trigger AS $$
DECLARE
  payload TEXT;
BEGIN
  payload := json_build_object(
    'table',            TG_TABLE_NAME,
    'action',           TG_OP,
    'id',               NEW.id,
    'name',             NEW.name,
    'domain_canonical', NEW.domain_canonical,
    'domain_image',     NEW.domain_image,
    'updated_at',       NEW.updated_at
  )::text;

  PERFORM pg_notify('catalog_updates',              payload);
  PERFORM pg_notify('catalog_' || TG_TABLE_NAME,    payload);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- Trigger function — DELETE
-- Uses OLD (not NEW) since the row no longer exists after deletion.
-- Also fires on both channels so the listener can handle removals.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION notify_catalog_delete()
RETURNS trigger AS $$
DECLARE
  payload TEXT;
BEGIN
  payload := json_build_object(
    'table',  TG_TABLE_NAME,
    'action', TG_OP,
    'id',     OLD.id,
    'name',   OLD.name
  )::text;

  PERFORM pg_notify('catalog_updates',              payload);
  PERFORM pg_notify('catalog_' || TG_TABLE_NAME,    payload);
  RETURN OLD;
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

DROP TRIGGER IF EXISTS datasets_delete_notify ON datasets;
CREATE TRIGGER datasets_delete_notify
AFTER DELETE ON datasets
FOR EACH ROW EXECUTE FUNCTION notify_catalog_delete();

DROP TRIGGER IF EXISTS models_delete_notify ON models;
CREATE TRIGGER models_delete_notify
AFTER DELETE ON models
FOR EACH ROW EXECUTE FUNCTION notify_catalog_delete();
