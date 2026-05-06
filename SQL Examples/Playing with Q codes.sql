/****** Script for SelectTopNRows command from SSMS  ******/
SELECT TOP (1000) [Admission date]
      ,[Patient ID]
      ,[Diagnosis All]
  FROM [Health].[dbo].[Random Patient Diag codes]
  where [Diagnosis All] like '%Q2%'


  WITH DiagSplit AS (
    SELECT 
        [Patient ID], 
        YEAR([Admission date]) AS [YEAR], 
        [Diagnosis All], 
        S.Item AS Code
    FROM 
        [Health].[dbo].[Random Patient Diag codes]
    CROSS APPLY 
        dbo.SplitString([Diagnosis All], ';') AS S
),
DistinctQCodes AS (
    SELECT DISTINCT
        [Patient ID],
        [Year],
        [Diagnosis All],
        Code
    FROM
        DiagSplit
    WHERE 
        Code LIKE 'Q2%'
)
SELECT 
    [Patient ID],
    [Year],
    [Diagnosis All],
    STRING_AGG(Code, ';') WITHIN GROUP (ORDER BY Code) AS [Q2_codes]
FROM 
    DistinctQCodes
GROUP BY 
    [Patient ID], [Year], [Diagnosis All];

----------------------------------------------------------------------------------------------------------------------------------
WITH CTE_DiagSplit AS (
    SELECT 
        [Patient ID],
        TRIM(Item) AS Code,
        YEAR([Admission date]) AS [YEAR]
    FROM 
        [Health].[dbo].[Random Patient Diag codes]
    CROSS APPLY 
        dbo.SplitString([Diagnosis All], ';')
),
CTE_FilteredDiagCodes AS (
    SELECT DISTINCT
        [Patient ID],
        Code,
        [Year]
    FROM
        CTE_DiagSplit
    WHERE
        Code LIKE 'Q2%'
),
CTE_AggregatedCodes AS (
    SELECT
        [Patient ID],
        STRING_AGG(Code, ';') WITHIN GROUP (ORDER BY Code) AS [Q numbers],
        MIN([Year]) AS [Year when first seen]
    FROM
        CTE_FilteredDiagCodes
    GROUP BY
        [Patient ID]
)
SELECT 
    [Patient ID],
    [Q numbers],
    [Year when first seen]
FROM 
    CTE_AggregatedCodes
ORDER BY
    [Patient ID];

-------------------------------------------------------------------------------------
WITH CTE_SumDiagCodes AS (
    SELECT
        SUM(CASE WHEN [Diagnosis All] LIKE '%Q142%' THEN 1 ELSE 0 END) AS 'Q142',
        SUM(CASE WHEN [Diagnosis All] LIKE '%Q215%' THEN 1 ELSE 0 END) AS 'Q215',
        SUM(CASE WHEN [Diagnosis All] LIKE '%Q286%' THEN 1 ELSE 0 END) AS 'Q286',
        SUM(CASE WHEN [Diagnosis All] LIKE '%Q297%' THEN 1 ELSE 0 END) AS 'Q297',
        SUM(CASE WHEN [Diagnosis All] LIKE '%Q278%' THEN 1 ELSE 0 END) AS 'Q278',
        SUM(CASE WHEN [Diagnosis All] LIKE '%Q247%' THEN 1 ELSE 0 END) AS 'Q247',
        SUM(CASE WHEN [Diagnosis All] LIKE '%Q276%' THEN 1 ELSE 0 END) AS 'Q276'
    FROM [Health].[dbo].[Random Patient Diag codes]
)
SELECT 'Q142' AS [Q number], Q142 AS [No of patients] FROM CTE_SumDiagCodes
UNION ALL
SELECT 'Q215', Q215 FROM CTE_SumDiagCodes
UNION ALL
SELECT 'Q286', Q286 FROM CTE_SumDiagCodes
UNION ALL
SELECT 'Q297', Q297 FROM CTE_SumDiagCodes
UNION ALL
SELECT 'Q278', Q278 FROM CTE_SumDiagCodes
UNION ALL
SELECT 'Q247', Q247 FROM CTE_SumDiagCodes
UNION ALL
SELECT 'Q276', Q276 FROM CTE_SumDiagCodes;

-------------------------------------------------------------------------------------------------------
---------------------- This is horrible long list - don't use

