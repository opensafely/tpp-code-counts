# APCS missing ICD10 code analysis

Analysis of how different prefix matching assumptions affect codelist coverage.

## Introduction

ICD10 codes appear in the admitted patient care spells (APCS) table in three fields: primary diagnosis, secondary diagnosis, and all diagnosis. We ran a [job](https://jobs.opensafely.org/opensafely-internal/tpp-code-counts/) to find the usage of all ICD10 codes in APCS. OpenCodelists does not have all ICD10 codes in its database - partly down to using the 2019 version of ICD10 (rather than the modified 2016 version used by APCS), and partly due to the absence of 5 character codes. This report analyzes to what extent this affects the codelists that have been used in OpenCodelists.

## Overall Summary

- Total codelists analyzed: 89
- Builder codelists: 34
- Uploaded codelists: 41
- Inline codelists: 14

A 'builder' codelist is one created using the OpenCodelists builder tool, whereas an 'uploaded' codelist is one uploaded directly by a user. 'Inline' codelists are hardcoded values in analysis code. They are reported separately in places because in the builder, children of included codes get automatically included (unless explicitly excluded), whereas in uploaded and inline codelists they are deliberately excluded.

## Primary diagnosis field

This field contains a single ICD10 code. It is ALWAYS 4 or 5 characters long, with any 3 character codes padded with an X to make them 4 characters (e.g. `G35` becomes `G35X`).

Prefix matching is NOT applied by ehrQL when querying this field.

For our analysis we report:
|Strategy|Description|
|----|----|
|Baseline| Total event count in this field using just codes in the codelist|
|Strict| Total event count if we supplement the codelist with the descendants of `COMPLETE`**\*** codes from the codelist|
|Partial| Total event count if we supplement the codelist with the descendants of `COMPLETE`**\*** and `PARTIAL`**\*** codes from the codelist|
|Lax (uploaded only)| Including descendants of `NONE`**\*** codes from the codelist|

**\*** _For each code in a codelist we look to see whether its descendants (according to the opencodelist dictionary) are also present. If all of its descendants are there we class the code as `COMPLETE`. If some, but not all, we class it as `PARTIAL`. If none, we class it as `NONE`. NB a code with no children is `COMPLETE`._

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 2,226,140 | - | - |
| Strict | 2,728,900 | +502,760 | +22.58% |
| Partial | 2,757,570 | +531,430 | +23.87% |

### Unaffected Codelists

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| Strict vs Baseline | 69/89 (77.5%) | 27/34 (79.4%) | 29/41 (70.7%) |
| Partial vs Baseline | 61/89 (68.5%) | 21/34 (61.8%) | 27/41 (65.9%) |


### By Creation Method

#### Builder Codelists

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 883,400 | - | - |
| Strict | 1,098,440 | +215,040 | +24.34% |
| Partial | 1,116,100 | +232,700 | +26.34% |


#### Uploaded Codelists

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 982,140 | - | - |
| Strict | 1,207,280 | +225,140 | +22.92% |
| Partial | 1,218,290 | +236,150 | +24.04% |
| Lax | 2,227,150 | +1,245,010 | +126.77% |

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| Strict vs Baseline | 29/41 (70.7%) | - | 29/41 (70.7%) |
| Partial vs Baseline | 27/41 (65.9%) | - | 27/41 (65.9%) |
| Lax vs Baseline | 5/41 (12.2%) | - | 5/41 (12.2%) |


#### Inline Codelists

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 360,600 | - | - |
| Strict | 423,180 | +62,580 | +17.35% |
| Partial | 423,180 | +62,580 | +17.35% |
| Lax | 360,600 | +0 | +0.00% |

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| Strict vs Baseline | 13/14 (92.9%) | - | 13/14 (92.9%) |
| Partial vs Baseline | 13/14 (92.9%) | - | 13/14 (92.9%) |


## Secondary Diagnosis Field

This field is exactly the same as the primary diagnosis field so we just repeat the above analysis here.

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 2,096,270 | - | - |
| Strict | 2,978,990 | +882,720 | +42.11% |
| Partial | 2,988,720 | +892,450 | +42.57% |

### Unaffected Codelists

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| Strict vs Baseline | 69/89 (77.5%) | 27/34 (79.4%) | 29/41 (70.7%) |
| Partial vs Baseline | 60/89 (67.4%) | 21/34 (61.8%) | 26/41 (63.4%) |


### By Creation Method

#### Builder Codelists

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 652,830 | - | - |
| Strict | 709,090 | +56,260 | +8.62% |
| Partial | 715,440 | +62,610 | +9.59% |


#### Uploaded Codelists

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 1,169,930 | - | - |
| Strict | 1,969,720 | +799,790 | +68.36% |
| Partial | 1,973,100 | +803,170 | +68.65% |
| Lax | 2,092,970 | +923,040 | +78.90% |

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| Strict vs Baseline | 29/41 (70.7%) | - | 29/41 (70.7%) |
| Partial vs Baseline | 26/41 (63.4%) | - | 26/41 (63.4%) |
| Lax vs Baseline | 4/41 (9.8%) | - | 4/41 (9.8%) |


#### Inline Codelists

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 273,510 | - | - |
| Strict | 300,180 | +26,670 | +9.75% |
| Partial | 300,180 | +26,670 | +9.75% |
| Lax | 273,510 | +0 | +0.00% |

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| Strict vs Baseline | 13/14 (92.9%) | - | 13/14 (92.9%) |
| Partial vs Baseline | 13/14 (92.9%) | - | 13/14 (92.9%) |


## All Diagnosis Field

This field contains all ICD10 codes recorded during a patient spell in hospital. It contains a concatenated list of ICD10 codes. The codes are usually in the same format as those in the primary and secondary diagnosis fields (i.e., 4 or 5 characters, with 3 character codes padded with an X). However, the field doesn't seem to have as much validation and so you do get exceptions e.g. 3 character codes without the X padding. However, these are always below the 15 usage threshold so we ignore them in this analysis.

Currently, the way we query this field with ehrQL, means that prefix matching is ALWAYS applied. This means that if you have a codelist with `PARTIAL` codes, that is places where a parent code is included, and some, but not all, of its children are deliberatly excluded suggesting the intention is for only the included codes to be matched, so the prefix matching would lead to inadvertent inclusion of those excluded children.

For our analysis we report:
|Strategy|Description|
|----|----|
|Baseline| Total event count in this field using just codes in the codelist|
|With PARTIAL descendants| Total event count when including codes that are children of `PARTIAL` codes|

| Scenario | Total Events | Inadvertent Inclusion | % Increase |
|----------|-------------:|----------------------:|-----------:|
| Baseline (codelist codes only) | 14,074,580 | - | - |
| With PARTIAL descendants (prefix matching) | 14,138,970 | +64,390 | +0.46% |

### Unaffected Codelists

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| PARTIAL descendants vs Baseline | 75/89 (84.3%) | 25/34 (73.5%) | 36/41 (87.8%) |


### By Creation Method

#### Builder Codelists

| Scenario | Total Events | Inadvertent Inclusion | % Increase |
|----------|-------------:|----------------------:|-----------:|
| Baseline (codelist codes only) | 4,630,270 | - | - |
| With PARTIAL descendants (prefix matching) | 4,671,700 | +41,430 | +0.89% |


#### Uploaded Codelists

| Scenario | Total Events | Inadvertent Inclusion | % Increase |
|----------|-------------:|----------------------:|-----------:|
| Baseline (codelist codes only) | 7,705,950 | - | - |
| With PARTIAL descendants (prefix matching) | 7,728,910 | +22,960 | +0.30% |

