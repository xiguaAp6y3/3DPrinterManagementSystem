IF EXISTS (SELECT 1 FROM dbo.staff_users WHERE username = N'admin')
BEGIN
    UPDATE dbo.staff_users
    SET
        password_hash = N'$argon2id$v=19$m=65536,t=3,p=4$XOJSBfXbP5bLF/anAcierA$ee9/Of+a7/UbpOlXBvUufhJ64GYqVWM6LI4SS1BTVxc',
        email = COALESCE(email, N'admin@local.3dpms'),
        display_name = COALESCE(display_name, N'管理员'),
        role = N'super_admin',
        status = N'active',
        updated_at = SYSUTCDATETIME()
    WHERE username = N'admin';
END
ELSE
BEGIN
    INSERT INTO dbo.staff_users (username, email, password_hash, display_name, role, status)
    VALUES (
        N'admin',
        N'admin@local.3dpms',
        N'$argon2id$v=19$m=65536,t=3,p=4$XOJSBfXbP5bLF/anAcierA$ee9/Of+a7/UbpOlXBvUufhJ64GYqVWM6LI4SS1BTVxc',
        N'管理员',
        N'super_admin',
        N'active'
    );
END;
GO