--WITH CTE_SumDiagCodes AS (
--    SELECT YEAR([Admission date]) AS [Year],
--        SUM(CASE WHEN [Diagnosis All] LIKE '%Q142%' THEN 1 ELSE 0 END) AS 'Q142',
--        SUM(CASE WHEN [Diagnosis All] LIKE '%Q215%' THEN 1 ELSE 0 END) AS 'Q215',
--        SUM(CASE WHEN [Diagnosis All] LIKE '%Q286%' THEN 1 ELSE 0 END) AS 'Q286',
--        SUM(CASE WHEN [Diagnosis All] LIKE '%Q297%' THEN 1 ELSE 0 END) AS 'Q297',
--        SUM(CASE WHEN [Diagnosis All] LIKE '%Q278%' THEN 1 ELSE 0 END) AS 'Q278',
--        SUM(CASE WHEN [Diagnosis All] LIKE '%Q247%' THEN 1 ELSE 0 END) AS 'Q247',
--        SUM(CASE WHEN [Diagnosis All] LIKE '%Q276%' THEN 1 ELSE 0 END) AS 'Q276'
--    FROM [Health].[dbo].[Random Patient Diag codes]
--	GROUP BY YEAR([Admission date])
--)
--SELECT 'Q142' AS [Q number], [Year], Q142 AS [No of patients] FROM CTE_SumDiagCodes
--UNION ALL
--SELECT 'Q215', [Year], Q215 FROM CTE_SumDiagCodes
--UNION ALL
--SELECT 'Q286', [Year], Q286 FROM CTE_SumDiagCodes
--UNION ALL
--SELECT 'Q297', [Year], Q297 FROM CTE_SumDiagCodes
--UNION ALL
--SELECT 'Q278', [Year], Q278 FROM CTE_SumDiagCodes
--UNION ALL
--SELECT 'Q247', [Year], Q247 FROM CTE_SumDiagCodes
--UNION ALL
--SELECT 'Q276', [Year], Q276 FROM CTE_SumDiagCodes
--order by [Year], [Q number];

----------------------------------------------------------------------------------------------------
------------------ Displays years down Left hand column, and Q codes along the top
    SELECT YEAR([Admission date]) AS [Year],
        SUM(CASE WHEN [Diagnosis All] LIKE '%Q142%' THEN 1 ELSE 0 END) AS 'Q142',
        SUM(CASE WHEN [Diagnosis All] LIKE '%Q215%' THEN 1 ELSE 0 END) AS 'Q215',
        SUM(CASE WHEN [Diagnosis All] LIKE '%Q286%' THEN 1 ELSE 0 END) AS 'Q286',
        SUM(CASE WHEN [Diagnosis All] LIKE '%Q297%' THEN 1 ELSE 0 END) AS 'Q297',
        SUM(CASE WHEN [Diagnosis All] LIKE '%Q278%' THEN 1 ELSE 0 END) AS 'Q278',
        SUM(CASE WHEN [Diagnosis All] LIKE '%Q247%' THEN 1 ELSE 0 END) AS 'Q247',
        SUM(CASE WHEN [Diagnosis All] LIKE '%Q276%' THEN 1 ELSE 0 END) AS 'Q276'
    FROM [Health].[dbo].[Random Patient Diag codes]
	where YEAR([Admission date]) > '1999'
	GROUP BY YEAR([Admission date])
	order by Year([admission date])

---------------------------------------------------------------------------------------------
SELECT [Q Number], [2000], [2021], [2022], [2023], [2024] 
FROM
( Select [Diagnosis All], [Q number], YEAR([admission date])
   FROM [Health].[dbo].[Random Patient Diag codes]
) as tpvt
pivot
(
			SUM(CASE WHEN [Diagnosis All] LIKE '%Q142%' THEN 1 ELSE 0 END) AS 'Q142',
			SUM(CASE WHEN [Diagnosis All] LIKE '%Q215%' THEN 1 ELSE 0 END) AS 'Q215',
			SUM(CASE WHEN [Diagnosis All] LIKE '%Q286%' THEN 1 ELSE 0 END) AS 'Q286',
			SUM(CASE WHEN [Diagnosis All] LIKE '%Q297%' THEN 1 ELSE 0 END) AS 'Q297',
			SUM(CASE WHEN [Diagnosis All] LIKE '%Q278%' THEN 1 ELSE 0 END) AS 'Q278',
			SUM(CASE WHEN [Diagnosis All] LIKE '%Q247%' THEN 1 ELSE 0 END) AS 'Q247',
			SUM(CASE WHEN [Diagnosis All] LIKE '%Q276%' THEN 1 ELSE 0 END) AS 'Q276'
		for [Q number] in ([Q142], [Q215], [Q286], [Q297], [Q278], [Q247], [Q276])
		)  AS PVT




