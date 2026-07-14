IF COL_LENGTH('dbo.print_tasks', 'planned_quantity') IS NULL
BEGIN
    ALTER TABLE dbo.print_tasks
        ADD planned_quantity INT NOT NULL
            CONSTRAINT DF_print_tasks_planned_quantity DEFAULT 1 WITH VALUES;
END
