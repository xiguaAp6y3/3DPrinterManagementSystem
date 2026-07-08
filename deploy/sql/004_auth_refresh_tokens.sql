IF OBJECT_ID(N'dbo.auth_refresh_tokens', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.auth_refresh_tokens (
        id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        token_hash NVARCHAR(128) NOT NULL,
        subject_type NVARCHAR(50) NOT NULL,
        user_id BIGINT NULL,
        staff_user_id BIGINT NULL,
        expires_at DATETIME2(3) NOT NULL,
        revoked_at DATETIME2(3) NULL,
        created_at DATETIME2(3) NOT NULL CONSTRAINT DF_auth_refresh_tokens_created_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_auth_refresh_tokens_token_hash UNIQUE (token_hash),
        CONSTRAINT FK_auth_refresh_tokens_user FOREIGN KEY (user_id) REFERENCES dbo.users(id),
        CONSTRAINT FK_auth_refresh_tokens_staff FOREIGN KEY (staff_user_id) REFERENCES dbo.staff_users(id),
        CONSTRAINT CK_auth_refresh_tokens_subject_type CHECK (subject_type IN (N'app', N'admin')),
        CONSTRAINT CK_auth_refresh_tokens_subject CHECK (
            (subject_type = N'app' AND user_id IS NOT NULL AND staff_user_id IS NULL)
            OR (subject_type = N'admin' AND staff_user_id IS NOT NULL AND user_id IS NULL)
        )
    );
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_auth_refresh_tokens_user' AND object_id = OBJECT_ID(N'dbo.auth_refresh_tokens'))
BEGIN
    CREATE INDEX IX_auth_refresh_tokens_user ON dbo.auth_refresh_tokens(user_id, expires_at);
END;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_auth_refresh_tokens_staff' AND object_id = OBJECT_ID(N'dbo.auth_refresh_tokens'))
BEGIN
    CREATE INDEX IX_auth_refresh_tokens_staff ON dbo.auth_refresh_tokens(staff_user_id, expires_at);
END;
GO
