-- Incremental migration: coupon & lottery demo tables.
-- Run this on an EXISTING database that was initialised with 001-003 before coupons existed.
-- For fresh databases, 001_create_tables.sql already includes these tables, so this script
-- is a no-op (guarded by IF NOT EXISTS).
--
-- Encoding policy: business text columns use NVARCHAR, string literals with Chinese use N'' prefix.

IF NOT EXISTS (SELECT 1 FROM sys.sequences WHERE object_id = OBJECT_ID(N'dbo.seq_coupon_no') AND [object_id] = OBJECT_ID(N'dbo.seq_coupon_no'))
BEGIN
    CREATE SEQUENCE dbo.seq_coupon_no AS BIGINT START WITH 1 INCREMENT BY 1;
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.sequences WHERE name = N'seq_lottery_record_no' AND schema_id = SCHEMA_ID(N'dbo'))
BEGIN
    CREATE SEQUENCE dbo.seq_lottery_record_no AS BIGINT START WITH 1 INCREMENT BY 1;
END;
GO

-- User coupons (issued instances).
-- For the demo, coupons are percentage-discount only (e.g. 85 = 8.5折).
-- discount_value must be >= 80 (最多八折) and < 100.
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = N'user_coupons' AND schema_id = SCHEMA_ID(N'dbo'))
BEGIN
    CREATE TABLE dbo.user_coupons (
        id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        coupon_no NVARCHAR(50) NOT NULL,
        name NVARCHAR(100) NOT NULL,
        discount_type NVARCHAR(50) NOT NULL CONSTRAINT DF_user_coupons_discount_type DEFAULT N'percentage',
        discount_value DECIMAL(18,2) NOT NULL,
        min_spend DECIMAL(18,2) NOT NULL CONSTRAINT DF_user_coupons_min_spend DEFAULT 0,
        scope_type NVARCHAR(50) NOT NULL CONSTRAINT DF_user_coupons_scope_type DEFAULT N'all',
        source NVARCHAR(50) NOT NULL CONSTRAINT DF_user_coupons_source DEFAULT N'lottery',
        status NVARCHAR(50) NOT NULL CONSTRAINT DF_user_coupons_status DEFAULT N'unused',
        valid_from DATETIME2(3) NOT NULL,
        valid_until DATETIME2(3) NOT NULL,
        used_at DATETIME2(3) NULL,
        used_order_id BIGINT NULL,
        discount_amount DECIMAL(18,2) NULL,
        revoked_at DATETIME2(3) NULL,
        revoked_by BIGINT NULL,
        revoke_reason NVARCHAR(500) NULL,
        created_at DATETIME2(3) NOT NULL CONSTRAINT DF_user_coupons_created_at DEFAULT DATEADD(HOUR, 8, SYSUTCDATETIME()),
        updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_user_coupons_updated_at DEFAULT DATEADD(HOUR, 8, SYSUTCDATETIME()),
        row_version ROWVERSION NOT NULL,
        CONSTRAINT UQ_user_coupons_no UNIQUE (coupon_no),
        CONSTRAINT FK_user_coupons_user FOREIGN KEY (user_id) REFERENCES dbo.users(id),
        CONSTRAINT FK_user_coupons_order FOREIGN KEY (used_order_id) REFERENCES dbo.orders(id),
        CONSTRAINT FK_user_coupons_revoked_by FOREIGN KEY (revoked_by) REFERENCES dbo.staff_users(id),
        CONSTRAINT CK_user_coupons_discount_type CHECK (discount_type IN (N'percentage', N'fixed', N'fixed_no_threshold')),
        CONSTRAINT CK_user_coupons_source CHECK (source IN (N'admin_grant', N'lottery', N'signup_gift', N'promotion')),
        CONSTRAINT CK_user_coupons_status CHECK (status IN (N'unused', N'used', N'expired', N'revoked')),
        CONSTRAINT CK_user_coupons_scope CHECK (scope_type IN (N'all', N'listed_product', N'custom', N'category', N'product')),
        CONSTRAINT CK_user_coupons_time CHECK (valid_until > valid_from),
        CONSTRAINT CK_user_coupons_discount_value CHECK (discount_value >= 0),
        CONSTRAINT CK_user_coupons_discount_amount CHECK (discount_amount IS NULL OR discount_amount >= 0)
    );
END;
GO

-- Lottery draw records (tracks every draw, supports idempotency & daily limits).
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = N'lottery_records' AND schema_id = SCHEMA_ID(N'dbo'))
BEGIN
    CREATE TABLE dbo.lottery_records (
        id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        record_no NVARCHAR(50) NOT NULL,
        user_id BIGINT NOT NULL,
        is_win BIT NOT NULL CONSTRAINT DF_lottery_records_is_win DEFAULT 1,
        prize_name NVARCHAR(100) NOT NULL,
        discount_value DECIMAL(18,2) NULL,
        won_coupon_id BIGINT NULL,
        idempotency_key NVARCHAR(100) NOT NULL,
        client_ip NVARCHAR(50) NULL,
        created_at DATETIME2(3) NOT NULL CONSTRAINT DF_lottery_records_created_at DEFAULT DATEADD(HOUR, 8, SYSUTCDATETIME()),
        CONSTRAINT UQ_lottery_records_no UNIQUE (record_no),
        CONSTRAINT FK_lottery_records_user FOREIGN KEY (user_id) REFERENCES dbo.users(id),
        CONSTRAINT FK_lottery_records_coupon FOREIGN KEY (won_coupon_id) REFERENCES dbo.user_coupons(id),
        CONSTRAINT CK_lottery_records_win CHECK (
            (is_win = 1 AND discount_value IS NOT NULL)
            OR (is_win = 0 AND discount_value IS NULL)
        )
    );
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_user_coupons_user_status' AND [object_id] = OBJECT_ID(N'dbo.user_coupons'))
BEGIN
    CREATE INDEX IX_user_coupons_user_status ON dbo.user_coupons(user_id, status, valid_until DESC);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_lottery_records_user_created' AND [object_id] = OBJECT_ID(N'dbo.lottery_records'))
BEGIN
    CREATE INDEX IX_lottery_records_user_created ON dbo.lottery_records(user_id, created_at DESC);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_lottery_records_user_idem' AND [object_id] = OBJECT_ID(N'dbo.lottery_records'))
BEGIN
    CREATE UNIQUE INDEX UX_lottery_records_user_idem ON dbo.lottery_records(user_id, idempotency_key);
END;
GO
