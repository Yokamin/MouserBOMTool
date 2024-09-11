# BOM Tool
This script is designed to search for part numbers using the Mouser API and update a Bill of Materials (BOM) with pricing information.

## Features
- Searches Mouser for part numbers found in a CSV file.
- Extracts pricing information for multiple quantities.
- Calculates the nearest price for quantities not directly available from the search results.
- Saves the updated BOM data to a new file.
- Supports excluding rows with invalid or empty URLs.

### Price Calculation
The script uses a function called find_price_for_quantity to determine the price for a given quantity.

If the exact quantity is not available in the search results, it calculates the nearest price by summing up smaller quantities. For example:
- If you request the price for 150 units and the search results have prices for 100 and 50 units, the script will combine these to estimate the cost for 150 units.
- This ensures the script can always provide a price estimate, even if the exact quantity is not listed.

## Requirements
Make sure you have the following Python packages installed:
- requests
- PyYAML

You can install them by using:
```bash
pip install requests PyYAML
```

## Setup
### API Key:
1. Obtain a Mouser API key for part searches.
2. Save it in your environment variables as ```MOUSER_SEARCH_API_KEY``` or in a file named ```mouser_api_keys.yaml``` with the format:
```yaml
search_api_key: YOUR_API_KEY_HERE
```

### CSV File:
Ensure your BOM file is named ```BOM_.csv``` and is in the same directory as this script.

## Usage
### Run the script:
```bash
python your_script.py
```
By default, it will include all rows, even those with invalid or empty URLs.
To exclude rows with invalid or empty URLs, run:
```bash
python your_script.py --exclude-invalid-urls
```

### Output
The script creates a timestamped output directory under the ```output``` folder.
The results are saved in two files:
- ```part_data.json```: Contains the search results from Mouser.
- ```updated_BOM.tsv```: The updated BOM with pricing information.

## Logging
The script logs its progress to the console, including when it starts searching for each part number, any errors encountered, and when files are successfully saved.