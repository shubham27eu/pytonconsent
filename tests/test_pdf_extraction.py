import unittest
import os
from app.services.pdf_extraction_service import PDFExtractionService
from app.models import DocumentType, DocumentField, FieldClassification
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

class PDFExtractionServiceTestCase(unittest.TestCase):
    def setUp(self):
        # Define a document type that matches the sample PDF's fields
        self.doc_type = DocumentType(name="ProFormaInvoice")
        self.doc_type.fields.append(DocumentField(name="Pro forma invoice No.", classification=FieldClassification.OPEN))
        self.doc_type.fields.append(DocumentField(name="Issue date", classification=FieldClassification.OPEN))
        self.doc_type.fields.append(DocumentField(name="Due date", classification=FieldClassification.CONTROLLED))
        self.doc_type.fields.append(DocumentField(name="TOTAL (GBP)", classification=FieldClassification.CONTROLLED))
        # This field name is slightly different in the PDF ("TOTAL DUE (GBP)"), so it should not be found by this name.
        self.doc_type.fields.append(DocumentField(name="Total Due", classification=FieldClassification.CONTROLLED))

        # Create a dummy file path. This assumes the test runs from the project root.
        self.sample_pdf_path = os.path.join(os.path.dirname(__file__), 'samples', 'invoice.pdf')

        # Ensure the sample directory exists
        os.makedirs(os.path.dirname(self.sample_pdf_path), exist_ok=True)

        # Generate a simple, valid PDF for testing
        c = canvas.Canvas(self.sample_pdf_path, pagesize=letter)
        textobject = c.beginText()
        textobject.setTextOrigin(50, 750) # x, y from bottom left
        textobject.setFont("Helvetica", 10)

        lines = [
            "Pro forma invoice No.: 0012022",
            "Issue date: 30/04/2022",
            "Due date: 14/05/2022",
            "",
            "DESCRIPTION QUANTITY UNIT PRICE (€) AMOUNT (E)",
            "Sample service 1 400.00 400.00",
            "Sample service 1 1 200.00 200.00",
            "",
            "TOTAL (GBP): £600.00",
            "TOTAL DUE (GBP): £600.00"
        ]
        for line in lines:
            textobject.textLine(line)

        c.drawText(textobject)
        c.save()


    def tearDown(self):
        # Clean up the dummy file and directory
        if os.path.exists(self.sample_pdf_path):
            os.remove(self.sample_pdf_path)
        # Clean up directory if empty
        try:
            os.rmdir(os.path.dirname(self.sample_pdf_path))
        except OSError:
            pass # Directory not empty, or does not exist

    def test_extract_data_from_pdf(self):
        extracted_data = PDFExtractionService.extract_data(self.sample_pdf_path, self.doc_type)

        self.assertIsNotNone(extracted_data)
        self.assertNotIn("_pdf_extraction_error", extracted_data)

        self.assertEqual(extracted_data.get("Pro forma invoice No."), "0012022")
        self.assertEqual(extracted_data.get("Issue date"), "30/04/2022")
        self.assertEqual(extracted_data.get("Due date"), "14/05/2022")
        self.assertEqual(extracted_data.get("TOTAL (GBP)"), "£600.00")

        # "Total Due" should not be found because the label in the PDF is "TOTAL DUE (GBP)"
        self.assertIsNone(extracted_data.get("Total Due"))

    def test_extract_data_file_not_found(self):
        # The service itself doesn't check for file existence, the DocumentService does.
        # But if pdfplumber is given a bad path, it should raise an error.
        bad_path = "/path/to/nonexistent/file.pdf"
        # We expect our service to catch the exception and return a dict with an error key.
        extracted_data = PDFExtractionService.extract_data(bad_path, self.doc_type)
        self.assertIn("_pdf_extraction_error", extracted_data)

if __name__ == '__main__':
    unittest.main()
