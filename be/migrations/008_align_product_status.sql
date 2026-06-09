-- Migration 008: Align product status values across migrations
-- Migration 005 used 'live'/'takedown', architect spec / current backend code uses 'published'/'unpublished'
-- Allow both, plus archived for backward compat

ALTER TABLE knowledge_products DROP CONSTRAINT IF EXISTS knowledge_products_status_check;
ALTER TABLE knowledge_products ADD CONSTRAINT knowledge_products_status_check
    CHECK (status IN (
        'pending_review',
        'approved',
        'rejected',
        'disabled',
        'live',
        'takedown',
        'published',
        'unpublished',
        'archived'
    ));
