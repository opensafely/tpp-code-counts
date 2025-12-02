-- Count ICD10 codes from ONS Deaths data
-- Counts primary cause (icd10u) and contributing causes (ICD10001-ICD10015) separately
-- Uses only the first death record per patient (by earliest dod, then by icd10u for ties - which is what ehrql does)
-- Grouped by financial year, counts rounded to nearest 10 (or "<15" if 1-14)
-- Excludes patients with Type 1 opt-out

WITH first_record_per_patient AS (
    -- Get only the first death record per patient, excluding T1OO patients
    SELECT *
    FROM (
        SELECT
            Patient_ID,
            dod,
            LTRIM(RTRIM(icd10u)) AS icd10_code,
            LTRIM(RTRIM(ICD10001)) AS ICD10001,
            LTRIM(RTRIM(ICD10002)) AS ICD10002,
            LTRIM(RTRIM(ICD10003)) AS ICD10003,
            LTRIM(RTRIM(ICD10004)) AS ICD10004,
            LTRIM(RTRIM(ICD10005)) AS ICD10005,
            LTRIM(RTRIM(ICD10006)) AS ICD10006,
            LTRIM(RTRIM(ICD10007)) AS ICD10007,
            LTRIM(RTRIM(ICD10008)) AS ICD10008,
            LTRIM(RTRIM(ICD10009)) AS ICD10009,
            LTRIM(RTRIM(ICD10010)) AS ICD10010,
            LTRIM(RTRIM(ICD10011)) AS ICD10011,
            LTRIM(RTRIM(ICD10012)) AS ICD10012,
            LTRIM(RTRIM(ICD10013)) AS ICD10013,
            LTRIM(RTRIM(ICD10014)) AS ICD10014,
            LTRIM(RTRIM(ICD10015)) AS ICD10015,
            ROW_NUMBER() OVER (
                PARTITION BY Patient_ID
                ORDER BY dod ASC, icd10u ASC
            ) AS rownum
        FROM ONS_Deaths ons
        WHERE NOT EXISTS (
            SELECT 1 FROM PatientsWithTypeOneDissent p WHERE p.Patient_ID = ons.Patient_ID
        )
    ) t
    WHERE t.rownum = 1
),
death_codes AS (
    -- Unpivot all ICD10 codes with their type (primary vs contributing)
    SELECT Patient_ID, dod, icd10_code, 'primary' AS code_type FROM first_record_per_patient WHERE icd10_code IS NOT NULL AND icd10_code <> ''
    UNION ALL
    SELECT Patient_ID, dod, ICD10001, 'contributing' FROM first_record_per_patient WHERE ICD10001 IS NOT NULL AND ICD10001 <> ''
    UNION ALL
    SELECT Patient_ID, dod, ICD10002, 'contributing' FROM first_record_per_patient WHERE ICD10002 IS NOT NULL AND ICD10002 <> ''
    UNION ALL
    SELECT Patient_ID, dod, ICD10003, 'contributing' FROM first_record_per_patient WHERE ICD10003 IS NOT NULL AND ICD10003 <> ''
    UNION ALL
    SELECT Patient_ID, dod, ICD10004, 'contributing' FROM first_record_per_patient WHERE ICD10004 IS NOT NULL AND ICD10004 <> ''
    UNION ALL
    SELECT Patient_ID, dod, ICD10005, 'contributing' FROM first_record_per_patient WHERE ICD10005 IS NOT NULL AND ICD10005 <> ''
    UNION ALL
    SELECT Patient_ID, dod, ICD10006, 'contributing' FROM first_record_per_patient WHERE ICD10006 IS NOT NULL AND ICD10006 <> ''
    UNION ALL
    SELECT Patient_ID, dod, ICD10007, 'contributing' FROM first_record_per_patient WHERE ICD10007 IS NOT NULL AND ICD10007 <> ''
    UNION ALL
    SELECT Patient_ID, dod, ICD10008, 'contributing' FROM first_record_per_patient WHERE ICD10008 IS NOT NULL AND ICD10008 <> ''
    UNION ALL
    SELECT Patient_ID, dod, ICD10009, 'contributing' FROM first_record_per_patient WHERE ICD10009 IS NOT NULL AND ICD10009 <> ''
    UNION ALL
    SELECT Patient_ID, dod, ICD10010, 'contributing' FROM first_record_per_patient WHERE ICD10010 IS NOT NULL AND ICD10010 <> ''
    UNION ALL
    SELECT Patient_ID, dod, ICD10011, 'contributing' FROM first_record_per_patient WHERE ICD10011 IS NOT NULL AND ICD10011 <> ''
    UNION ALL
    SELECT Patient_ID, dod, ICD10012, 'contributing' FROM first_record_per_patient WHERE ICD10012 IS NOT NULL AND ICD10012 <> ''
    UNION ALL
    SELECT Patient_ID, dod, ICD10013, 'contributing' FROM first_record_per_patient WHERE ICD10013 IS NOT NULL AND ICD10013 <> ''
    UNION ALL
    SELECT Patient_ID, dod, ICD10014, 'contributing' FROM first_record_per_patient WHERE ICD10014 IS NOT NULL AND ICD10014 <> ''
    UNION ALL
    SELECT Patient_ID, dod, ICD10015, 'contributing' FROM first_record_per_patient WHERE ICD10015 IS NOT NULL AND ICD10015 <> ''
),
codes_with_fy AS (
    -- Calculate financial year from date of death and deduplicate per patient
    SELECT DISTINCT
        Patient_ID,
        icd10_code,
        code_type,
        -- Financial year: Apr-Mar, so Apr 2024 -> 2024-25, Mar 2024 -> 2023-24
        CASE 
            WHEN MONTH(dod) >= 4 
            THEN CAST(YEAR(dod) AS VARCHAR(4)) + '-' + RIGHT(CAST(YEAR(dod) + 1 AS VARCHAR(4)), 2)
            ELSE CAST(YEAR(dod) - 1 AS VARCHAR(4)) + '-' + RIGHT(CAST(YEAR(dod) AS VARCHAR(4)), 2)
        END AS financial_year
    FROM death_codes
    WHERE dod IS NOT NULL
),
code_counts AS (
    -- Count by financial year, code, and type
    SELECT 
        financial_year,
        icd10_code,
        SUM(CASE WHEN code_type = 'primary' THEN 1 ELSE 0 END) AS primary_count,
        SUM(CASE WHEN code_type = 'contributing' THEN 1 ELSE 0 END) AS contributing_count
    FROM codes_with_fy
    GROUP BY financial_year, icd10_code
)
SELECT 
    financial_year,
    icd10_code,
    CASE 
        WHEN primary_count = 0 THEN '0'
        WHEN primary_count < 15 THEN '<15'
        ELSE CAST(ROUND(primary_count, -1) AS VARCHAR(20))
    END AS primary_cause_count,
    CASE 
        WHEN contributing_count = 0 THEN '0'
        WHEN contributing_count < 15 THEN '<15'
        ELSE CAST(ROUND(contributing_count, -1) AS VARCHAR(20))
    END AS contributing_cause_count
FROM code_counts
WHERE primary_count > 0 OR contributing_count > 0
ORDER BY financial_year DESC, (primary_count + contributing_count) DESC, icd10_code;
