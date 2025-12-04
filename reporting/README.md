Once we have the output files we can produce some post-hoc reports. These are kept separate from the main analysis so that they can be run independently as needed. Also we expect that if they find issues, these will be resolved, so no need to rerun in future.

The list of codes used in OpenCodelists can be generated from a copy of the coding database. So e.g. if you have the icd10_2019-covid-expanded_20190101.sqlite3 file, you can run:

```bash
sqlite3 icd10_2019-covid-expanded_20190101.sqlite3 \
  "SELECT code FROM icd10_concept WHERE kind!='chapter';" | \
   sort | \
   uniq > ocl_icd10_codes.txt
```

TODO - improve this file
