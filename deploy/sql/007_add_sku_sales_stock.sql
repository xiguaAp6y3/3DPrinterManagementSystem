IF COL_LENGTH(N'dbo.product_skus', N'sale_stock_quantity') IS NULL
BEGIN
    ALTER TABLE dbo.product_skus
    ADD sale_stock_quantity INT NOT NULL
        CONSTRAINT DF_product_skus_sale_stock_quantity DEFAULT 0;
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.check_constraints
    WHERE name = N'CK_product_skus_sale_stock_quantity'
)
BEGIN
    ALTER TABLE dbo.product_skus
    ADD CONSTRAINT CK_product_skus_sale_stock_quantity
    CHECK (sale_stock_quantity >= 0);
END;
GO

UPDATE product
SET base_price = COALESCE(price.minimum_price, 0)
FROM dbo.products AS product
OUTER APPLY (
    SELECT MIN(sku.price) AS minimum_price
    FROM dbo.product_skus AS sku
    WHERE sku.product_id = product.id
      AND sku.status = N'active'
) AS price;
GO

UPDATE product
SET sales_status = N'off_sale'
FROM dbo.products AS product
WHERE product.sales_status = N'on_sale'
  AND NOT EXISTS (
      SELECT 1
      FROM dbo.product_skus AS sku
      WHERE sku.product_id = product.id
        AND sku.status = N'active'
  );
GO

IF COL_LENGTH(N'dbo.order_items', N'fulfillment_mode') IS NULL
BEGIN
    ALTER TABLE dbo.order_items
    ADD fulfillment_mode NVARCHAR(50) NOT NULL
        CONSTRAINT DF_order_items_fulfillment_mode DEFAULT N'make_to_order';
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.check_constraints
    WHERE name = N'CK_order_items_fulfillment_mode'
)
BEGIN
    ALTER TABLE dbo.order_items
    ADD CONSTRAINT CK_order_items_fulfillment_mode
    CHECK (fulfillment_mode IN (N'in_stock', N'make_to_order'));
END;
GO
