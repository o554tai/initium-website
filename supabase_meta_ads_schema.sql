-- INITIUM Meta Ads Schema
-- Run this in Supabase SQL Editor

-- Agent Meta Connections (encrypted tokens)
CREATE TABLE IF NOT EXISTS agent_meta_connections (
    agent_name TEXT PRIMARY KEY,
    access_token_encrypted TEXT NOT NULL,
    ig_business_account_id TEXT,
    page_id TEXT,
    page_name TEXT,
    ad_accounts JSONB DEFAULT '[]',
    status TEXT DEFAULT 'active',
    connected_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ad Campaigns (local tracking of Meta campaigns)
CREATE TABLE IF NOT EXISTS ad_campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT REFERENCES agent_meta_connections(agent_name),
    meta_campaign_id TEXT,
    meta_adset_id TEXT,
    meta_ad_id TEXT,
    name TEXT,
    project TEXT,
    location TEXT,
    objective TEXT DEFAULT 'OUTCOME_LEADS',
    daily_budget INT DEFAULT 0,
    status TEXT DEFAULT 'DRAFT',
    angle TEXT,
    copy_headline TEXT,
    copy_body TEXT,
    creative_image_url TEXT,
    creative_video_url TEXT,
    targeting JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Launch Packages (B-mode creative factory)
CREATE TABLE IF NOT EXISTS launch_packages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT REFERENCES agent_meta_connections(agent_name),
    project TEXT,
    location TEXT,
    top_year TEXT,
    budget TEXT,
    duration_days INT DEFAULT 7,
    angle TEXT DEFAULT 'urgency',
    copy_angles JSONB DEFAULT '{}',
    targeting JSONB DEFAULT '{}',
    campaign_name TEXT,
    adset_name TEXT,
    status TEXT DEFAULT 'ready',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS (optional — manage via API key auth in backend)
ALTER TABLE agent_meta_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE ad_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE launch_packages ENABLE ROW LEVEL SECURITY;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ad_campaigns_agent ON ad_campaigns(agent_name);
CREATE INDEX IF NOT EXISTS idx_ad_campaigns_status ON ad_campaigns(status);
CREATE INDEX IF NOT EXISTS idx_launch_packages_agent ON launch_packages(agent_name);
