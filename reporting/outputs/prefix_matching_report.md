# Prefix Matching Issues Report

**Generated**: 2026-01-20 13:10:53

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

**8 projects** may be affected by this change.

### Affected Projects:

| Project # | Project Name | Repository |
|-----------|-------------|-----------|
|  |  | [COMPARES-vaccines](https://github.com/opensafely/COMPARES-vaccines) |
|  |  | [JAKi-hosp](https://github.com/opensafely/JAKi-hosp) |
| 182 | [Incidence of long-term conditions in England before and after the onset of the COVID-19 pandemic](https://jobs.opensafely.org/incidence-of-long-term-conditions-in-england-before-and-after-the-onset-of-the-covid-19-pandemic) | [disease_incidence](https://github.com/opensafely/disease_incidence) |
| 193 | [Incidence and management of inflammatory rheumatic diseases before, during and after the COVID-19 pandemic](https://jobs.opensafely.org/incidence-and-management-of-inflammatory-rheumatic-diseases-before-during-and-after-the-covid-19-pandemic) | [inflammatory_rheum](https://github.com/opensafely/inflammatory_rheum) |
| 175 | [Implications of metformin for Long COVID](https://jobs.opensafely.org/implications-of-metformin-for-long-covid) | [metformin_covid](https://github.com/opensafely/metformin_covid) |
|  |  | [post-covid-vax-autoimmune](https://github.com/opensafely/post-covid-vax-autoimmune) |
| 91 | [Coverage, effectiveness and safety of neutralising monoclonal antibodies or antivirals for non-hospitalised patients with COVID-19](https://jobs.opensafely.org/coverage-effectiveness-and-safety-of-neutralising-monoclonal-antibodies-or-antivirals-for-non-hospitalised-patients-with-covid-19) | [prophy_effects_Sotro_Molnup](https://github.com/opensafely/prophy_effects_Sotro_Molnup) |
| 153 | [What was the impact of COVID-19 on mortality related to venous thromboembolism in England?](https://jobs.opensafely.org/what-was-the-impact-of-covid-19-on-mortality-related-to-venous-thromboembolism-in-england) | [vte-diagnoses-and-deaths](https://github.com/opensafely/vte-diagnoses-and-deaths) |

---

## COMPARES-vaccines

### Affected Codelists:

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
- Exact match: 51,820 events
- With X-padded codes: 54,060 events
- With prefix matching: 57,360 events

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

## disease_incidence

### Affected Codelists:

- **`/bristol/multiple-sclerosis-icd10-v13/31e7874a/`**
  - Just the codelist: 1,350
  - With X-padded codes: 38,130 (2724% increase)
  - With prefix matching: 38,150 (2726% increase)
- **`/opensafely/stroke-secondary-care/2b8aa4a9/`**
  - Just the codelist: 54,420
  - With X-padded codes: 55,950 (3% increase)
  - With prefix matching: 55,950 (3% increase)
- **`/user/markdrussell/COPD_admission/43348250/`**
  - Just the codelist: 59,280
  - With X-padded codes: 59,450 (0% increase)
  - With prefix matching: 59,450 (0% increase)
- **`/user/markdrussell/asthma-secondary-care/2a250f1b/`**
  - Just the codelist: 31,760
  - With X-padded codes: 33,560 (6% increase)
  - With prefix matching: 33,560 (6% increase)
- **`/user/markdrussell/chronic-kidney-disease-secondary-care/167b1bd2/`**
  - Just the codelist: 248,030
  - With X-padded codes: 248,370 (0% increase)
  - With prefix matching: 250,280 (1% increase)
- **`/user/markdrussell/crohns-disease-secondary-care/7ab8e8a6/`**
  - Just the codelist: 86,320
  - With X-padded codes: 86,320 (0% increase)
  - With prefix matching: 86,350 (0% increase)
- **`/user/markdrussell/dementia-secondary-care/45e74246/`**
  - Just the codelist: 12,230
  - With X-padded codes: 14,170 (16% increase)
  - With prefix matching: 14,170 (16% increase)
- **`/user/markdrussell/multiple-sclerosis-secondary-care/2cd7cf11/`**
  - Just the codelist: 0
  - With X-padded codes: 36,780
  - With prefix matching: 36,780
- **`/user/markdrussell/osteoporosis-secondary-care/4b4cc232/`**
  - Just the codelist: 20,430
  - With X-padded codes: 20,430 (0% increase)
  - With prefix matching: 31,810 (56% increase)
- **`/user/markdrussell/psoriasis-secondary-care/7d6ba89c/`**
  - Just the codelist: 4,030
  - With X-padded codes: 4,030 (0% increase)
  - With prefix matching: 4,730 (17% increase)
- **`/user/markdrussell/rheumatoid-arthritis-secondary-care/245780e9/`**
  - Just the codelist: 21,910
  - With X-padded codes: 21,910 (0% increase)
  - With prefix matching: 36,860 (68% increase)
- **`/user/markdrussell/stroke-and-tia-secondary-care/780628b0/`**
  - Just the codelist: 64,480
  - With X-padded codes: 66,010 (2% increase)
  - With prefix matching: 66,410 (3% increase)

**Total for disease_incidence:**
- Exact match: 604,240 events
- With X-padded codes: 685,110 events
- With prefix matching: 714,500 events

## inflammatory_rheum

### Affected Codelists:

- **`/user/markdrussell/axial-spondyloarthritis-secondary-care/4e9728c6/`**
  - Just the codelist: 0
  - With X-padded codes: 2,160
  - With prefix matching: 2,870
- **`/user/markdrussell/psoriatic-arthritis-secondary-care/67a69bfb/`**
  - Just the codelist: 2,810
  - With X-padded codes: 2,810 (0% increase)
  - With prefix matching: 3,300 (17% increase)
- **`/user/markdrussell/rheumatoid-arthritis-secondary-care/245780e9/`**
  - Just the codelist: 21,910
  - With X-padded codes: 21,910 (0% increase)
  - With prefix matching: 36,860 (68% increase)

**Total for inflammatory_rheum:**
- Exact match: 24,720 events
- With X-padded codes: 26,880 events
- With prefix matching: 43,030 events

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
- **`/user/r_denholm/type-2-diabetes-secondary-care-bristol/0b7f6cd4/`**
  - Just the codelist: 0
  - With X-padded codes: 0
  - With prefix matching: 17,750

**Total for metformin_covid:**
- Exact match: 321,320 events
- With X-padded codes: 569,820 events
- With prefix matching: 1,495,950 events

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
- **`/user/r_denholm/type-2-diabetes-secondary-care-bristol/0b7f6cd4/`**
  - Just the codelist: 0
  - With X-padded codes: 0
  - With prefix matching: 17,750

**Total for post-covid-vax-autoimmune:**
- Exact match: 0 events
- With X-padded codes: 22,520 events
- With prefix matching: 56,160 events

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
