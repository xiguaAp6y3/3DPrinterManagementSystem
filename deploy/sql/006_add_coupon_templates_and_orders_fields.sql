-- Incremental migration: coupon templates, grant batches, orders coupon fields.
-- Run this on an EXISTING database that has user_coupons from 005 but lacks templates.
-- For fresh databases, 001_create_tables.sql already includes everything.
--
-- Encoding policy: business text columns use NVARCHAR, string literals with Chinese use N'' prefix.

-- Sequence for grant batch numbers
IF NOT EXISTS (SELECT 1 FROM sys.sequences WHERE name = N'seq_grant_batch_no' AND schema_id = SCHEMA_ID(N'dbo'))
BEGIN
    CREATE SEQUENCE dbo.seq_grant_batch_no AS BIGINT START WITH 1 INCREMENT BY 1;
END;
GO

-- Coupon templates (admin-defined, no discount upper-bound at DB level).
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = N'coupon_templates' AND schema_id = SCHEMA_ID(N'dbo'))
BEGIN
    CREATE TABLE dbo.coupon_templates (
        id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        coupon_no NVARCHAR(50) NOT NULL,
        name NVARCHAR(100) NOT NULL,
        discount_type NVARCHAR(50) NOT NULL,
        discount_value DECIMAL(18,2) NOT NULL,
        min_spend DECIMAL(18,2) NOT NULL CONSTRAINT DF_coupon_templates_min_spend DEFAULT 0,
        max_discount DECIMAL(18,2) NULL,
        scope_type NVARCHAR(50) NOT NULL CONSTRAINT DF_coupon_templates_scope_type DEFAULT N'all',
        scope_category_id BIGINT NULL,
        scope_product_id BIGINT NULL,
        validity_type NVARCHAR(50) NOT NULL,
        valid_days INT NULL,
        fixed_start_at DATETIME2(3) NULL,
        fixed_end_at DATETIME2(3) NULL,
        total_quota BIGINT NULL,
        issued_count BIGINT NOT NULL CONSTRAINT DF_coupon_templates_issued_count DEFAULT 0,
        per_user_limit INT NULL,
        status NVARCHAR(50) NOT NULL CONSTRAINT DF_coupon_templates_status DEFAULT N'active',
        remark NVARCHAR(1000) NULL,
        created_by BIGINT NULL,
        created_at DATETIME2(3) NOT NULL CONSTRAINT DF_coupon_templates_created_at DEFAULT DATEADD(HOUR, 8, SYSUTCDATETIME()),
        updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_coupon_templates_updated_at DEFAULT DATEADD(HOUR, 8, SYSUTCDATETIME()),
        row_version ROWVERSION NOT NULL,
        CONSTRAINT UQ_coupon_templates_no UNIQUE (coupon_no),
        CONSTRAINT FK_coupon_templates_category FOREIGN KEY (scope_category_id) REFERENCES dbo.product_categories(id),
        CONSTRAINT FK_coupon_templates_product FOREIGN KEY (scope_product_id) REFERENCES dbo.products(id),
        CONSTRAINT FK_coupon_templates_created_by FOREIGN KEY (created_by) REFERENCES dbo.staff_users(id),
        CONSTRAINT CK_coupon_templates_discount_type CHECK (discount_type IN (N'fixed', N'percentage', N'fixed_no_threshold')),
        CONSTRAINT CK_coupon_templates_scope_type CHECK (scope_type IN (N'all', N'listed_product', N'custom', N'category', N'product')),
        CONSTRAINT CK_coupon_templates_validity_type CHECK (validity_type IN (N'fixed', N'relative')),
        CONSTRAINT CK_coupon_templates_status CHECK (status IN (N'active', N'disabled', N'archived')),
        CONSTRAINT CK_coupon_templates_discount_value CHECK (discount_value >= 0),
        CONSTRAINT CK_coupon_templates_max_discount CHECK (max_discount IS NULL OR max_discount >= 0)
    );
END;
GO

