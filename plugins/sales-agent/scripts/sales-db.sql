-- Sales Agent Database Schema

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    directory TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prospects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    company_name TEXT NOT NULL,
    industry TEXT,
    location TEXT,
    website_url TEXT,
    email TEXT,
    contact_form_url TEXT,
    sns_accounts TEXT,  -- JSON: {"twitter": "...", "linkedin": "...", ...}
    key_person TEXT,
    key_person_title TEXT,
    match_reason TEXT,  -- なぜこの企業がターゲットとして適切か
    priority INTEGER DEFAULT 3,  -- 1=最高 5=最低
    status TEXT NOT NULL DEFAULT 'new',  -- new, contacted, responded, converted, rejected, inactive
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS outreach_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL,
    channel TEXT NOT NULL,  -- email, form, sns_twitter, sns_linkedin, etc.
    subject TEXT,
    body TEXT,
    status TEXT NOT NULL DEFAULT 'sent',  -- draft, sent, delivered, bounced, failed
    sent_at TEXT NOT NULL DEFAULT (datetime('now')),
    error_message TEXT,
    FOREIGN KEY (prospect_id) REFERENCES prospects(id)
);

CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL,
    outreach_log_id INTEGER,
    channel TEXT NOT NULL,
    content TEXT,
    sentiment TEXT,  -- positive, neutral, negative
    response_type TEXT,  -- reply, auto_reply, bounce, meeting_request, rejection, etc.
    received_at TEXT NOT NULL DEFAULT (datetime('now')),
    notes TEXT,
    FOREIGN KEY (prospect_id) REFERENCES prospects(id),
    FOREIGN KEY (outreach_log_id) REFERENCES outreach_logs(id)
);

CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    evaluation_date TEXT NOT NULL DEFAULT (datetime('now')),
    metrics TEXT NOT NULL,  -- JSON: {"total_sent": N, "response_rate": 0.XX, ...}
    findings TEXT NOT NULL,
    improvements TEXT NOT NULL,  -- JSON array of improvement actions
    applied_changes TEXT,  -- 実際に適用した変更の記録
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_prospects_project ON prospects(project_id);
CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(status);
CREATE INDEX IF NOT EXISTS idx_outreach_prospect ON outreach_logs(prospect_id);
CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach_logs(status);
CREATE INDEX IF NOT EXISTS idx_responses_prospect ON responses(prospect_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_project ON evaluations(project_id);
