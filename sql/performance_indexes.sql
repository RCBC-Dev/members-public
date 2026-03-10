-- Performance indexes for members_app_enquiry
-- These indexes were manually created in SSMS for query performance tuning.
-- They are NOT managed by Django migrations and must be applied manually
-- to each environment (TEST, LIVE).
--
-- Django-managed indexes are defined in application/models.py and applied
-- via migrations - do not add those here.
--
-- Run with the correct database selected, e.g.:
--   USE MembersEnquiries;  -- TEST
--   USE Members2;          -- LIVE
-- ---------------------------------------------------------------------------

-- Wide covering index for the main enquiry list query
-- Covers all columns returned in list views to avoid key lookups
CREATE INDEX IX_enquiry_created_desc_with_joins
ON members_app_enquiry (created_at DESC)
INCLUDE (id, title, reference, description, status, member_id, admin_id,
         section_id, contact_id, job_type_id, updated_at, closed_at);

-- FK + date compound indexes for filtering by related entity with date ordering
CREATE INDEX IX_enquiry_member_fk   ON members_app_enquiry (member_id,   created_at DESC);
CREATE INDEX IX_enquiry_admin_fk    ON members_app_enquiry (admin_id,    created_at DESC);
CREATE INDEX IX_enquiry_section_fk  ON members_app_enquiry (section_id,  created_at DESC);
CREATE INDEX IX_enquiry_contact_fk  ON members_app_enquiry (contact_id,  created_at DESC);
CREATE INDEX IX_enquiry_jobtype_fk  ON members_app_enquiry (job_type_id, created_at DESC);

-- Simple single-column indexes (may overlap with Django-managed ones -
-- check sys.indexes before applying if in doubt)
CREATE INDEX enquiry_status_idx  ON members_app_enquiry (status);
CREATE INDEX enquiry_created_idx ON members_app_enquiry (created_at);
