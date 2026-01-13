# APCS missing ICD10 code analysis

Analysis of how different prefix matching assumptions affect codelist coverage.

## Introduction

ICD10 codes appear in the admitted patient care spells (APCS) table in three fields: primary diagnosis, secondary diagnosis, and all diagnosis. We ran a [job](https://jobs.opensafely.org/opensafely-internal/tpp-code-counts/) to find the usage of all ICD10 codes in APCS. OpenCodelists does not have all ICD10 codes in its database - partly down to using the 2019 version of ICD10 (rather than the modified 2016 version used by APCS), and partly due to the absence of 5 character codes. This report analyzes to what extent this affects the codelists that have been used in OpenCodelists.

## Overall Summary

- Total codelists analyzed: 93
- Builder codelists: 55
- Uploaded codelists: 31
- Inline codelists: 7

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
| Baseline | 2,141,870 | - | - |
| Strict | 2,503,100 | +361,230 | +16.87% |
| Partial | 2,509,550 | +367,680 | +17.17% |

### Unaffected Codelists

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| Strict vs Baseline | 66/93 (71.0%) | 41/55 (74.5%) | 18/31 (58.1%) |
| Partial vs Baseline | 60/93 (64.5%) | 36/55 (65.5%) | 17/31 (54.8%) |


### By Creation Method

#### Builder Codelists

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 1,409,900 | - | - |
| Strict | 1,542,180 | +132,280 | +9.38% |
| Partial | 1,547,570 | +137,670 | +9.76% |


#### Uploaded Codelists

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 446,270 | - | - |
| Strict | 675,220 | +228,950 | +51.30% |
| Partial | 676,280 | +230,010 | +51.54% |
| Lax | 1,634,480 | +1,188,210 | +266.25% |

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| Strict vs Baseline | 18/31 (58.1%) | - | 18/31 (58.1%) |
| Partial vs Baseline | 17/31 (54.8%) | - | 17/31 (54.8%) |
| Lax vs Baseline | 1/31 (3.2%) | - | 1/31 (3.2%) |


#### Inline Codelists

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 285,700 | - | - |
| Strict | 285,700 | +0 | +0.00% |
| Partial | 285,700 | +0 | +0.00% |
| Lax | 285,700 | +0 | +0.00% |

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| Strict vs Baseline | 7/7 (100.0%) | - | 7/7 (100.0%) |
| Partial vs Baseline | 7/7 (100.0%) | - | 7/7 (100.0%) |


## Secondary Diagnosis Field

This field is exactly the same as the primary diagnosis field so we just repeat the above analysis here.

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 2,469,100 | - | - |
| Strict | 2,949,620 | +480,520 | +19.46% |
| Partial | 2,977,460 | +508,360 | +20.59% |

### Unaffected Codelists

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| Strict vs Baseline | 65/93 (69.9%) | 40/55 (72.7%) | 18/31 (58.1%) |
| Partial vs Baseline | 58/93 (62.4%) | 35/55 (63.6%) | 16/31 (51.6%) |


### By Creation Method

#### Builder Codelists

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 1,710,850 | - | - |
| Strict | 1,757,160 | +46,310 | +2.71% |
| Partial | 1,781,840 | +70,990 | +4.15% |


#### Uploaded Codelists

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 519,630 | - | - |
| Strict | 953,840 | +434,210 | +83.56% |
| Partial | 957,000 | +437,370 | +84.17% |
| Lax | 1,348,440 | +828,810 | +159.50% |

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| Strict vs Baseline | 18/31 (58.1%) | - | 18/31 (58.1%) |
| Partial vs Baseline | 16/31 (51.6%) | - | 16/31 (51.6%) |
| Lax vs Baseline | 2/31 (6.5%) | - | 2/31 (6.5%) |


#### Inline Codelists

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 238,620 | - | - |
| Strict | 238,620 | +0 | +0.00% |
| Partial | 238,620 | +0 | +0.00% |
| Lax | 238,620 | +0 | +0.00% |

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| Strict vs Baseline | 7/7 (100.0%) | - | 7/7 (100.0%) |
| Partial vs Baseline | 7/7 (100.0%) | - | 7/7 (100.0%) |


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
| Baseline (codelist codes only) | 16,776,390 | - | - |
| With PARTIAL descendants (prefix matching) | 17,059,270 | +282,880 | +1.69% |

### Unaffected Codelists

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| PARTIAL descendants vs Baseline | 79/93 (84.9%) | 45/55 (81.8%) | 27/31 (87.1%) |


### By Creation Method

#### Builder Codelists

| Scenario | Total Events | Inadvertent Inclusion | % Increase |
|----------|-------------:|----------------------:|-----------:|
| Baseline (codelist codes only) | 11,787,920 | - | - |
| With PARTIAL descendants (prefix matching) | 12,058,100 | +270,180 | +2.29% |


#### Uploaded Codelists

| Scenario | Total Events | Inadvertent Inclusion | % Increase |
|----------|-------------:|----------------------:|-----------:|
| Baseline (codelist codes only) | 3,434,020 | - | - |
| With PARTIAL descendants (prefix matching) | 3,446,720 | +12,700 | +0.37% |

