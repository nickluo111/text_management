# Yelp dataset access

## Required files

Only these two files are needed for the assignment:

- `yelp_academic_dataset_business.json`
- `yelp_academic_dataset_review.json`

Place both under `data/raw/`. Do not rename them unless `configs/default.toml` is updated.

## Official Yelp page

The official URLs currently return an HTTP 403 response from CloudFront in both automated requests and a normal browser session from this environment:

- <https://www.yelp.com/dataset>
- <https://business.yelp.com/data/resources/open-dataset/>

This looks like a delivery/access restriction rather than evidence that the dataset has been withdrawn. Do not attempt to bypass the restriction. It may still work from a different ordinary network or at a later time.

## Recommended fallback: Yelp's Kaggle dataset

Kaggle exposes a dataset owned by `yelp-dataset` / Yelp, Inc. containing the same named business and review JSON files:

<https://www.kaggle.com/datasets/yelp-dataset/yelp-dataset/data>

The web page is accessible from this environment. Downloading may require a Kaggle account or Kaggle CLI authentication. After installing the official Kaggle CLI and authenticating, download only the two needed files:

```powershell
kaggle datasets download yelp-dataset/yelp-dataset `
  -f yelp_academic_dataset_business.json `
  -p data/raw --unzip

kaggle datasets download yelp-dataset/yelp-dataset `
  -f yelp_academic_dataset_review.json `
  -p data/raw --unzip
```

Before using this fallback, read the included `Dataset_User_Agreement.pdf` and record the dataset version/date in the report.

## Other acceptable fallback

The assignment explicitly encourages one download per group. A group member who can access the official dataset may share the unchanged archive privately with the group, subject to the dataset agreement. The instructor/course channel is the best escalation if neither Yelp nor Kaggle works.

Avoid arbitrary third-party mirrors and do not replace this dataset with Yelp Review Polarity/Full: those classification datasets lack `business.json`, `business_id`, categories, and the temporal/business linkage required by the assignment.
