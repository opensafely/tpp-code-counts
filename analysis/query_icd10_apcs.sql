-- Count ICD10 codes from Der_Diagnosis_All in HES APC spells
-- Each code is counted only once per spell, regardless of how many episodes contain it
-- Format of Der_Diagnosis_All: "||E119 ,E780 ,J849 ||I801 ,I802 ,N179"
--   - "||" delimits episodes within a spell
--   - "," delimits codes within an episode
--   - We assume spaces may vary
-- Grouped by financial year, counts rounded to nearest 10 (or "<15" if 1-14)
-- Excludes patients with Type 1 opt-out
--
-- Note: Uses XML-based string splitting for SQL Server compatibility level 100
-- (STRING_SPLIT requires compatibility level 130+ which TPP doesn't use)

WITH apcs_filtered AS (
    -- Pre-filter APCS records excluding Type 1 opt-outs
    SELECT 
        APCS_Ident,
        Der_Financial_Year,
        -- Normalize: replace || with comma, remove spaces
        REPLACE(REPLACE(Der_Diagnosis_All, '||', ','), ' ', '') AS normalized_codes
    FROM APCS
    WHERE Der_Diagnosis_All IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM PatientsWithTypeOneDissent p 
          WHERE p.Patient_ID = APCS.Patient_ID
      )
),
spell_codes AS (
    -- Extract all codes from each spell using XML-based string splitting
    -- This approach is compatible with SQL Server 2008+ (compatibility level 100)
    SELECT DISTINCT
        a.APCS_Ident,
        a.Der_Financial_Year,
        LTRIM(RTRIM(split.code.value('.', 'VARCHAR(20)'))) AS icd10_code
    FROM apcs_filtered a
    CROSS APPLY (
        SELECT CAST('<x>' + REPLACE(a.normalized_codes, ',', '</x><x>') + '</x>' AS XML) AS xml_codes
    ) AS xml_data
    CROSS APPLY xml_data.xml_codes.nodes('/x') AS split(code)
    WHERE LTRIM(RTRIM(split.code.value('.', 'VARCHAR(20)'))) <> ''
),
code_counts AS (
    -- Count spells per code per financial year
    SELECT 
        Der_Financial_Year AS financial_year,
        icd10_code,
        COUNT(*) AS raw_count
    FROM spell_codes
    GROUP BY Der_Financial_Year, icd10_code
)
SELECT 
    financial_year,
    icd10_code,
    CASE 
        WHEN raw_count < 15 THEN '<15'
        ELSE CAST(ROUND(raw_count, -1) AS VARCHAR(20))
    END AS spell_count
FROM code_counts
WHERE raw_count > 0
ORDER BY financial_year DESC, raw_count DESC, icd10_code;