import fitz  # PyMuPDF
from PIL import Image
import io
import os
from pathlib import Path

class PdfProcessor:
    """Handles PDF related operations for image extraction"""
    
    @staticmethod
    def pdf_to_images(pdf_path, dpi=300):
        """
        Convert PDF pages to PIL images
        
        Args:
            pdf_path: Path to the PDF file
            dpi: Dots per inch for rendering (higher is better for OCR)
            
        Returns:
            List of PIL Image objects
        """
        images = []
        try:
            doc = fitz.open(pdf_path)
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                images.append(img.convert("RGB"))
            doc.close()
        except Exception as e:
            print(f"Error converting PDF to images: {e}")
            
        return images

    @staticmethod
    def batch_extract_pdf(pdf_path, output_base_folder, progress_callback=None, visual_callback=None):
        """
        Extract images from a PDF file
        """
        # This will be called by the PdfExtractorMode
        # It's essentially a wrapper around pdf_to_images + ImageProcessor.extract_from_pil_images
        pass