-- Coupon grant batches (admin batch issue tracking).
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = N'coupon_grant_batches' AND schema_id = SCHEMA_ID(N'dbo'))
BEGIN
    CREATE TABLE dbo.coupon_grant_batches (
        id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        batch_no NVARCHAR(50) NOT NULL,
        template_id BIGINT NOT NULL,
        granted_by BIGINT NOT NULL,
        target_type NVARCHAR(50) NOT NULL,
        target_count INT NOT NULL,
        success_count INT NOT NULL CONSTRAINT DF_coupon_grant_batches_success DEFAULT 0,
        remark NVARCHAR(1000) NULL,
        created_at DATETIME2(3) NOT NULL CONSTRAINT DF_coupon_grant_batches_created_at DEFAULT DATEADD(HOUR, 8, SYSUTCDATETIME()),
        CONSTRAINT UQ_coupon_grant_batches_no UNIQUE (batch_no),
        CONSTRAINT FK_coupon_grant_batches_template FOREIGN KEY (template_id) REFERENCES dbo.coupon_templates(id),
        CONSTRAINT FK_coupon_grant_batches_granted_by FOREIGN KEY (granted_by) REFERENCES dbo.staff_users(id),
        CONSTRAINT CK_coupon_grant_batches_target_type CHECK (target_type IN (N'all_users', N'specified_users', N'single_user')),
        CONSTRAINT CK_coupon_grant_batches_count CHECK (target_count > 0 AND success_count >= 0 AND success_count <= target_count)
    );
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_coupon_grant_batches_template' AND [object_id] = OBJECT_ID(N'dbo.coupon_grant_batches'))
BEGIN
    CREATE INDEX IX_coupon_grant_batches_template ON dbo.coupon_grant_batches(template_id, created_at DESC);
END;
GO

-- Add template_id to user_coupons (nullable: lottery coupons may not have a template).
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE name = N'template_id' AND [object_id] = OBJECT_ID(N'dbo.user_coupons'))
BEGIN
    ALTER TABLE dbo.user_coupons ADD template_id BIGINT NULL;
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_user_coupons_template' AND [parent_object_id] = OBJECT_ID(N'dbo.user_coupons'))
BEGIN
    ALTER TABLE dbo.user_coupons ADD CONSTRAINT FK_user_coupons_template FOREIGN KEY (template_id) REFERENCES dbo.coupon_templates(id);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_user_coupons_template' AND [object_id] = OBJECT_ID(N'dbo.user_coupons'))
BEGIN
    CREATE INDEX IX_user_coupons_template ON dbo.user_coupons(template_id);
END;
GO

-- Add created_by column to user_coupons (for admin-granted coupons).
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE name = N'created_by' AND [object_id] = OBJECT_ID(N'dbo.user_coupons'))
BEGIN
    ALTER TABLE dbo.user_coupons ADD created_by BIGINT NULL;
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_user_coupons_created_by' AND [parent_object_id] = OBJECT_ID(N'dbo.user_coupons'))
BEGIN
    ALTER TABLE dbo.user_coupons ADD CONSTRAINT FK_user_coupons_created_by FOREIGN KEY (created_by) REFERENCES dbo.staff_users(id);
END;
GO

-- Add coupon fields to orders.
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE name = N'user_coupon_id' AND [object_id] = OBJECT_ID(N'dbo.orders'))
BEGIN
    ALTER TABLE dbo.orders ADD user_coupon_id BIGINT NULL;
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE name = N'coupon_discount_amount' AND [object_id] = OBJECT_ID(N'dbo.orders'))
BEGIN
    ALTER TABLE dbo.orders ADD coupon_discount_amount DECIMAL(18,2) NOT NULL CONSTRAINT DF_orders_coupon_discount DEFAULT 0;
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_orders_user_coupon' AND [parent_object_id] = OBJECT_ID(N'dbo.orders'))
BEGIN
    ALTER TABLE dbo.orders ADD CONSTRAINT FK_orders_user_coupon FOREIGN KEY (user_coupon_id) REFERENCES dbo.user_coupons(id);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_orders_user_coupon' AND [object_id] = OBJECT_ID(N'dbo.orders'))
BEGIN
    CREATE INDEX IX_orders_user_coupon ON dbo.orders(user_coupon_id);
END;
GO
