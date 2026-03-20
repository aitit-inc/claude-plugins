-- 評価用SQLクエリテンプレート
-- <project_id> を実際のプロジェクトIDに置き換えて使用

-- アプローチ総数
SELECT COUNT(*) as total_outreach
FROM outreach_logs
WHERE prospect_id IN (SELECT id FROM prospects WHERE project_id = <project_id>);

-- チャネル別アプローチ数
SELECT channel, COUNT(*) as count
FROM outreach_logs
WHERE prospect_id IN (SELECT id FROM prospects WHERE project_id = <project_id>)
GROUP BY channel;

-- 反応数・ユニーク回答者数
SELECT
    COUNT(*) as total_responses,
    COUNT(DISTINCT prospect_id) as unique_responders
FROM responses
WHERE prospect_id IN (SELECT id FROM prospects WHERE project_id = <project_id>);

-- センチメント別・反応種別の内訳
SELECT sentiment, response_type, COUNT(*) as count
FROM responses
WHERE prospect_id IN (SELECT id FROM prospects WHERE project_id = <project_id>)
GROUP BY sentiment, response_type;

-- 優先度別の反応率
SELECT
    p.priority,
    COUNT(DISTINCT CASE WHEN o.id IS NOT NULL THEN p.id END) as contacted,
    COUNT(DISTINCT CASE WHEN r.id IS NOT NULL THEN p.id END) as responded
FROM prospects p
LEFT JOIN outreach_logs o ON p.id = o.prospect_id
LEFT JOIN responses r ON p.id = r.prospect_id
WHERE p.project_id = <project_id>
GROUP BY p.priority;

-- ステータス別企業数
SELECT status, COUNT(*) as count
FROM prospects
WHERE project_id = <project_id>
GROUP BY status;

-- チャネル別反応率
SELECT
    o.channel,
    COUNT(DISTINCT o.prospect_id) as contacted,
    COUNT(DISTINCT r.prospect_id) as responded,
    ROUND(CAST(COUNT(DISTINCT r.prospect_id) AS FLOAT) / NULLIF(COUNT(DISTINCT o.prospect_id), 0) * 100, 1) as response_rate_pct
FROM outreach_logs o
LEFT JOIN responses r ON o.prospect_id = r.prospect_id AND o.id = r.outreach_log_id
WHERE o.prospect_id IN (SELECT id FROM prospects WHERE project_id = <project_id>)
GROUP BY o.channel;
