-- Migration 009: Add 'deleted' to knowledge_products status CHECK constraint
-- Needed for seller soft-delete flow (DELETE /api/v1/seller/products/{id})
-- Current enum from migration 008:
--   pending_review, approved, rejected, disabled, live, takedown, published, unpublished, archived

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
        'archived',
        'deleted'
    ));
