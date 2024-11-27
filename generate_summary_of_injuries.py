import sys
import os
import io
import base64
from dotenv import load_dotenv
import json
from openai import OpenAI
from pdf2image import convert_from_path

load_dotenv()

client = OpenAI()

EXTRACTION_SYSTEM_PROMPT = """
You are an office assistant tasked with aiding in manual data extraction from documents such as clinic visit notes.

**Instructions:**

1. **Text Extraction:**
   - You will be provided with an **image of a document**.
   - Your task is to **extract all the text** present on that page accurately.

2. **Hierarchy Identification:**
   - Identify the **hierarchy of content** within the text.
   - Use **nested indentation** denoted by **dashes ("-")** to represent different levels of hierarchy.
     - Each additional dash represents a deeper level in the hierarchy.

3. **Output Format:**
   - **Return the extracted text in a JSON object** with the following fields:
     - `"header"`: *(string, optional)* The text from the page header, if present.
     - `"content"`: *(string)* The main content of the page, with hierarchy indicated by dashes.
     - `"footer"`: *(string, optional)* The text from the page footer, if present.
   - Ensure the JSON is properly formatted and valid.

**Guidelines:**

- **Maintain the Original Order:** Keep the text in the same sequence as it appears in the document.
- **Accuracy is Key:** Transcribe the text exactly as it appears, including any headers, subheaders, bullet points, and numbering.
- **No Additional Interpretation:** Do not add any information or alter the text in any way.
- **Formatting within `content`:**
  - Use **line breaks (`\n`)** to separate different sections or headings.
  - Represent bullet points or numbered lists appropriately within the hierarchy using dashes.

---

**Example:**

*Assuming the following text is present in the image:*

- **Page Header:**  
  ```
  Confidential Medical Records
  ```
- **Main Content:**
  ```
  Patient Visit Summary

  Chief Complaint
  - Patient reports persistent cough
  - Duration: 2 weeks

  History of Present Illness
  - Cough is dry and non-productive
  - No associated fever or chills

  Medications
  - Currently taking over-the-counter cough syrup

  Plan
  - Recommend chest X-ray
  - Prescribe antitussive medication
  ```
- **Page Footer:**  
  ```
  Page 1 of 2
  ```

*Your response should be:*

```json
{
  "header": "Confidential Medical Records",
  "content": "Patient Visit Summary\n- Chief Complaint\n-- Patient reports persistent cough\n-- Duration: 2 weeks\n- History of Present Illness\n-- Cough is dry and non-productive\n-- No associated fever or chills\n- Medications\n-- Currently taking over-the-counter cough syrup\n- Plan\n-- Recommend chest X-ray\n-- Prescribe antitussive medication",
  "footer": "Page 1 of 2"
}
```

---

**Further Clarifications:**

- **Headers and Subheaders:** Treat any main titles or headings as higher levels in the hierarchy.
- **Content Under Headers:** Use additional dashes to indicate subheadings or content under each header.
- **Optional Elements:** If there's no page header or footer, you can omit those fields or set their values to `null` in the JSON object.

**Additional Example:**

*Example 2:*

*Image Text:*

- **Main Content Only:**
  ```
  Laboratory Results

  Complete Blood Count
  - WBC: 6.0 x10^3/µL
  - RBC: 4.5 x10^6/µL
  - Hemoglobin: 13.5 g/dL

  Metabolic Panel
  - Sodium: 140 mmol/L
  - Potassium: 4.0 mmol/L
  - Glucose: 90 mg/dL
  ```

*Response:*

```json
{
  "content": "Laboratory Results\n- Complete Blood Count\n-- WBC: 6.0 x10^3/µL\n-- RBC: 4.5 x10^6/µL\n-- Hemoglobin: 13.5 g/dL\n- Metabolic Panel\n-- Sodium: 140 mmol/L\n-- Potassium: 4.0 mmol/L\n-- Glucose: 90 mg/dL"
}
```
"""

