IF NOT EXISTS (SELECT 1 FROM dbo.staff_users WHERE username = N'admin')
BEGIN
    INSERT INTO dbo.staff_users (username, email, password_hash, display_name, role)
    VALUES (N'admin', N'admin@local.3dpms', N'$argon2id$v=19$m=65536,t=3,p=4$XOJSBfXbP5bLF/anAcierA$ee9/Of+a7/UbpOlXBvUufhJ64GYqVWM6LI4SS1BTVxc', N'超级管理员', N'super_admin');
END;

IF NOT EXISTS (SELECT 1 FROM dbo.product_categories WHERE name = N'默认分类')
BEGIN
    INSERT INTO dbo.product_categories (name, sort_order)
    VALUES (N'默认分类', 0);
END;

IF NOT EXISTS (SELECT 1 FROM dbo.materials WHERE name = N'PLA 黑色')
BEGIN
    INSERT INTO dbo.materials (name, material_type, brand, color, diameter, stock_weight, safe_stock_weight, unit_cost)
    VALUES (N'PLA 黑色', N'PLA', N'默认品牌', N'黑色', 1.75, 1000, 200, 0.08);
END;

IF NOT EXISTS (SELECT 1 FROM dbo.printers WHERE name = N'Printer-001')
BEGIN
    INSERT INTO dbo.printers (name, brand, model, printer_type, supported_materials, build_volume, location, status)
    VALUES (N'Printer-001', N'Bambu Lab', N'X1C', N'FDM', N'PLA,PETG,ABS', N'256x256x256', N'工位A1', N'idle');
END;

IF NOT EXISTS (SELECT 1 FROM dbo.warehouses WHERE warehouse_code = N'MAIN')
BEGIN
    INSERT INTO dbo.warehouses (warehouse_code, name, status, remark)
    VALUES (N'MAIN', N'默认仓库', N'active', N'开发初始化仓库');
END;

IF NOT EXISTS (
    SELECT 1
    FROM dbo.warehouse_locations l
    INNER JOIN dbo.warehouses w ON w.id = l.warehouse_id
    WHERE w.warehouse_code = N'MAIN' AND l.location_code = N'A-01'
)
BEGIN
    INSERT INTO dbo.warehouse_locations (warehouse_id, location_code, name, status)
    SELECT id, N'A-01', N'默认库位', N'active'
    FROM dbo.warehouses
    WHERE warehouse_code = N'MAIN';
END;
GO
