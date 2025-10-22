# Weekly Analysis Upload Process

## Overview
This document describes how to update the weekly bias analysis data for the RTM Monitor application deployed on Google Cloud Run.

## Prerequisites
- Google Cloud SDK (`gcloud`) installed and configured
- Access to the `escobar-analysis-data` GCS bucket
- New Analysis.xlsx file with updated weekly data

## Upload Process

### Option 1: Using gcloud CLI (Recommended)
```bash
# Upload the new Analysis.xlsx file to GCS bucket
gsutil cp Analysis.xlsx gs://escobar-analysis-data/Analysis.xlsx

# Verify upload
gsutil ls -l gs://escobar-analysis-data/Analysis.xlsx
```

### Option 2: Using Google Cloud Console
1. Go to Google Cloud Console > Storage > Browser
2. Navigate to the `escobar-analysis-data` bucket
3. Click "Upload Files"
4. Select and upload the new `Analysis.xlsx` file
5. Confirm the file is uploaded and replaces the old one

## Analysis File Format
The Analysis.xlsx file must contain these columns:
- **Date**: Date of the analysis (YYYY-MM-DD format)
- **Instrument**: Trading instrument symbol (e.g., AU200_AUD, EUR_USD)
- **Current Daily**: Current market condition (RTM, Trending, Ranging, etc.)
- **Bias**: Trading bias - must be one of: "Up", "Down", "Hold"

### Example Data Structure:
```
Date        | Instrument  | Current Daily | Bias
2025-08-13  | AU200_AUD   | RTM          | Down
2025-08-13  | CN50_USD    | Trending     | Up
2025-08-13  | EUR_USD     | Ranging      | Hold
```

## How It Works
1. **Upload**: New Analysis.xlsx is uploaded to GCS bucket
2. **Detection**: Backend automatically detects file changes via timestamp
3. **Processing**: Latest date's data is loaded and cached
4. **Display**: Frontend groups instruments by bias (Up/Down/Hold/No Data)

## Verification
After uploading, verify the changes:
1. Open the RTM Monitor application
2. Click "Generate RTM Data" for any category
3. Confirm instruments are grouped by bias sections:
   - 📈 Up Bias
   - 📉 Down Bias  
   - ⏸️ Hold Bias
   - 📊 No Bias Data

## Environment Variables
Ensure these are set in Cloud Run:
- `GCS_BUCKET_NAME=escobar-analysis-data`
- `GOOGLE_APPLICATION_CREDENTIALS` (service account with GCS read access)

## Troubleshooting
- **File not loading**: Check GCS bucket permissions and Cloud Run service account access
- **Invalid bias values**: Ensure Bias column only contains "Up", "Down", or "Hold"
- **No grouping shown**: Verify instrument names match between Analysis.xlsx and symbol.json

## Weekly Checklist
- [ ] Prepare new Analysis.xlsx with current week's data
- [ ] Upload file to GCS bucket using one of the methods above
- [ ] Verify upload completed successfully
- [ ] Test application to confirm bias grouping is working
- [ ] Document any issues or changes needed