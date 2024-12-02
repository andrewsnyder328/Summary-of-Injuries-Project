# Summary of Injuries Generator

This project is a console application that automates the process of creating a "Summary of Injuries" section for a demand letter based on provided medical records in PDF format.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Setup](#setup)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Notes](#notes)
- [License](#license)

---

## Features

- Extracts text from medical PDFs using AI techniques (not regex).
- Processes and combines extracted data into a structured Markdown table.
- Fetches the corresponding ICD-10 codes for the diagnoses using web search.
- Generates a "Summary of Injuries" in Markdown format (acceptable as per instructions).

## Requirements

- Python 3.7 or higher
- [OpenAI API Key](https://platform.openai.com)
- [SerpAPI Key](https://serpapi.com)
- Poppler (for PDF processing)
  - **Note for Windows users**: You need to install Poppler and add it to your PATH.

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/summary-of-injuries.git
   cd summary-of-injuries
   ```

2. **Create a Virtual Environment**

   It's recommended to use a virtual environment to manage dependencies.

   ```bash
   python -m venv venv
   ```

3. **Activate the Virtual Environment**

   - **Windows**:

     ```bash
     venv\Scripts\activate
     ```

   - **Unix/Linux/MacOS**:

     ```bash
     source venv/bin/activate
     ```

4. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

## Setup

1. **Obtain API Keys**

   - **OpenAI API Key**
     - Sign up or log in to [OpenAI Platform](https://platform.openai.com).
     - Navigate to the API section and get your secret API key.

   - **SerpAPI Key**
     - Sign up or log in to [SerpAPI](https://serpapi.com).
     - Obtain your API key from the account dashboard.

2. **Configure Environment Variables**

   The application uses environment variables to securely manage API keys.

   - **Create a `.env` File**

     Create a file named `.env` in the root directory of the project.

     ```bash
     touch .env
     ```

   - **Add Your API Keys to the `.env` File**

     Open the `.env` file in a text editor and add your API keys:

     ```env
     OPENAI_API_KEY=your_openai_api_key_here
     SERPAPI_API_KEY=your_serpapi_api_key_here
     ```

     Replace `your_openai_api_key_here` and `your_serpapi_api_key_here` with your actual API keys.

3. **Set Up Poppler (For Windows Users Only)**

   - Download Poppler for Windows from [Poppler for Windows](http://blog.alivate.com.au/poppler-windows/).
   - Extract the downloaded zip file.
   - Add the `poppler/bin` folder to your system's PATH environment variable.

     **Adding to PATH:**

     - Open System Properties > Environment Variables.
     - Under System Variables, find and select the `Path` variable.
     - Click **Edit** and add the path to the `poppler/bin` folder.

## Usage

Run the script from the command line, providing the input folder containing PDF documents and the output folder where the summary will be saved.

```bash
python generate_summary_of_injuries.py /path/to/input_pdfs /path/to/output_summary
```

**Example:**

```bash
python generate_summary_of_injuries.py input_pdfs output_summary
```

### Parameters

- `/path/to/input_pdfs`: The directory containing the medical records in PDF format.
- `/path/to/output_summary`: The directory where the `summary_of_injuries.md` file will be saved.

## Project Structure

```
summary-of-injuries/
├── input_pdfs/
├── output_summary/
├── venv/
├── .env
├── .env_example
├── .gitignore
├── config.py
├── generate_summary_of_injuries.py
├── prompts.py
├── requirements.txt
└── utils.py
```

- `input_pdfs/`: Directory containing input PDF files.
- `output_summary/`: Directory where the output summary will be saved.
- `venv/`: Virtual environment directory.
- `.env`: Environment variables file containing API keys (not committed to version control).
- `.env_example`: Example of the `.env` file structure.
- `.gitignore`: Specifies intentionally untracked files to ignore.
- `config.py`: Configuration settings for the application.
- `generate_summary_of_injuries.py`: Main script to run the application.
- `prompts.py`: Contains system prompts for AI models.
- `requirements.txt`: Lists Python dependencies.
- `utils.py`: Utility functions used in the application.

## Notes

- **AI Models Used**: The application uses OpenAI GPT models for text extraction and processing. Ensure that your API key has access to the required models.
- **SerpAPI Usage**: SerpAPI is used to search for the ICD-10 codes corresponding to the diagnoses extracted from the medical records.
- **Output Format**: The final summary is saved in Markdown format as `summary_of_injuries.md` in the output directory.

## License

This project is for demonstration purposes and is not licensed for commercial use.

---

**Disclaimer**: This application is intended for educational purposes. Ensure compliance with all relevant laws and regulations when handling medical records and personal data. Always maintain patient confidentiality and privacy.