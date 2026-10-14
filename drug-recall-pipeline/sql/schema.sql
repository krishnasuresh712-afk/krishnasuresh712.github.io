CREATE TABLE IF NOT EXISTS recalls (
    recall_number          TEXT PRIMARY KEY,
    report_date            DATE NOT NULL,
    recall_initiation_date DATE,
    classification         TEXT,          -- Class I (most serious), II, III
    status                 TEXT,          -- Ongoing, Completed, Terminated
    recalling_firm         TEXT,
    state                  TEXT,
    country                TEXT,
    voluntary_mandated     TEXT,
    product_description    TEXT,
    reason_for_recall      TEXT,
    reason_category        TEXT,          -- derived in ingest.categorize_reason
    distribution_pattern   TEXT,
    loaded_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_recalls_report_date ON recalls (report_date);
CREATE INDEX IF NOT EXISTS idx_recalls_firm ON recalls (recalling_firm);

CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    since_date    DATE,
    records_seen  INTEGER,
    records_new   INTEGER
);