COMBINE_SYSTEM_PROMPT = """
You are an assistant tasked with combining extracted document content into a single markdown-formatted output.

**Instructions:**

1. **Content Integration:**
   - You will be provided with a list of JSON objects, each representing the extracted content from individual pages of a document.
   - Each JSON object has the following fields:
     - `"header"`: *(string, optional)* The text from the page header.
     - `"content"`: *(string)* The main content of the page, with hierarchy indicated by dashes.
     - `"footer"`: *(string, optional)* The text from the page footer.
   - Concatenate the contents from all pages, maintaining the original sequence.

2. **Hierarchy Reconciliation:**
   - Reconcile varying indentation levels where sections continue from one page to the next.
   - Use your best judgment to ensure consistent hierarchy throughout the document.
   - Do not modify any content; only adjust indentation levels if necessary for consistency.

3. **Markdown Formatting:**
   - Convert the hierarchical content into appropriate markdown elements without altering the text.
     - Use `#`, `##`, `###`, etc., for headings corresponding to hierarchy levels.
     - Bullet points (`-` or `*`) should represent list items.
     - Maintain numbering and lists as they appear.

4. **Content Preservation:**
   - Under no circumstances should you modify the content.
   - Do not add, remove, or alter any text.
   - Focus solely on formatting the provided content into markdown.

**Output Format:**

- Return the combined content as a JSON object with one key:
  - `"markdown"`: *(string)* The combined markdown-formatted content.
- Ensure the JSON is properly formatted and valid.
- Do not include any additional commentary or notes.

**Example:**

*Given the following list of JSON objects:*

```json
[
  {
    "header": "Patient Visit Summary",
    "content": "- Chief Complaint\n-- Patient reports persistent cough\n-- Duration: 2 weeks",
    "footer": "Page 1 of 2"
  },
  {
    "content": "- Chief Complaint (continued)\n-- Severity: Moderate\n- History of Present Illness\n-- Cough is dry and non-productive",
    "footer": "Page 2 of 2"
  }
]
```

*Your output should be:*

```json
{
  "markdown": "# Patient Visit Summary\n\n## Chief Complaint\n\n- Patient reports persistent cough\n- Duration: 2 weeks\n- Severity: Moderate\n\n## History of Present Illness\n\n- Cough is dry and non-productive"
}
```

**Guidelines:**

- Use heading levels that correspond to the hierarchy indicated by dashes in the content.
- Headers from `"header"` fields are top-level headings.
- Maintain the order and exact wording of the content.
- Ensure continuity where sections span multiple pages.
- Do not include any extraneous text or explanations.
"""

GPT4O_MAX_OUTPUT_TOKENS = 16384


def main():
    if len(sys.argv) != 3:
        print("Usage: python generate_summary_of_injuries.py /path/to/input/folder /path/to/output/folder")
        sys.exit(1)

    input_folder = sys.argv[1]
    output_folder = sys.argv[2]

    # Validate input folder
    if not os.path.exists(input_folder):
        print(f"Input folder '{input_folder}' does not exist.")
        sys.exit(1)

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Get list of PDF files
    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]

    if not pdf_files:
        print(f"No PDF files found in the input folder '{input_folder}'.")
        sys.exit(1)

    for pdf_file in pdf_files:
        pdf_path = os.path.join(input_folder, pdf_file)
        print(f"Processing '{pdf_path}'...")

        try:
            images = convert_from_path(pdf_path)
            page_results = []

            for page_number, image in enumerate(images):
                print(f"Processing page {page_number + 1} of '{pdf_file}'...")

                # Encode image to base64
                buffered = io.BytesIO()
                image.save(buffered, format="JPEG")
                base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')

                # Prepare messages for extraction
                messages = [
                    {
                        "role": "system",
                        "content": EXTRACTION_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Please process the following image:",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    },
                ]

                # Call the AI model for extraction
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    response_format={
                        "type": "json_object"
                    },
                    temperature=0,
                    max_tokens=GPT4O_MAX_OUTPUT_TOKENS,
                )

                # Extract the JSON result
                assistant_message = response.choices[0].message.content
                page_results.append(assistant_message)

            print(f"Compiling results for {pdf_file}'...")

            # Combine page results
            page_contents = []
            for idx, page_result in enumerate(page_results):
                try:
                    page_json = json.loads(page_result)
                    page_contents.append(page_json)
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON on page {idx + 1} of '{pdf_file}': {e}")
                    continue

            if not page_contents:
                print(f"No valid content extracted from '{pdf_file}'.")
                continue

            # Prepare messages for combining
            combine_messages = [
                {
                    "role": "system",
                    "content": COMBINE_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": "Please combine the following page contents into a JSON output:",
                },
                {
                    "role": "user",
                    "content": json.dumps(page_contents),
                },
            ]

            # Call the AI model to combine contents
            combine_response = client.chat.completions.create(
                model="gpt-4o",
                messages=combine_messages,
                response_format={
                    "type": "json_object"
                },
                temperature=0,
                max_tokens=GPT4O_MAX_OUTPUT_TOKENS,
            )

            # Extract the combined markdown content
            combined_message = combine_response.choices[0].message.content.strip()

            # Parse the JSON to get the markdown content
            try:
                combined_json = json.loads(combined_message)
                if "markdown" in combined_json:
                    combined_markdown = combined_json["markdown"]
                else:
                    print(f"No 'markdown' key found in the response for '{pdf_file}'.")
                    continue
            except json.JSONDecodeError as e:
                print(f"Error parsing combined JSON for '{pdf_file}': {e}")
                continue

            # Save the output to a markdown file
            output_md_path = os.path.join(output_folder, f"{os.path.splitext(pdf_file)[0]}_summary.md")
            with open(output_md_path, 'w', encoding='utf-8') as f:
                f.write(combined_markdown)

            print(f"Combined markdown output saved to '{output_md_path}'.")

        except Exception as e:
            print(f"Failed to process '{pdf_file}'. Error: {e}")


if __name__ == "__main__":
    main()
