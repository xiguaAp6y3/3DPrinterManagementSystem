USE AgentOrder;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.staff_users WHERE username = N'admin')
BEGIN
    INSERT INTO dbo.staff_users (username, password_hash, display_name, role)
    VALUES (N'admin', N'CHANGE_ME_HASH', N'管理员', N'admin');
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
GO
