# Prefix Matching Issues Report

**Generated**: 2026-03-04 12:11:38

## ⚠️  Prefix Matching Changes Between Cohort Extractor and ehrQL

In Cohort Extractor (the old framework), prefix matching was applied by default when querying the primary and secondary diagnosis fields in HES APCS data. This means that a code like `E10` would automatically match `E10`, `E100`, `E101`, `E102`, etc.

**In ehrQL, prefix matching is NOT automatically applied to these fields.** 

There are two sources of potential error from this:
1. 3-character ICD10 codes get padded with an X in hospital data - so A33 becomes A33X in the data
2. Some 4 character ICD10 codes have an optional 5th character modifier

For each affected project and each affected codelist, this report shows how many primary diagnosis events, in the 24/25 financial year, would be matched under three scenarios:
1. Just using the codes in the codelist
2. Using the codes in the codelist AND any 'X'-padded codes
3. Match any code that starts with a codelist code (i.e., prefix matching)

## Summary

**15 projects** may be affected by this change.

### Affected Projects:

| Project # | Project Name | Repository |
|-----------|-------------|-----------|
|  |  | [COMPARES-vaccines](https://github.com/opensafely/COMPARES-vaccines) |
|  |  | [COMPARES-vaccines-Autumn-2024](https://github.com/opensafely/COMPARES-vaccines-Autumn-2024) |
|  |  | [JAKi-hosp](https://github.com/opensafely/JAKi-hosp) |
|  |  | [NeurodegenerativeDiseaseBurden](https://github.com/opensafely/NeurodegenerativeDiseaseBurden) |
| 196 | [OpenPREGnosis: Developing an Open Algorithm to Identify Pregnancy Episodes and Outcomes in OpenSAFELY](https://jobs.opensafely.org/openpregnosis-developing-an-open-algorithm-to-identify-pregnancy-episodes-and-outcomes-in-opensafely) | [OpenPregnosis](https://github.com/opensafely/OpenPregnosis) |
| 22 | [Investigating the effectiveness of the COVID-19 vaccination programme in the UK](https://jobs.opensafely.org/investigating-the-effectiveness-of-the-covid-19-vaccination-programme-in-the-uk) | [comparative-booster-spring2023](https://github.com/opensafely/comparative-booster-spring2023) |
| 161 | [COVID-19 Collateral (Project continuation of approved project no 95)](https://jobs.opensafely.org/covid-19-collateral-project-continuation-of-approved-project-no-95) | [covid_collateral_hf_update](https://github.com/opensafely/covid_collateral_hf_update) |
| 176 | [Comparing Disparities in RSV, Influenza and Covid-19](https://jobs.opensafely.org/comparing-disparities-in-rsv-influenza-and-covid-19) | [disparities-comparison](https://github.com/opensafely/disparities-comparison) |
| 175 | [Implications of metformin for Long COVID](https://jobs.opensafely.org/implications-of-metformin-for-long-covid) | [metformin_covid](https://github.com/opensafely/metformin_covid) |
|  |  | [post-covid-vax-autoimmune](https://github.com/opensafely/post-covid-vax-autoimmune) |
| 172 | [Impact and inequalities of winter pressures in primary care: providing the evidence base for mitigation strategies](https://jobs.opensafely.org/impact-and-inequalities-of-winter-pressures-in-primary-care-providing-the-evidence-base-for-mitigation-strategies) | [post-infection-outcomes](https://github.com/opensafely/post-infection-outcomes) |
| 91 | [Coverage, effectiveness and safety of neutralising monoclonal antibodies or antivirals for non-hospitalised patients with COVID-19](https://jobs.opensafely.org/coverage-effectiveness-and-safety-of-neutralising-monoclonal-antibodies-or-antivirals-for-non-hospitalised-patients-with-covid-19) | [prophy_effects_Sotro_Molnup](https://github.com/opensafely/prophy_effects_Sotro_Molnup) |
| 153 | [What was the impact of COVID-19 on mortality related to venous thromboembolism in England?](https://jobs.opensafely.org/what-was-the-impact-of-covid-19-on-mortality-related-to-venous-thromboembolism-in-england) | [vte-diagnoses-and-deaths](https://github.com/opensafely/vte-diagnoses-and-deaths) |
| 172 | [Impact and inequalities of winter pressures in primary care: providing the evidence base for mitigation strategies](https://jobs.opensafely.org/impact-and-inequalities-of-winter-pressures-in-primary-care-providing-the-evidence-base-for-mitigation-strategies) | [winter_pressures_inequalities](https://github.com/opensafely/winter_pressures_inequalities) |
|  |  | [wp3_respiratory_virus_timeseries](https://github.com/opensafely/wp3_respiratory_virus_timeseries) |

---

## COMPARES-vaccines

### Affected Codelists:

- **`/opensafely/erythema-multiforme-icd-10/327fb94f/`**
  - Just the codelist: 270
  - With X-padded codes: 270 (0% increase)
  - With prefix matching: 420 (56% increase)
- **`/opensafely/heavy-menstrual-bleeding-icd-10/0624f81a/`**
  - Just the codelist: 13,670
  - With X-padded codes: 13,670 (0% increase)
  - With prefix matching: 14,870 (9% increase)
- **`/user/RochelleKnight/stroke_isch_icd10/278d734e/`**
  - Just the codelist: 51,660
  - With X-padded codes: 53,190 (3% increase)
  - With prefix matching: 53,190 (3% increase)
- **`/user/elsie_horne/dvt_icvt_icd10/30a4dcad/`**
  - Just the codelist: 160
  - With X-padded codes: 560 (250% increase)
  - With prefix matching: 560 (250% increase)
- **`/user/elsie_horne/other_arterial_embolism_icd10/463adc5d/`**
  - Just the codelist: 0
  - With X-padded codes: 0
  - With prefix matching: 3,300
- **`/user/elsie_horne/portal_vein_thrombosis_icd10/22606950/`**
  - Just the codelist: 0
  - With X-padded codes: 310
  - With prefix matching: 310

**Total for COMPARES-vaccines:**
- Exact match: 65,760 events
- With X-padded codes: 68,000 events
- With prefix matching: 72,650 events

## COMPARES-vaccines-Autumn-2024

### Affected Codelists:

- **`/opensafely/erythema-multiforme-icd-10/327fb94f/`**
  - Just the codelist: 270
  - With X-padded codes: 270 (0% increase)
  - With prefix matching: 420 (56% increase)
- **`/opensafely/heavy-menstrual-bleeding-icd-10/0624f81a/`**
  - Just the codelist: 13,670
  - With X-padded codes: 13,670 (0% increase)
  - With prefix matching: 14,870 (9% increase)
- **`/user/RochelleKnight/stroke_isch_icd10/278d734e/`**
  - Just the codelist: 51,660
  - With X-padded codes: 53,190 (3% increase)
  - With prefix matching: 53,190 (3% increase)
- **`/user/elsie_horne/dvt_icvt_icd10/30a4dcad/`**
  - Just the codelist: 160
  - With X-padded codes: 560 (250% increase)
  - With prefix matching: 560 (250% increase)
- **`/user/elsie_horne/other_arterial_embolism_icd10/463adc5d/`**
  - Just the codelist: 0
  - With X-padded codes: 0
  - With prefix matching: 3,300
- **`/user/elsie_horne/portal_vein_thrombosis_icd10/22606950/`**
  - Just the codelist: 0
  - With X-padded codes: 310
  - With prefix matching: 310

**Total for COMPARES-vaccines-Autumn-2024:**
- Exact match: 65,760 events
- With X-padded codes: 68,000 events
- With prefix matching: 72,650 events

## JAKi-hosp

### Affected Codelists:

- **`/user/RochelleKnight/prostate_cancer_icd10/6b27d648/`**
  - Just the codelist: 0
  - With X-padded codes: 58,660
  - With prefix matching: 58,660

**Total for JAKi-hosp:**
- Exact match: 0 events
- With X-padded codes: 58,660 events
- With prefix matching: 58,660 events

## NeurodegenerativeDiseaseBurden

### Affected Codelists:

- **`/user/RochelleKnight/prostate_cancer_icd10/6b27d648/`**
  - Just the codelist: 0
  - With X-padded codes: 58,660
  - With prefix matching: 58,660

**Total for NeurodegenerativeDiseaseBurden:**
- Exact match: 0 events
- With X-padded codes: 58,660 events
- With prefix matching: 58,660 events

## OpenPregnosis

### Affected Codelists:

- **`/user/paolomazzone/openpregnosis-icd_10-blighted-ovum-codes_v1/0d5ad4dd/`**
  - Just the codelist: 450
  - With X-padded codes: 450 (0% increase)
  - With prefix matching: 10,330 (2196% increase)

**Total for OpenPregnosis:**
- Exact match: 450 events
- With X-padded codes: 450 events
- With prefix matching: 10,330 events

## comparative-booster-spring2023

### Affected Codelists:

- **`/opensafely/fractures/086e92fc/`**
  - Just the codelist: 6,830
  - With X-padded codes: 6,830 (0% increase)
  - With prefix matching: 159,000 (2228% increase)

**Total for comparative-booster-spring2023:**
- Exact match: 6,830 events
- With X-padded codes: 6,830 events
- With prefix matching: 159,000 events

## covid_collateral_hf_update

### Affected Codelists:

- **`/opensafely/cardiovascular-secondary-care/20b63bd4/`**
  - Just the codelist: 402,180
  - With X-padded codes: 426,860 (6% increase)
  - With prefix matching: 493,570 (23% increase)
- **`/user/emilyherrett/heart-failure/6dd2440f/`**
  - Just the codelist: 55,580
  - With X-padded codes: 55,580 (0% increase)
  - With prefix matching: 57,310 (3% increase)

**Total for covid_collateral_hf_update:**
- Exact match: 457,760 events
- With X-padded codes: 482,440 events
- With prefix matching: 550,880 events

## disparities-comparison

### Affected Codelists:

- **`/opensafely/acute-respiratory-illness-secondary-care/680e1eda/`**
  - Just the codelist: 43,290
  - With X-padded codes: 44,390 (3% increase)
  - With prefix matching: 51,990 (20% increase)
- **`/opensafely/influenza-identification-secondary-care/3cfe5a71/`**
  - Just the codelist: 28,690
  - With X-padded codes: 28,930 (1% increase)
  - With prefix matching: 28,930 (1% increase)
- **`/opensafely/respiratory-virus-unspecified-identification-secondary-care/4d1c083b/`**
  - Just the codelist: 165,230
  - With X-padded codes: 166,330 (1% increase)
  - With prefix matching: 170,250 (3% increase)
- **`/opensafely/rsv-identification-secondary-care/560dcda6/`**
  - Just the codelist: 22,710
  - With X-padded codes: 22,710 (0% increase)
  - With prefix matching: 24,140 (6% increase)

**Total for disparities-comparison:**
- Exact match: 259,920 events
- With X-padded codes: 262,360 events
- With prefix matching: 275,310 events

## metformin_covid

### Affected Codelists:

- **`/bristol/fractures/565037f8/`**
  - Just the codelist: 4,290
  - With X-padded codes: 4,290 (0% increase)
  - With prefix matching: 169,910 (3861% increase)
- **`/opensafely/condition-advanced-decompensated-cirrhosis-of-the-liver-and-associated-conditions-icd-10/00e40554/`**
  - Just the codelist: 22,370
  - With X-padded codes: 26,520 (19% increase)
  - With prefix matching: 26,960 (21% increase)
- **`/opensafely/type-1-diabetes-secondary-care/2020-09-27/`**
  - Just the codelist: 0
  - With X-padded codes: 0
  - With prefix matching: 14,470
- **`/user/RochelleKnight/prostate_cancer_icd10/6b27d648/`**
  - Just the codelist: 0
  - With X-padded codes: 58,660
  - With prefix matching: 58,660
- **`/user/RochelleKnight/stroke_isch_icd10/278d734e/`**
  - Just the codelist: 51,660
  - With X-padded codes: 53,190 (3% increase)
  - With prefix matching: 53,190 (3% increase)
- **`/user/elsie_horne/bmi_obesity_icd10/6e55767e/`**
  - Just the codelist: 0
  - With X-padded codes: 0
  - With prefix matching: 5,160
- **`/user/elsie_horne/cancer_icd10/55460349/`**
  - Just the codelist: 0
  - With X-padded codes: 154,840
  - With prefix matching: 775,070
- **`/user/elsie_horne/ckd_icd10/0cca69a0/`**
  - Just the codelist: 237,240
  - With X-padded codes: 240,120 (1% increase)
  - With prefix matching: 273,970 (15% increase)
- **`/user/elsie_horne/copd_icd10/5aab8335/`**
  - Just the codelist: 0
  - With X-padded codes: 1,270
  - With prefix matching: 60,550
- **`/user/elsie_horne/dementia_icd10/2df21cb7/`**
  - Just the codelist: 5,600
  - With X-padded codes: 7,540 (35% increase)
  - With prefix matching: 10,980 (96% increase)
- **`/user/elsie_horne/dementia_vascular_icd10/27c5e93c/`**
  - Just the codelist: 0
  - With X-padded codes: 0
  - With prefix matching: 1,170
- **`/user/elsie_horne/dvt_icvt_icd10/30a4dcad/`**
  - Just the codelist: 160
  - With X-padded codes: 560 (250% increase)
  - With prefix matching: 560 (250% increase)
- **`/user/elsie_horne/hypertension_icd10/1a48296e/`**
  - Just the codelist: 0
  - With X-padded codes: 22,520
  - With prefix matching: 23,940
- **`/user/elsie_horne/other_arterial_embolism_icd10/463adc5d/`**
  - Just the codelist: 0
  - With X-padded codes: 0
  - With prefix matching: 3,300
- **`/user/elsie_horne/portal_vein_thrombosis_icd10/22606950/`**
  - Just the codelist: 0
  - With X-padded codes: 310
  - With prefix matching: 310
- **`/user/kurttaylor/depression_icd10/4dc56a05/`**
  - Just the codelist: 3,250
  - With X-padded codes: 3,250 (0% increase)
  - With prefix matching: 3,850 (18% increase)
- **`/user/r_denholm/type-2-diabetes-secondary-care-bristol/0b7f6cd4/`**
  - Just the codelist: 0
  - With X-padded codes: 0
  - With prefix matching: 17,750

**Total for metformin_covid:**
- Exact match: 324,570 events
- With X-padded codes: 573,070 events
- With prefix matching: 1,499,800 events

## post-covid-vax-autoimmune

### Affected Codelists:

- **`/opensafely/type-1-diabetes-secondary-care/2020-09-27/`**
  - Just the codelist: 0
  - With X-padded codes: 0
  - With prefix matching: 14,470
- **`/user/elsie_horne/hypertension_icd10/1a48296e/`**
  - Just the codelist: 0
  - With X-padded codes: 22,520
  - With prefix matching: 23,940
- **`/user/josephignace/hematologic-diseases-aplastic-anaemia-icd10/778a31a2/`**
  - Just the codelist: 9,470
  - With X-padded codes: 9,470 (0% increase)
  - With prefix matching: 9,670 (2% increase)
- **`/user/r_denholm/type-2-diabetes-secondary-care-bristol/0b7f6cd4/`**
  - Just the codelist: 0
  - With X-padded codes: 0
  - With prefix matching: 17,750

**Total for post-covid-vax-autoimmune:**
- Exact match: 9,470 events
- With X-padded codes: 31,990 events
- With prefix matching: 65,830 events

## post-infection-outcomes

### Affected Codelists:

- **`/opensafely/acute-respiratory-illness-secondary-care/680e1eda/`**
  - Just the codelist: 43,290
  - With X-padded codes: 44,390 (3% increase)
  - With prefix matching: 51,990 (20% increase)
- **`/opensafely/cardiovascular-secondary-care/20b63bd4/`**
  - Just the codelist: 402,180
  - With X-padded codes: 426,860 (6% increase)
  - With prefix matching: 493,570 (23% increase)
- **`/opensafely/influenza-identification-secondary-care/3cfe5a71/`**
  - Just the codelist: 28,690
  - With X-padded codes: 28,930 (1% increase)
  - With prefix matching: 28,930 (1% increase)
- **`/opensafely/rsv-identification-secondary-care/560dcda6/`**
  - Just the codelist: 22,710
  - With X-padded codes: 22,710 (0% increase)
  - With prefix matching: 24,140 (6% increase)

**Total for post-infection-outcomes:**
- Exact match: 496,870 events
- With X-padded codes: 522,890 events
- With prefix matching: 598,630 events

## prophy_effects_Sotro_Molnup

### Affected Codelists:

- **`/nhsd/haematological-malignancies-icd-10/073f45c0/`**
  - Just the codelist: 1,680
  - With X-padded codes: 1,730 (3% increase)
  - With prefix matching: 266,220 (15746% increase)

**Total for prophy_effects_Sotro_Molnup:**
- Exact match: 1,680 events
- With X-padded codes: 1,730 events
- With prefix matching: 266,220 events

## vte-diagnoses-and-deaths

### Affected Codelists:

- **`/opensafely/venous-thromboembolic-disease-hospital/2020-10-01/`**
  - Just the codelist: 32,410
  - With X-padded codes: 32,720 (1% increase)
  - With prefix matching: 32,720 (1% increase)

**Total for vte-diagnoses-and-deaths:**
- Exact match: 32,410 events
- With X-padded codes: 32,720 events
- With prefix matching: 32,720 events

## winter_pressures_inequalities

### Affected Codelists:

- **`/opensafely/influenza-identification-secondary-care/3cfe5a71/`**
  - Just the codelist: 28,690
  - With X-padded codes: 28,930 (1% increase)
  - With prefix matching: 28,930 (1% increase)
- **`/opensafely/rsv-identification-secondary-care/560dcda6/`**
  - Just the codelist: 22,710
  - With X-padded codes: 22,710 (0% increase)
  - With prefix matching: 24,140 (6% increase)

**Total for winter_pressures_inequalities:**
- Exact match: 51,400 events
- With X-padded codes: 51,640 events
- With prefix matching: 53,070 events

## wp3_respiratory_virus_timeseries

### Affected Codelists:

- **`/opensafely/influenza-identification-secondary-care/7d33be15/`**
  - Just the codelist: 28,690
  - With X-padded codes: 28,930 (1% increase)
  - With prefix matching: 28,930 (1% increase)
- **`/opensafely/rsv-identification-secondary-care/5ebecaf4/`**
  - Just the codelist: 22,710
  - With X-padded codes: 22,710 (0% increase)
  - With prefix matching: 24,140 (6% increase)

**Total for wp3_respiratory_virus_timeseries:**
- Exact match: 51,400 events
- With X-padded codes: 51,640 events
- With prefix matching: 53,070 events
