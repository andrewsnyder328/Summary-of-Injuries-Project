import sys
import os
import logging
import json
import concurrent.futures
from pdf2image import convert_from_path

from utils import extract_text_from_image, combine_page_contents, extract_icd10_code_from_results, \
    search_icd10_code, generate_search_query


def process_pdf_file(pdf_path):
    """Process a single PDF file and generate the markdown summary."""
    pdf_file = os.path.basename(pdf_path)
    document_name = os.path.splitext(pdf_file)
    logging.info(f"Processing '{pdf_file}'...")

    try:
        images = convert_from_path(pdf_path)
    except Exception as e:
        logging.error(f"Error converting PDF to images '{pdf_file}': {e}")
        return

    def process_page(page_tuple):
        page_number, image = page_tuple
        logging.info(f"Processing page {page_number + 1} of '{pdf_file}'...")
        assistant_message = extract_text_from_image(image, page_number=page_number + 1)
        return page_number, assistant_message

    # Initialize an empty list to store tuples of (page_number, assistant_message)
    page_results = []

    # Process pages in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for page_number, image in enumerate(images):
            futures.append(executor.submit(process_page, (page_number, image)))

        for future in concurrent.futures.as_completed(futures):
            page_number, assistant_message = future.result()
            if assistant_message:
                # Store (page_number, assistant_message) as a tuple
                page_results.append((page_number, assistant_message))
            else:
                logging.error(f"Text extraction failed for page {page_number + 1} of '{pdf_file}'.")

    # Ensure page_results is sorted by page_number
    page_results.sort(key=lambda x: x[0])

    if not page_results:
        logging.warning(f"No valid content extracted from '{pdf_file}'.")
        return

    # Now, process each page_result along with its page_number
    page_contents = []
    for page_number, page_result in page_results:
        try:
            page_json = json.loads(page_result)
            page_json["page_number"] = page_number + 1  # Adjust for 1-based page numbers
            page_contents.append(page_json)
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing JSON on page {page_number + 1} of '{pdf_file}': {e}")
            continue

    if not page_contents:
        logging.warning(f"No valid JSON content to combine for '{pdf_file}'.")
        return

    print("Combining pages...")
    combined_message = combine_page_contents(page_contents)

    if combined_message:
        try:
            combined_json = json.loads(combined_message)
            if "markdown" in combined_json:
                combined_markdown = combined_json["markdown"]

                # Optional: Save the extracted markdown content to a file
                # output_md_path = os.path.join(output_folder, f"{document_name}_summary.md")
                # save_markdown(output_md_path, combined_markdown)

                # Generate Search Query and Extract Information
                extracted_info = generate_search_query(
                    combined_markdown,
                    document_name
                )
                if not extracted_info:
                    logging.error(f"Failed to generate search query and extract information for '{pdf_file}'.")
                    return

                date_of_visit = extracted_info["date_of_visit"]
                diagnosis = extracted_info["diagnosis"]
                reference = extracted_info["reference"]
                query = extracted_info["query"]

                logging.info(f"Extracted Date of Visit: {date_of_visit}")
                logging.info(f"Extracted Diagnosis: {diagnosis}")
                logging.info(f"Extracted Reference: {reference}")
                logging.info(f"Generated Search Query: {query}")

                # Perform Web Search
                search_results = search_icd10_code(query)
                if not search_results:
                    logging.error(f"Failed to retrieve search results for '{pdf_file}'.")
                    return

                # Extract ICD-10 Code from Results
                icd10_code = extract_icd10_code_from_results(search_results)
                if not icd10_code:
                    logging.error(f"Failed to extract ICD-10 code for '{pdf_file}'.")
                    return

                logging.info(f"Extracted ICD-10 code: {icd10_code}")

                # Collect the Record
                record = {
                    "date_of_visit": date_of_visit,
                    "diagnosis": diagnosis,
                    "icd10_code": icd10_code,
                    "reference": reference,
                }

                # Return the record to be added to the summary table
                return record
            else:
                logging.error(f"No 'markdown' key found in combined response for '{pdf_file}'.")
                return
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing combined JSON for '{pdf_file}': {e}")
            return
    else:
        logging.error(f"Content combination failed for '{pdf_file}'.")


def generate_summary_table(records, output_folder):
    """Generate the summary table as a PDF or acceptable text format."""
    # Sort records in reverse chronological order (latest date first)
    # For simplicity, dates are treated as strings; parsing may be needed for proper sorting
    records_sorted = sorted(records, key=lambda x: x['date_of_visit'], reverse=True)

    # Create a simple Markdown table
    table_lines = [
        "| Date of Visit | Diagnosis | ICD-10 Code | Reference |",
        "|---------------|-----------|-------------|-----------|",
    ]

    for record in records_sorted:
        line = f"| {record['date_of_visit']} | {record['diagnosis']} | {record['icd10_code']} | {record['reference']} |"
        table_lines.append(line)

    summary_content = "\n".join(table_lines)

    # Save the summary to a markdown file
    output_summary_path = os.path.join(output_folder, "summary_of_injuries.md")
    with open(output_summary_path, 'w', encoding='utf-8') as f:
        f.write(summary_content)

    logging.info(f"Summary of Injuries saved to '{output_summary_path}'.")

    # Optionally, convert the markdown to PDF using a library like `pdfkit` or `weasyprint`
    # For now, we will keep it in markdown format as acceptable per instructions


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

    records = []  # List to store all records

    for pdf_file in pdf_files:
        record = process_pdf_file(pdf_file)
        if record:
            records.append(record)

    if records:
        generate_summary_table(records, output_folder)
    else:
        logging.warning("No records to generate summary table.")


if __name__ == "__main__":
    main()
