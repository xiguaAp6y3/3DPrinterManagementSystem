IF EXISTS (SELECT 1 FROM dbo.staff_users WHERE username = N'admin')
BEGIN
    UPDATE dbo.staff_users
    SET
        password_hash = N'$argon2id$v=19$m=65536,t=3,p=4$XOJSBfXbP5bLF/anAcierA$ee9/Of+a7/UbpOlXBvUufhJ64GYqVWM6LI4SS1BTVxc',
        display_name = COALESCE(display_name, N'管理员'),
        role = COALESCE(role, N'admin'),
        status = N'active',
        updated_at = SYSUTCDATETIME()
    WHERE username = N'admin';
END
ELSE
BEGIN
    INSERT INTO dbo.staff_users (username, password_hash, display_name, role, status)
    VALUES (
        N'admin',
        N'$argon2id$v=19$m=65536,t=3,p=4$XOJSBfXbP5bLF/anAcierA$ee9/Of+a7/UbpOlXBvUufhJ64GYqVWM6LI4SS1BTVxc',
        N'管理员',
        N'admin',
        N'active'
    );
END;
GO
