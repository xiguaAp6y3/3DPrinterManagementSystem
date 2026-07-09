-- Fix customer account uniqueness for soft delete.
-- Run this script in database 3DPMS. Do not use USE statements here.
--
-- Goal:
-- 1. Deleted users should not occupy email / phone uniqueness.
-- 2. Active, disabled, and other non-deleted users still keep unique email / phone.

IF EXISTS (
    SELECT 1
    FROM sys.key_constraints
    WHERE [name] = N'UQ_users_email'
      AND [parent_object_id] = OBJECT_ID(N'dbo.users')
)
BEGIN
    ALTER TABLE dbo.users DROP CONSTRAINT UQ_users_email;
END;
GO

IF EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE [name] = N'UX_users_phone_not_null'
      AND [object_id] = OBJECT_ID(N'dbo.users')
)
BEGIN
    DROP INDEX UX_users_phone_not_null ON dbo.users;
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE [name] = N'UX_users_email_active'
      AND [object_id] = OBJECT_ID(N'dbo.users')
)
BEGIN
    CREATE UNIQUE INDEX UX_users_email_active
    ON dbo.users(email)
    WHERE deleted_at IS NULL;
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE [name] = N'UX_users_phone_active_not_null'
      AND [object_id] = OBJECT_ID(N'dbo.users')
)
BEGIN
    CREATE UNIQUE INDEX UX_users_phone_active_not_null
    ON dbo.users(phone)
    WHERE phone IS NOT NULL AND deleted_at IS NULL;
END;
GO
