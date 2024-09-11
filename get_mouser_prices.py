import os
import yaml
import csv
import json
import requests
from urllib.parse import urlparse
from datetime import datetime
import time
from typing import List, Dict, Any, Optional, Tuple

class APIManager:
    """
    Handles API-related operations, including fetching the API key and searching for part numbers using the Mouser API.
    """
    BASE_URL = 'https://api.mouser.com/api/v1/search/partnumber'

    @staticmethod
    def get_api_key() -> str:
        """
        Retrieve the API key for part searches from environment variables or a configuration file.

        Raises:
            FileNotFoundError: If the configuration file is not found.
            ValueError: If the API key is not available in either environment variables or configuration file.

        Returns:
            str: The API key as a string.
        """
        try:
            api_key: Optional[str] = os.environ.get('MOUSER_SEARCH_API_KEY')

            if not api_key:
                with open('mouser_api_keys.yaml', 'r') as f:
                    keys = yaml.safe_load(f)
                    if keys is None:
                        raise ValueError("The 'mouser_api_keys.yaml' file is empty or not formatted correctly.")
                    api_key = keys.get('search_api_key', '').strip()

            if not api_key:
                raise ValueError("API key is required. Set it as 'MOUSER_SEARCH_API_KEY' in the environment or provide 'mouser_api_keys.yaml'.")

            return api_key
        except FileNotFoundError:
            raise FileNotFoundError("Configuration file 'mouser_api_keys.yaml' not found.")
        except Exception as e:
            raise Exception(f"Error obtaining API key: {e}")

    @staticmethod
    def search_part_number(part_number: str, api_key: str, option: str = 'Exact') -> Optional[Dict[str, Any]]:
        """
        Search for a part number using the Mouser API.

        Args:
            part_number (str): The part number to search for.
            api_key (str): The API key for authentication.
            option (str): The search option, default to 'Exact'.

        Returns:
            Optional[Dict[str, Any]]: The search result as a dictionary or None if an error occurs.
        """
        try:
            url = f"{APIManager.BASE_URL}?apiKey={api_key}"
            headers = {'Content-Type': 'application/json'}
            payload = {'SearchByPartRequest': {'mouserPartNumber': part_number, 'partSearchOptions': option}}
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            DataProcessor.log_message(f"HTTP error occurred while searching for '{part_number}': {e}")
            return None
        except Exception as e:
            DataProcessor.log_message(f"Error occurred while searching for '{part_number}': {e}")
            return None

