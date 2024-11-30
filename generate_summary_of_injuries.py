import sys
import os
import logging
import json
import concurrent.futures
from pdf2image import convert_from_path

from utils import extract_text_from_image, combine_page_contents, save_markdown


def process_pdf_file(pdf_path, output_folder):
    """Process a single PDF file and generate the markdown summary."""
    pdf_file = os.path.basename(pdf_path)
    logging.info(f"Processing '{pdf_file}'...")

    try:
        images = convert_from_path(pdf_path)
    except Exception as e:
        logging.error(f"Error converting PDF to images '{pdf_file}': {e}")
        return

    page_results = [None] * len(images)  # Initialize a list to store results

    def process_page(page_tuple):
        page_number, image = page_tuple
        logging.info(f"Processing page {page_number + 1} of '{pdf_file}'...")
        assistant_message = extract_text_from_image(image, page_number=page_number + 1)
        return (page_number, assistant_message)

    # Process pages in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for page_number, image in enumerate(images):
            futures.append(executor.submit(process_page, (page_number, image)))

        for future in concurrent.futures.as_completed(futures):
            page_number, assistant_message = future.result()
            if assistant_message:
                page_results[page_number] = assistant_message
            else:
                logging.error(f"Text extraction failed for page {page_number + 1} of '{pdf_file}'.")

    # Remove None entries and ensure order
    page_results = [result for result in page_results if result is not None]

    if not page_results:
        logging.warning(f"No valid content extracted from '{pdf_file}'.")
        return

    page_contents = []
    for idx, page_result in enumerate(page_results):
        try:
            page_json = json.loads(page_result)
            page_contents.append(page_json)
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing JSON on page {idx + 1} of '{pdf_file}': {e}")
            continue

    if not page_contents:
        logging.warning(f"No valid JSON content to combine for '{pdf_file}'.")
        return

    combined_message = combine_page_contents(page_contents)

    if combined_message:
        try:
            combined_json = json.loads(combined_message)
            if "markdown" in combined_json:
                combined_markdown = combined_json["markdown"]
            else:
                logging.error(f"No 'markdown' key found in combined response for '{pdf_file}'.")
                return
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing combined JSON for '{pdf_file}': {e}")
            return

        output_md_path = os.path.join(output_folder, f"{os.path.splitext(pdf_file)[0]}_summary.md")
        save_markdown(output_md_path, combined_markdown)
    else:
        logging.error(f"Content combination failed for '{pdf_file}'.")


def main():
    if len(sys.argv) != 3:
        print("Usage: python generate_summary_of_injuries.py /path/to/input/folder /path/to/output/folder")
        sys.exit(1)

    input_folder = sys.argv[1]
    output_folder = sys.argv[2]

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s:%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Validate input folder
    if not os.path.exists(input_folder):
        logging.error(f"Input folder '{input_folder}' does not exist.")
        sys.exit(1)

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Get list of PDF files
    pdf_files = [os.path.join(input_folder, f) for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]

    if not pdf_files:
        logging.warning(f"No PDF files found in the input folder '{input_folder}'.")
        sys.exit(1)

    for pdf_file in pdf_files:
        process_pdf_file(pdf_file, output_folder)


if __name__ == "__main__":
    main()
