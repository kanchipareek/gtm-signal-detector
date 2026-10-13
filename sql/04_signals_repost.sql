-- Migration: link a re-posted signal back to the original it repeats.
-- Run ONCE against an existing database (re-running errors - the column
-- already exists). Fresh databases get this column from 01_signals.sql.
ALTER TABLE signals ADD COLUMN repost_of INTEGER REFERENCES signals(id);