class DataProcessor:
    """
    Handles data processing tasks, including reading CSV files, extracting part numbers from URLs, and saving results to a file.
    """
    @staticmethod
    def create_output_directory(base_path: str = 'output') -> str:
        """
        Creates a timestamped output directory and returns its path.

        Args:
            base_path (str): The base path where the output directory will be created.

        Returns:
            str: The path to the created output directory.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = os.path.join(base_path, timestamp)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    @staticmethod
    def log_message(message: str) -> None:
        """
        Logs a message to the console. Can be replaced with a more sophisticated logging system if needed.

        Args:
            message (str): The message to log.
        """
        print(message)

    @staticmethod
    def read_csv_and_search_parts(file_path: str, output_dir: str, option: str = 'Exact') -> Dict[str, Any]:
        """
        Read a CSV file, extract part numbers from URLs, and search for each part number using the Mouser API.

        Args:
            file_path (str): Path to the CSV file.
            output_dir (str): Path to the output directory where files will be saved.
            option (str): The search option, default to 'Exact'.

        Returns:
            Dict[str, Any]: A dictionary with part numbers as keys and their respective search results as values.
        """
        api_key = APIManager.get_api_key()
        results: Dict[str, Any] = {}
        urls: List[str] = DataProcessor.extract_urls(file_path)

        if not urls:
            DataProcessor.log_message("Error: No URLs extracted from the CSV file.")
            return results

        mouser_part_numbers, non_mouser_urls, error_urls = DataProcessor.extract_part_numbers_from_urls(urls)

        if non_mouser_urls:
            DataProcessor.log_message("\nThe following URLs are not from Mouser and will not be processed:")
            for url in non_mouser_urls:
                DataProcessor.log_message(url)
            DataProcessor.log_message("")

        if error_urls:
            DataProcessor.log_message("\nThe following URLs caused errors during processing:")
            for url in error_urls:
                DataProcessor.log_message(url)
            DataProcessor.log_message("")

        api_error_parts: List[str] = []
        index = 0
        wait_time = 15  # seconds to wait after rate limit is hit

        while index < len(mouser_part_numbers):
            part_number = mouser_part_numbers[index]
            DataProcessor.log_message(f"Searching for part number: {part_number}")
            try:
                result = APIManager.search_part_number(part_number, api_key, option)
                if result:
                    results[part_number] = result
                    index += 1  # move to the next part number only if successful
                else:
                    # If the result is None, we assume it was due to rate limiting, wait and retry
                    DataProcessor.log_message(f"Rate limit reached. Waiting for {wait_time} seconds before retrying...")
                    time.sleep(wait_time)

            except Exception as e:
                DataProcessor.log_message(f"Error searching for part number '{part_number}': {e}")
                api_error_parts.append(part_number)
                index += 1  # move to the next part number after logging the error

        if api_error_parts:
            DataProcessor.log_message("\nThe following part numbers caused errors during API search:")
            for part in api_error_parts:
                DataProcessor.log_message(part)

        return results

    @staticmethod
    def extract_urls(file_path: str) -> List[str]:
        """
        Extract URLs from the 'Datasheet' column of the CSV file.

        Args:
            file_path (str): Path to the CSV file.

        Returns:
            List[str]: A list of URLs extracted from the file.
        """
        urls: List[str] = []
        with open(file_path, mode='r') as file:
            csv_reader = csv.DictReader(file)
            if 'Datasheet' not in csv_reader.fieldnames:
                DataProcessor.log_message("Error: The CSV file does not have a 'Datasheet' column.")
                return []

            urls = [row['Datasheet'].strip() for row in csv_reader if row['Datasheet'].strip()]
        return urls

    @staticmethod
    def extract_part_numbers_from_urls(urls: List[str]) -> Tuple[List[str], List[str], List[str]]:
        """
        Extract part numbers from Mouser URLs, separate non-Mouser URLs, and handle errors.

        Args:
            urls (List[str]): List of URLs to process.

        Returns:
            Tuple[List[str], List[str], List[str]]: A tuple containing lists of Mouser part numbers, non-Mouser URLs, and errored URLs.
        """
        mouser_part_numbers: List[str] = []
        non_mouser_urls: List[str] = []
        error_urls: List[str] = []

        for url in urls:
            try:
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.lower()

                if 'mouser.com' in domain:
                    part_number = parsed_url.path.split('/')[-1].strip()
                    mouser_part_numbers.append(part_number)
                else:
                    non_mouser_urls.append(url)

            except Exception as e:
                DataProcessor.log_message(f"Error processing URL '{url}': {e}")
                error_urls.append(url)

        return mouser_part_numbers, non_mouser_urls, error_urls

    @staticmethod
    def save_results_to_file(results: Dict[str, Any], output_dir: str) -> None:
        """
        Save the results to a file in the output directory.

        Args:
            results (Dict[str, Any]): The dictionary containing part numbers and their respective data.
            output_dir (str): The path to the output directory where the file will be saved.
        """
        output_file = os.path.join(output_dir, 'part_data.json')

        with open(output_file, 'w') as file:
            json.dump(results, file, indent=4)

        DataProcessor.log_message(f"Results successfully saved to {output_file}")

    @staticmethod
    def find_price_for_quantity(price_breaks: List[Dict[str, Any]], target_quantity: int) -> float:
        """
        Finds the price for the target quantity. If the exact quantity is not found, it calculates the nearest price 
        by summing up smaller quantities.

        Args:
            price_breaks (List[Dict[str, Any]]): List of price breaks from the search results.
            target_quantity (int): The quantity to find the price for.

        Returns:
            float: The calculated or estimated price.
        """
        price_dict = {break_info['Quantity']: float(break_info['Price'].replace('kr ', '').replace(',', '.')) for break_info in price_breaks}
        
        if target_quantity in price_dict:
            return price_dict[target_quantity]

        # If the exact quantity is not found, find the nearest lower quantity
        sorted_quantities = sorted(price_dict.keys(), reverse=True)
        nearest_price = 0
        remaining_quantity = target_quantity
        
        for quantity in sorted_quantities:
            if quantity <= remaining_quantity:
                num_units = remaining_quantity // quantity
                nearest_price += num_units * price_dict[quantity]
                remaining_quantity %= quantity
        
        return nearest_price if nearest_price > 0 else price_dict[sorted_quantities[-1]] * (target_quantity // sorted_quantities[-1])

    @staticmethod
    def extract_prices_and_save_to_csv(results: Dict[str, Any], input_file_path: str, output_dir: str, exclude_invalid_urls: bool = False) -> None:
        """
        Matches the parts to their respective places in the initial input file and saves the updated data to a new TSV file.

        Args:
            results (Dict[str, Any]): The search results for all parts.
            input_file_path (str): Path to the original BOM input file.
            output_dir (str): The path to the output directory where the CSV file will be saved.
            exclude_invalid_urls (bool): If True, exclude rows with invalid or empty URLs.
        """
        with open(input_file_path, mode='r') as infile:
            reader = csv.DictReader(infile)
            input_data = list(reader)

        output_file = os.path.join(output_dir, 'updated_BOM.tsv')

        with open(output_file, mode='w', newline='') as tsvfile:
            writer = csv.DictWriter(tsvfile, fieldnames=reader.fieldnames + ['Price for 1', 'Price for 10', 'Price for 100', 'Price for 1000'], delimiter='\t')

            for row in input_data:
                # Check for valid URLs if exclusion is enabled
                if exclude_invalid_urls and (not row['Datasheet'] or row['Datasheet'].strip() in ['~', '']):
                    continue

                part_number = urlparse(row['Datasheet']).path.split('/')[-1]
                if part_number in results:
                    search_results = results[part_number].get('SearchResults', {})
                    parts = search_results.get('Parts', [])
                    if parts:
                        part = parts[0]
                        price_breaks = part.get('PriceBreaks', [])

                        price_1 = DataProcessor.find_price_for_quantity(price_breaks, 1)
                        price_10 = DataProcessor.find_price_for_quantity(price_breaks, 10)
                        price_100 = DataProcessor.find_price_for_quantity(price_breaks, 100)
                        price_1000 = DataProcessor.find_price_for_quantity(price_breaks, 1000)

                        row.update({
                            'Price for 1': f"{price_1:.2f}",
                            'Price for 10': f"{price_10:.2f}",
                            'Price for 100': f"{price_100:.2f}",
                            'Price for 1000': f"{price_1000:.2f}"
                        })

                writer.writerow(row)

        DataProcessor.log_message(f"Updated BOM with prices saved to {output_file}")

def main(exclude_invalid_urls: bool = False) -> None:
    """
    Main function to execute the CSV reading, part searching process, and price extraction.

    Args:
        exclude_invalid_urls (bool): If True, exclude rows with invalid or empty URLs from the output.
    """
    csv_file_path = 'BOM_.csv'

    if not os.path.exists(csv_file_path):
        print(f"Error: File '{csv_file_path}' does not exist.")
        return

    # Create the output directory once and reuse it
    output_dir = DataProcessor.create_output_directory()

    extracted_bom_data = DataProcessor.read_csv_and_search_parts(csv_file_path, output_dir)

    # Save the results JSON file in the created output directory
    DataProcessor.save_results_to_file(extracted_bom_data, output_dir)

    # Extract prices and match with the input data to save to a new CSV file in the same output directory
    DataProcessor.extract_prices_and_save_to_csv(extracted_bom_data, csv_file_path, output_dir, exclude_invalid_urls)

if __name__ == '__main__':
    import sys
    exclude_invalid = '--exclude-invalid-urls' in sys.argv
    main(exclude_invalid_urls=exclude_invalid)
