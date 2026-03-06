# Prefix Matching Issues Report

**Generated**: 2026-03-06 15:07:58

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

**14 projects** may be affected by this change.

### Affected Projects:

| Project # | Project Name | Repository |
|-----------|-------------|-----------|
|  |  | [COVID-19_vacci_and_MACE_after_hip_fracture](https://github.com/opensafely/COVID-19_vacci_and_MACE_after_hip_fracture) |
|  |  | [NeurodegenerativeDiseaseBurden](https://github.com/opensafely/NeurodegenerativeDiseaseBurden) |
| 196 | [OpenPREGnosis: Developing an Open Algorithm to Identify Pregnancy Episodes and Outcomes in OpenSAFELY](https://jobs.opensafely.org/openpregnosis-developing-an-open-algorithm-to-identify-pregnancy-episodes-and-outcomes-in-opensafely) | [OpenPregnosis](https://github.com/opensafely/OpenPregnosis) |
| 22 | [Investigating the effectiveness of the COVID-19 vaccination programme in the UK](https://jobs.opensafely.org/investigating-the-effectiveness-of-the-covid-19-vaccination-programme-in-the-uk) | [comparative-booster-spring2023](https://github.com/opensafely/comparative-booster-spring2023) |
| 161 | [COVID-19 Collateral (Project continuation of approved project no 95)](https://jobs.opensafely.org/covid-19-collateral-project-continuation-of-approved-project-no-95) | [covid_collateral_hf_update](https://github.com/opensafely/covid_collateral_hf_update) |
| 182 | [Incidence of long-term conditions in England before and after the onset of the COVID-19 pandemic](https://jobs.opensafely.org/incidence-of-long-term-conditions-in-england-before-and-after-the-onset-of-the-covid-19-pandemic) | [disease_incidence](https://github.com/opensafely/disease_incidence) |
| 176 | [Comparing Disparities in RSV, Influenza and Covid-19](https://jobs.opensafely.org/comparing-disparities-in-rsv-influenza-and-covid-19) | [disparities-comparison](https://github.com/opensafely/disparities-comparison) |
| 193 | [Incidence and management of inflammatory rheumatic diseases before, during and after the COVID-19 pandemic](https://jobs.opensafely.org/incidence-and-management-of-inflammatory-rheumatic-diseases-before-during-and-after-the-covid-19-pandemic) | [inflammatory_rheum](https://github.com/opensafely/inflammatory_rheum) |
| 175 | [Implications of metformin for Long COVID](https://jobs.opensafely.org/implications-of-metformin-for-long-covid) | [metformin_covid](https://github.com/opensafely/metformin_covid) |
| 172 | [Impact and inequalities of winter pressures in primary care: providing the evidence base for mitigation strategies](https://jobs.opensafely.org/impact-and-inequalities-of-winter-pressures-in-primary-care-providing-the-evidence-base-for-mitigation-strategies) | [post-infection-outcomes](https://github.com/opensafely/post-infection-outcomes) |
| 91 | [Coverage, effectiveness and safety of neutralising monoclonal antibodies or antivirals for non-hospitalised patients with COVID-19](https://jobs.opensafely.org/coverage-effectiveness-and-safety-of-neutralising-monoclonal-antibodies-or-antivirals-for-non-hospitalised-patients-with-covid-19) | [prophy_effects_Sotro_Molnup](https://github.com/opensafely/prophy_effects_Sotro_Molnup) |
| 153 | [What was the impact of COVID-19 on mortality related to venous thromboembolism in England?](https://jobs.opensafely.org/what-was-the-impact-of-covid-19-on-mortality-related-to-venous-thromboembolism-in-england) | [vte-diagnoses-and-deaths](https://github.com/opensafely/vte-diagnoses-and-deaths) |
| 172 | [Impact and inequalities of winter pressures in primary care: providing the evidence base for mitigation strategies](https://jobs.opensafely.org/impact-and-inequalities-of-winter-pressures-in-primary-care-providing-the-evidence-base-for-mitigation-strategies) | [winter_pressures_inequalities](https://github.com/opensafely/winter_pressures_inequalities) |
|  |  | [wp3_respiratory_virus_timeseries](https://github.com/opensafely/wp3_respiratory_virus_timeseries) |

---

## COVID-19_vacci_and_MACE_after_hip_fracture

### Affected Codelists:

- **`/user/BillyZhongUOM/hip-fracture-icd-10/0ec29807/`**
  - Just the codelist: 1,560
  - With X-padded codes: 1,560 (0% increase)
  - With prefix matching: 35,100 (2150% increase)
- **`/user/BillyZhongUOM/non_fatal_stroke/5f567192/`**
  - Just the codelist: 52,200
  - With X-padded codes: 53,730 (3% increase)
  - With prefix matching: 53,730 (3% increase)

**Total for COVID-19_vacci_and_MACE_after_hip_fracture:**
- Exact match: 53,760 events
- With X-padded codes: 55,290 events
- With prefix matching: 88,830 events

## NeurodegenerativeDiseaseBurden

### Affected Codelists:

- **`/bristol/burden-of-neurodegenerative-diseases-huntington-disease/762e0511/`**
  - Just the codelist: 0
  - With X-padded codes: 100
  - With prefix matching: 100
- **`/bristol/burden-of-neurodegenerative-diseases-parkinsons-disease/19d8dfc7/`**
  - Just the codelist: 40
  - With X-padded codes: 3,200 (7900% increase)
  - With prefix matching: 3,200 (7900% increase)
- **`/bristol/burden-of-neurodegenerative-diseases-unspecified-dementia-icd10/0bd6d6bc/`**
  - Just the codelist: 5,680
  - With X-padded codes: 7,620 (34% increase)
  - With prefix matching: 7,690 (35% increase)
- **`/user/RochelleKnight/prostate_cancer_icd10/6b27d648/`**
  - Just the codelist: 0
  - With X-padded codes: 58,660
  - With prefix matching: 58,660

**Total for NeurodegenerativeDiseaseBurden:**
- Exact match: 5,720 events
- With X-padded codes: 69,580 events
- With prefix matching: 69,650 events

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
- **`/user/markdrussell/coronary-heart-disease-secondary-care/11159be6/`**
  - Just the codelist: 87,200
  - With X-padded codes: 87,200 (0% increase)
  - With prefix matching: 87,440 (0% increase)
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
- Exact match: 691,440 events
- With X-padded codes: 772,310 events
- With prefix matching: 801,940 events

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

## inflammatory_rheum

### Affected Codelists:

- **`/user/markdrussell/axial-spondyloarthritis-secondary-care/4e9728c6/`**
  - Just the codelist: 0
  - With X-padded codes: 2,160
  - With prefix matching: 2,870
- **`/user/markdrussell/inflammatory-myositis-secondary-care/7ad5af04/`**
  - Just the codelist: 1,720
  - With X-padded codes: 1,720 (0% increase)
  - With prefix matching: 4,140 (141% increase)
- **`/user/markdrussell/psoriatic-arthritis-secondary-care/67a69bfb/`**
  - Just the codelist: 2,810
  - With X-padded codes: 2,810 (0% increase)
  - With prefix matching: 3,300 (17% increase)
- **`/user/markdrussell/rheumatoid-arthritis-secondary-care/245780e9/`**
  - Just the codelist: 21,910
  - With X-padded codes: 21,910 (0% increase)
  - With prefix matching: 36,860 (68% increase)

**Total for inflammatory_rheum:**
- Exact match: 26,440 events
- With X-padded codes: 28,600 events
- With prefix matching: 47,170 events

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
