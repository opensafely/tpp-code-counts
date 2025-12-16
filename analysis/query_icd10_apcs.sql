-- Count ICD10 codes from HES APC spells
-- Each code is counted only once per spell, regardless of how many episodes contain it
-- Format of Der_Diagnosis_All: "||E119 ,E780 ,J849 ||I801 ,I802 ,N179"
--   - "||" delimits episodes within a spell
--   - "," delimits codes within an episode
--   - We assume spaces may vary
-- Outputs two independent count columns:
--   - primary_count: count of spells where this code is the primary diagnosis (from APCS_Der)
--   - secondary_count: count of spells where this code is in the secondary diagnoses (from APCS_Der)
--   - all_count: count of spells where this code appears in Der_Diagnosis_All
-- Note: A code may appear as primary but not in "all", or vice versa, or neither - we're not really sure
-- Grouped by financial year, counts rounded to nearest 10 (or "<15" if 1-14, "0" if 0)
-- Excludes patients with Type 1 opt-out
--
-- Note: Uses XML-based string splitting for SQL Server compatibility level 100
-- (STRING_SPLIT requires compatibility level 130+ which TPP doesn't use)

WITH apcs_base AS (
    -- Base APCS records excluding Type 1 opt-outs
    SELECT
        apcs.APCS_Ident,
        -- Normalize Der_Financial_Year to canonical form YYYY-YY
        CASE 
            WHEN apcs.Der_Financial_Year IS NULL OR LTRIM(RTRIM(apcs.Der_Financial_Year)) = '' THEN NULL
            WHEN LTRIM(RTRIM(apcs.Der_Financial_Year)) LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]' THEN LTRIM(RTRIM(apcs.Der_Financial_Year))
            WHEN LTRIM(RTRIM(apcs.Der_Financial_Year)) LIKE '[0-9][0-9][0-9][0-9]/[0-9][0-9]' THEN REPLACE(LTRIM(RTRIM(apcs.Der_Financial_Year)), '/', '-')
            WHEN LTRIM(RTRIM(apcs.Der_Financial_Year)) LIKE '[0-9][0-9][0-9][0-9][0-9][0-9]' THEN SUBSTRING(LTRIM(RTRIM(apcs.Der_Financial_Year)),1,4) + '-' + SUBSTRING(LTRIM(RTRIM(apcs.Der_Financial_Year)),5,2)
            ELSE LTRIM(RTRIM(apcs.Der_Financial_Year))
        END AS Der_Financial_Year,
        LTRIM(RTRIM(der.Spell_Primary_Diagnosis)) as primary_diagnosis,
        LTRIM(RTRIM(der.Spell_Secondary_Diagnosis)) as secondary_diagnosis,
        -- Normalize: replace || with comma, remove spaces
        REPLACE(REPLACE(apcs.Der_Diagnosis_All, '||', ','), ' ', '') AS normalized_codes
    FROM APCS as apcs
    LEFT JOIN APCS_Der AS der -- 1:1 relationship between apcs and apcs_der as per ehrql docs
    ON apcs.APCS_Ident = der.APCS_Ident
    WHERE NOT EXISTS (
          SELECT 1 FROM PatientsWithTypeOneDissent p
          WHERE p.Patient_ID = apcs.Patient_ID
      )
    AND Der_Activity_Month >= '202304'

    UNION ALL

    SELECT
        apcs.APCS_Ident,
        -- Normalize Der_Financial_Year to canonical form YYYY-YY
        CASE 
            WHEN apcs.Der_Financial_Year IS NULL OR LTRIM(RTRIM(apcs.Der_Financial_Year)) = '' THEN NULL
            WHEN LTRIM(RTRIM(apcs.Der_Financial_Year)) LIKE '[0-9][0-9][0-9][0-9]-[0-9][0-9]' THEN LTRIM(RTRIM(apcs.Der_Financial_Year))
            WHEN LTRIM(RTRIM(apcs.Der_Financial_Year)) LIKE '[0-9][0-9][0-9][0-9]/[0-9][0-9]' THEN REPLACE(LTRIM(RTRIM(apcs.Der_Financial_Year)), '/', '-')
            WHEN LTRIM(RTRIM(apcs.Der_Financial_Year)) LIKE '[0-9][0-9][0-9][0-9][0-9][0-9]' THEN SUBSTRING(LTRIM(RTRIM(apcs.Der_Financial_Year)),1,4) + '-' + SUBSTRING(LTRIM(RTRIM(apcs.Der_Financial_Year)),5,2)
            ELSE LTRIM(RTRIM(apcs.Der_Financial_Year))
        END AS Der_Financial_Year,
        LTRIM(RTRIM(der.Spell_Primary_Diagnosis)) as primary_diagnosis,
        LTRIM(RTRIM(der.Spell_Secondary_Diagnosis)) as secondary_diagnosis,
        -- Normalize: replace || with comma, remove spaces
        REPLACE(REPLACE(apcs.Der_Diagnosis_All, '||', ','), ' ', '') AS normalized_codes
    FROM APCS_ARCHIVED as apcs
    LEFT JOIN APCS_Der_ARCHIVED AS der -- 1:1 relationship between apcs and apcs_der as per ehrql docs
    ON apcs.APCS_Ident = der.APCS_Ident
    WHERE NOT EXISTS (
          SELECT 1 FROM PatientsWithTypeOneDissent p
          WHERE p.Patient_ID = apcs.Patient_ID
      )
    AND Der_Activity_Month < '202304'
),
-- Extract all codes from Der_Diagnosis_All
all_codes AS (
    SELECT DISTINCT
        a.APCS_Ident,
        a.Der_Financial_Year,
        LTRIM(RTRIM(split.code.value('.', 'VARCHAR(20)'))) AS icd10_code
    FROM apcs_base a
    CROSS APPLY (
        SELECT CAST('<x>' + REPLACE(a.normalized_codes, ',', '</x><x>') + '</x>' AS XML) AS xml_codes
    ) AS xml_data
    CROSS APPLY xml_data.xml_codes.nodes('/x') AS split(code)
    WHERE a.normalized_codes IS NOT NULL
      AND a.normalized_codes <> ''
      AND LTRIM(RTRIM(split.code.value('.', 'VARCHAR(20)'))) <> ''
),
-- Extract primary diagnosis codes
primary_codes AS (
    SELECT DISTINCT
        APCS_Ident,
        Der_Financial_Year,
        primary_diagnosis AS icd10_code
    FROM apcs_base
    WHERE primary_diagnosis IS NOT NULL
      AND primary_diagnosis <> ''
),
-- Extract secondary diagnosis codes
secondary_codes AS (
    SELECT DISTINCT
        APCS_Ident,
        Der_Financial_Year,
        secondary_diagnosis AS icd10_code
    FROM apcs_base
    WHERE secondary_diagnosis IS NOT NULL
      AND secondary_diagnosis <> ''
),
-- Get all unique codes from either source
all_unique_codes AS (
    SELECT Der_Financial_Year, icd10_code FROM all_codes
    UNION
    SELECT Der_Financial_Year, icd10_code FROM primary_codes
    UNION
    SELECT Der_Financial_Year, icd10_code FROM secondary_codes
),
-- Count "all" occurrences per code per financial year
all_counts AS (
    SELECT
        Der_Financial_Year AS financial_year,
        icd10_code,
        COUNT(*) AS raw_count
    FROM all_codes
    GROUP BY Der_Financial_Year, icd10_code
),
-- Count "primary" occurrences per code per financial year
primary_counts AS (
    SELECT
        Der_Financial_Year AS financial_year,
        icd10_code,
        COUNT(*) AS raw_count
    FROM primary_codes
    GROUP BY Der_Financial_Year, icd10_code
),
-- Count "secondary" occurrences per code per financial year
secondary_counts AS (
    SELECT
        Der_Financial_Year AS financial_year,
        icd10_code,
        COUNT(*) AS raw_count
    FROM secondary_codes
    GROUP BY Der_Financial_Year, icd10_code
),
-- Combine counts
combined_counts AS (
    SELECT
        u.Der_Financial_Year AS financial_year,
        u.icd10_code,
        ISNULL(p.raw_count, 0) AS primary_raw_count,
        ISNULL(s.raw_count, 0) AS secondary_raw_count,
        ISNULL(a.raw_count, 0) AS all_raw_count
    FROM all_unique_codes u
    LEFT JOIN primary_counts p ON u.Der_Financial_Year = p.financial_year AND u.icd10_code = p.icd10_code
    LEFT JOIN secondary_counts s ON u.Der_Financial_Year = s.financial_year AND u.icd10_code = s.icd10_code
    LEFT JOIN all_counts a ON u.Der_Financial_Year = a.financial_year AND u.icd10_code = a.icd10_code
)
SELECT
    financial_year,
    icd10_code,
    CASE
        WHEN primary_raw_count = 0 THEN '0'
        WHEN primary_raw_count < 15 THEN '<15'
        ELSE CAST(ROUND(primary_raw_count, -1) AS VARCHAR(20))
    END AS primary_count,
    CASE
        WHEN secondary_raw_count = 0 THEN '0'
        WHEN secondary_raw_count < 15 THEN '<15'
        ELSE CAST(ROUND(secondary_raw_count, -1) AS VARCHAR(20))
    END AS secondary_count,
    CASE
        WHEN all_raw_count = 0 THEN '0'
        WHEN all_raw_count < 15 THEN '<15'
        ELSE CAST(ROUND(all_raw_count, -1) AS VARCHAR(20))
    END AS all_count
FROM combined_counts
WHERE primary_raw_count > 0 OR secondary_raw_count > 0 OR all_raw_count > 0
ORDER BY financial_year DESC, all_raw_count DESC, icd10_code
