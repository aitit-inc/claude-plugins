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
    company_name TEXT NOT NULL,
    corporate_number TEXT,  -- 法人番号（13桁）。わかる場合のみ
    industry TEXT,
    website_url TEXT,
    email TEXT,
    contact_form_url TEXT,
    sns_accounts TEXT,  -- JSON: {"twitter": "...", "linkedin": "...", ...}
    do_not_contact INTEGER NOT NULL DEFAULT 0,  -- 1 = 送付NG（全プロジェクト共通）
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS project_prospects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    prospect_id INTEGER NOT NULL,
    match_reason TEXT,  -- なぜこの企業がこのプロジェクトのターゲットとして適切か
    priority INTEGER DEFAULT 3,  -- 1=最高 5=最低
    status TEXT NOT NULL DEFAULT 'new',  -- new, contacted, responded, converted, rejected, inactive
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (prospect_id) REFERENCES prospects(id),
    UNIQUE(project_id, prospect_id)
);

CREATE TABLE IF NOT EXISTS outreach_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    prospect_id INTEGER NOT NULL,
    channel TEXT NOT NULL,  -- email, form, sns_twitter, sns_linkedin, etc.
    subject TEXT,
    body TEXT,
    status TEXT NOT NULL DEFAULT 'sent',  -- sent, failed
    sent_at TEXT NOT NULL DEFAULT (datetime('now')),
    error_message TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (prospect_id) REFERENCES prospects(id)
);

CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    outreach_log_id INTEGER NOT NULL,
    channel TEXT NOT NULL,
    content TEXT,
    sentiment TEXT,  -- positive, neutral, negative
    response_type TEXT,  -- reply, auto_reply, bounce, meeting_request, rejection, etc.
    received_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (outreach_log_id) REFERENCES outreach_logs(id)
);

CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    evaluation_date TEXT NOT NULL DEFAULT (datetime('now')),
    metrics TEXT NOT NULL,  -- JSON: {"total_sent": N, "response_rate": 0.XX, ...}
    findings TEXT NOT NULL,
    improvements TEXT NOT NULL,  -- JSON array of improvement actions
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_project_prospects_project ON project_prospects(project_id);
CREATE INDEX IF NOT EXISTS idx_project_prospects_prospect ON project_prospects(prospect_id);
CREATE INDEX IF NOT EXISTS idx_project_prospects_status ON project_prospects(status);
CREATE INDEX IF NOT EXISTS idx_outreach_project ON outreach_logs(project_id);
CREATE INDEX IF NOT EXISTS idx_outreach_prospect ON outreach_logs(prospect_id);
CREATE INDEX IF NOT EXISTS idx_responses_outreach ON responses(outreach_log_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_project ON evaluations(project_id);
