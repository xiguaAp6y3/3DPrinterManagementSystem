CREATE OR ALTER TRIGGER dbo.trg_materials_no_negative_stock
ON dbo.materials
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS (
        SELECT 1
        FROM inserted
        WHERE stock_weight < 0
           OR reserved_weight < 0
           OR reserved_weight > stock_weight
    )
    BEGIN
        THROW 50001, N'Material stock is invalid.', 1;
    END
END;
GO

CREATE OR ALTER TRIGGER dbo.trg_printers_status_log
ON dbo.printers
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO dbo.printer_status_logs (
        printer_id,
        from_status,
        to_status,
        changed_by,
        created_at
    )
    SELECT
        i.id,
        d.status,
        i.status,
        TRY_CAST(SESSION_CONTEXT(N'staff_user_id') AS BIGINT),
        DATEADD(HOUR, 8, SYSUTCDATETIME())
    FROM inserted i
    INNER JOIN deleted d ON i.id = d.id
    WHERE ISNULL(i.status, N'') <> ISNULL(d.status, N'');
END;
GO

CREATE OR ALTER TRIGGER dbo.trg_production_schedule_items_no_overlap
ON dbo.production_schedule_items
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        INNER JOIN dbo.production_schedule_items s
            ON s.printer_id = i.printer_id
           AND s.id <> i.id
           AND s.status IN (N'scheduled', N'locked', N'in_progress')
           AND i.status IN (N'scheduled', N'locked', N'in_progress')
           AND i.scheduled_start_at < s.scheduled_end_at
           AND i.scheduled_end_at > s.scheduled_start_at
    )
    BEGIN
        THROW 50002, N'Printer schedule time overlaps.', 1;
    END
END;
GO

CREATE OR ALTER TRIGGER dbo.trg_orders_payment_confirm_log
ON dbo.orders
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO dbo.operation_logs (
        operator_id,
        operation_type,
        target_table,
        target_id,
        before_data,
        after_data,
        remark,
        created_at
    )
    SELECT
        i.payment_confirmed_by,
        N'order_payment_confirmed',
        N'orders',
        i.id,
        CONCAT(N'payment_status=', d.payment_status),
        CONCAT(N'payment_status=', i.payment_status),
        N'订单人工收款确认',
        DATEADD(HOUR, 8, SYSUTCDATETIME())
    FROM inserted i
    INNER JOIN deleted d ON i.id = d.id
    WHERE d.payment_status <> N'confirmed'
      AND i.payment_status = N'confirmed';
END;
GO
