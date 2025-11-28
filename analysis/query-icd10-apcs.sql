-- Count ICD10 codes from Der_Diagnosis_All in HES APC spells
-- Each code is counted only once per spell, regardless of how many episodes contain it
-- Format of Der_Diagnosis_All: "||E119 ,E780 ,J849 ||I801 ,I802 ,N179"
--   - "||" delimits episodes within a spell
--   - "," delimits codes within an episode
--   - We assume spaces may vary
-- Grouped by financial year, counts rounded to nearest 10 (or "<15" if 1-14)
-- Excludes patients with Type 1 opt-out

WITH spell_codes AS (
    -- Extract all codes from each spell, removing duplicates per spell
    SELECT DISTINCT
        APCS.APCS_Ident,
        APCS.Der_Financial_Year,
        LTRIM(RTRIM(code.value)) AS icd10_code
    FROM APCS
    CROSS APPLY STRING_SPLIT(
        -- Replace episode delimiters with commas to create uniform comma-separated list
        REPLACE(REPLACE(Der_Diagnosis_All, '||', ','), ' ', ''),
        ','
    ) AS code
    WHERE LTRIM(RTRIM(code.value)) <> ''
      AND Der_Diagnosis_All IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM PatientsWithTypeOneDissent p 
          WHERE p.Patient_ID = APCS.Patient_ID
      )
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