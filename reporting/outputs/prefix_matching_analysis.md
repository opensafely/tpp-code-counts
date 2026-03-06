# APCS missing ICD10 code analysis

Analysis of how different prefix matching assumptions affect codelist coverage.

## Introduction

ICD10 codes appear in the admitted patient care spells (APCS) table in three fields: primary diagnosis, secondary diagnosis, and all diagnosis. We ran a [job](https://jobs.opensafely.org/opensafely-internal/tpp-code-counts/) to find the usage of all ICD10 codes in APCS. OpenCodelists does not have all ICD10 codes in its database - partly down to using the 2019 version of ICD10 (rather than the modified 2016 version used by APCS), and partly due to the absence of 5 character codes. This report analyzes to what extent this affects the codelists that have been used in OpenCodelists.

## Overall Summary

- Total codelists analyzed: 123
- Builder codelists: 56
- Uploaded codelists: 53
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
| Baseline | 3,069,210 | - | - |
| Strict | 3,722,640 | +653,430 | +21.29% |
| Partial | 3,753,690 | +684,480 | +22.30% |

### Unaffected Codelists

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| Strict vs Baseline | 84/123 (68.3%) | 35/56 (62.5%) | 36/53 (67.9%) |
| Partial vs Baseline | 77/123 (62.6%) | 30/56 (53.6%) | 34/53 (64.2%) |


### By Creation Method

#### Builder Codelists

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 1,571,410 | - | - |
| Strict | 1,894,020 | +322,610 | +20.53% |
| Partial | 1,914,040 | +342,630 | +21.80% |


#### Uploaded Codelists

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 1,137,200 | - | - |
| Strict | 1,405,440 | +268,240 | +23.59% |
| Partial | 1,416,470 | +279,270 | +24.56% |
| Lax | 2,382,210 | +1,245,010 | +109.48% |

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| Strict vs Baseline | 36/53 (67.9%) | - | 36/53 (67.9%) |
| Partial vs Baseline | 34/53 (64.2%) | - | 34/53 (64.2%) |
| Lax vs Baseline | 6/53 (11.3%) | - | 6/53 (11.3%) |


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
| Baseline | 3,247,890 | - | - |
| Strict | 4,181,460 | +933,570 | +28.74% |
| Partial | 4,213,360 | +965,470 | +29.73% |

### Unaffected Codelists

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| Strict vs Baseline | 83/123 (67.5%) | 34/56 (60.7%) | 36/53 (67.9%) |
| Partial vs Baseline | 75/123 (61.0%) | 29/56 (51.8%) | 33/53 (62.3%) |


### By Creation Method

#### Builder Codelists

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 1,771,080 | - | - |
| Strict | 1,862,910 | +91,830 | +5.18% |
| Partial | 1,891,430 | +120,350 | +6.80% |


#### Uploaded Codelists

| Scenario | Total Events | Difference from Baseline | % Increase |
|----------|-------------:|-------------------------:|-----------:|
| Baseline | 1,203,300 | - | - |
| Strict | 2,018,370 | +815,070 | +67.74% |
| Partial | 2,021,750 | +818,450 | +68.02% |
| Lax | 2,126,340 | +923,040 | +76.71% |

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| Strict vs Baseline | 36/53 (67.9%) | - | 36/53 (67.9%) |
| Partial vs Baseline | 33/53 (62.3%) | - | 33/53 (62.3%) |
| Lax vs Baseline | 6/53 (11.3%) | - | 6/53 (11.3%) |


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
| Baseline (codelist codes only) | 22,205,220 | - | - |
| With PARTIAL descendants (prefix matching) | 22,533,250 | +328,030 | +1.48% |

### Unaffected Codelists

| Comparison | All Codelists | Builder | Uploaded |
|------------|--------------|---------|----------|
| PARTIAL descendants vs Baseline | 105/123 (85.4%) | 44/56 (78.6%) | 47/53 (88.7%) |


### By Creation Method

#### Builder Codelists

| Scenario | Total Events | Inadvertent Inclusion | % Increase |
|----------|-------------:|----------------------:|-----------:|
| Baseline (codelist codes only) | 12,365,750 | - | - |
| With PARTIAL descendants (prefix matching) | 12,670,560 | +304,810 | +2.46% |


#### Uploaded Codelists

| Scenario | Total Events | Inadvertent Inclusion | % Increase |
|----------|-------------:|----------------------:|-----------:|
| Baseline (codelist codes only) | 8,101,110 | - | - |
| With PARTIAL descendants (prefix matching) | 8,124,330 | +23,220 | +0.29% |

