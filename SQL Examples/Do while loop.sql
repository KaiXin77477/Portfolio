DROP TABLE IF EXISTS #TableMonthlyCounts;

DECLARE @Path NVARCHAR(MAX)
DECLARE @Counter INT = 1
DECLARE @MaxCount INT

-- Determine the maximum count (number of rows in your table list)
SELECT @MaxCount = COUNT(*)
FROM [INFRASTRUCTURE_SQL_AREA].[DFP].[DFP_data_Kay]

-- Create a temporary table to store the table list with row numbers
CREATE TABLE #TableListWithRowNumbers (
    RowNumber INT IDENTITY(1,1),
    TableName NVARCHAR(255)
)

-- Insert the table names into the temporary table with row numbers
INSERT INTO #TableListWithRowNumbers (TableName)
SELECT [Path]
FROM [INFRASTRUCTURE_SQL_AREA].[DFP].[DFP_data_Kay]

-- Create a table to store the results
CREATE TABLE #TableMonthlyCounts (
    TableName NVARCHAR(255),
    DateColumn NVARCHAR(200),
    Month_Year NVARCHAR(50),
    NumberOfRows INT
)

-- Loop through the table names and count rows
WHILE @Counter <= @MaxCount
BEGIN
    -- Get the table path at the current position
    SELECT @Path = TableName
    FROM #TableListWithRowNumbers
    WHERE RowNumber = @Counter

    -- Split the path into database, schema, and table
    DECLARE @DatabaseName NVARCHAR(255)
    DECLARE @SchemaName NVARCHAR(255)
    DECLARE @TableName NVARCHAR(255)

    SET @DatabaseName = PARSENAME(@Path, 3)  -- Assumes path is in the format "database.schema.table"
    SET @SchemaName   = PARSENAME(@Path, 2)
    SET @TableName    = PARSENAME(@Path, 1)

    -- Determine the date column based on the flag in the DateFlags table
    DECLARE @DateColumn NVARCHAR(100)
    SELECT @DateColumn = Column_Name
    FROM [INFRASTRUCTURE_SQL_AREA].[DFP].[DFP_data_Kay]
    WHERE [Path] = @Path AND Flag_for_Date = 1

    -- Construct the SQL query to count rows
    DECLARE @Something NVARCHAR(MAX)
    SET @Something = N'
        INSERT INTO #TableMonthlyCounts (TableName, DateColumn, Month_Year, NumberOfRows)
        SELECT ''' + @TableName + ''' AS TableName, ''' + @DateColumn + ''' AS DateColumn, ' + QUOTENAME(@DateColumn) + ' AS Month_Year, COUNT(*) AS NumberOfRows
        FROM ' + QUOTENAME(@DatabaseName) + '.' + QUOTENAME(@SchemaName) + '.' + QUOTENAME(@TableName) + '
        GROUP BY ' + QUOTENAME(@DateColumn)

    -- Execute the SQL query
    EXEC sp_executesql @Something

    -- Increment the counter
    SET @Counter = @Counter + 1
END

-- Clean up temporary tables
DROP TABLE #TableListWithRowNumbers

-- Select the results
--SELECT top 20 * FROM #TableMonthlyCounts

SELECT TableName, Year(Try_cast (Month_Year as date)) as 'Year', Month(Try_cast (Month_Year as date)) as 'Month', COUNT(*) as 'Count of Records'
FROM #TableMonthlyCounts
Group by  Month(Try_cast (Month_Year as date)), Year(Try_cast (Month_Year as date)),  TableName
order by TableName, Year(Try_cast (Month_Year as date)), Month(Try_cast (Month_Year as date))
