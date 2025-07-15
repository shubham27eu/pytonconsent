import pdfplumber
import re
from app.models import DocumentType, DocumentField

class PDFExtractionService:
    @staticmethod
    def extract_data(file_path: str, document_type: DocumentType) -> dict:
        """
        Extracts data from a PDF file based on the fields defined in a DocumentType.

        This is a simple implementation that looks for the field name as a label
        and assumes the value follows it on the same line.

        Args:
            file_path: The local path to the PDF file.
            document_type: The DocumentType object containing the fields to extract.

        Returns:
            A dictionary where keys are field names and values are the extracted strings.
            Returns an empty dict if the file cannot be opened or no data is found.
        """
        extracted_data = {}
        try:
            with pdfplumber.open(file_path) as pdf:
                full_text = ""
                for page in pdf.pages:
                    full_text += page.extract_text() + "\n"

                # A simple line-based extraction logic
                lines = full_text.split('\n')
                for field in document_type.fields:
                    field_name = field.name
                    # Use a more robust key-value logic based on splitting by colon.
                    found_value = None
                    search_label = field_name.lower()

                    for line in lines:
                        # Split line at the first colon to separate potential label from value
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            label_part = parts[0].strip().lower()
                            value_part = parts[1].strip()

                            # Check for an exact match of the label
                            if label_part == search_label:
                                found_value = value_part
                                break # Found it, stop searching for this field

                    if found_value:
                        extracted_data[field_name] = found_value
                    else:
                        # If not found, we could try other strategies, but for now, we'll just
                        # note that it wasn't found by not adding it to the dict.
                        pass

        except Exception as e:
            # In a real application, log this error properly.
            print(f"Error processing PDF file {file_path}: {e}")
            # Depending on policy, you might want to raise the exception
            # or return a dict with an error key.
            return {"_pdf_extraction_error": str(e)}

        return extracted_data
