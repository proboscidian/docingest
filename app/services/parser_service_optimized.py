from unstructured.partition.pdf import partition_pdf
from unstructured.partition.docx import partition_docx
from unstructured.partition.text import partition_text
import pytesseract
import easyocr
from PIL import Image
import io
import fitz  # PyMuPDF
from typing import List, Dict, Tuple
import time
from app.models.query import ParsedDocument, ParsedPage
from app.utils.config import get_settings
from app.utils.logging_optimized import get_logger, log_error
from app.utils.security import chunk_text

# Tesseract OCR Configuration
import os
import pytesseract

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = "/var/www/vhosts/old.industrialwebworks.net/mamba/envs/docingest/bin/tesseract"
os.environ.setdefault("TESSDATA_PREFIX", "/var/www/vhosts/old.industrialwebworks.net/mamba/envs/docingest/share/tessdata")



logger = get_logger(__name__)

class ParserService:
    """Document parsing and OCR service"""
    
    def __init__(self):
        self.settings = get_settings()
        self.ocr_enabled = True
    
    def parse_document(self, content: bytes, mime_type: str, filename: str) -> ParsedDocument:
        """Parse document and extract text with page information"""
        start_time = time.time()
        
        try:
            if mime_type == "application/pdf":
                return self._parse_pdf(content, filename)
            elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                return self._parse_docx(content, filename)
            elif mime_type in ["text/plain", "text/csv"]:
                return self._parse_text(content, filename)
            else:
                raise Exception(f"Unsupported MIME type: {mime_type}")
                
        except Exception as e:
            log_error(e, f"Error parsing document {filename}")
            raise Exception(f"Failed to parse document: {e}")
        finally:
            processing_time = time.time() - start_time
            logger.info(f"Document {filename} processed in {processing_time:.2f} seconds")
    
    def _parse_pdf(self, content: bytes, filename: str) -> ParsedDocument:
        """Parse PDF document"""
        try:
            # Use PyMuPDF for better page-by-page processing
            doc = fitz.open(stream=content, filetype="pdf")
            pages = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract text
                text = page.get_text()
                has_text = len(text.strip()) > 0
                
                parsed_page = ParsedPage(
                    page_number=page_num + 1,
                    text=text.strip(),
                    has_text=has_text,
                    needs_ocr=False,
                    confidence=None
                )
                
                # If no text, try OCR
                if not has_text and self.ocr_enabled:
                    try:
                        # Convert page to image
                        mat = fitz.Matrix(2.0, 2.0)  # Scale factor
                        pix = page.get_pixmap(matrix=mat)
                        img_data = pix.tobytes("png")
                        
                        # Perform OCR - try Tesseract first, fallback to EasyOCR
                        image = Image.open(io.BytesIO(img_data))
                        
                        try:
                            # Try Tesseract first (industry standard, lighter)
                            ocr_text = pytesseract.image_to_string(image, config='--oem 1 --psm 6')
                        except Exception as tesseract_error:
                            logger.warning(f"Tesseract failed for page {page_num + 1} in {filename}, falling back to EasyOCR: {tesseract_error}")
                            try:
                                # Fallback to EasyOCR
                                reader = easyocr.Reader(['en'])
                                ocr_results = reader.readtext(img_data)
                                ocr_text = ' '.join([result[1] for result in ocr_results])
                            except Exception as easyocr_error:
                                logger.error(f"Both Tesseract and EasyOCR failed for page {page_num + 1} in {filename}: {easyocr_error}")
                                ocr_text = ""
                        
                        parsed_page.text = ocr_text.strip()
                        parsed_page.has_text = len(ocr_text.strip()) > 0
                        parsed_page.needs_ocr = True
                        parsed_page.confidence = 0.8  # Default confidence
                        
                    except Exception as ocr_error:
                        log_error(ocr_error, f"OCR failed for page {page_num + 1} in {filename}")
                
                pages.append(parsed_page)
            
            doc.close()
            
            return ParsedDocument(
                doc_id=filename,
                title=filename,
                mime_type="application/pdf",
                pages=pages,
                total_pages=len(pages),
                processing_time=time.time() - time.time()
            )
            
        except Exception as e:
            log_error(e, f"Error parsing PDF {filename}")
            raise
    
    def _parse_docx(self, content: bytes, filename: str) -> ParsedDocument:
        """Parse DOCX document"""
        try:
            # Use unstructured for DOCX parsing
            elements = partition_docx(file=io.BytesIO(content))
            
            # Group elements by page (approximate)
            pages = []
            current_page_text = ""
            page_num = 1
            
            for element in elements:
                element_text = str(element).strip()
                if element_text:
                    current_page_text += element_text + "\n"
                    
                    # Simple page break detection (can be improved)
                    if len(current_page_text) > 2000:  # Arbitrary page size
                        pages.append(ParsedPage(
                            page_number=page_num,
                            text=current_page_text.strip(),
                            has_text=True,
                            needs_ocr=False
                        ))
                        current_page_text = ""
                        page_num += 1
            
            # Add remaining text as last page
            if current_page_text.strip():
                pages.append(ParsedPage(
                    page_number=page_num,
                    text=current_page_text.strip(),
                    has_text=True,
                    needs_ocr=False
                ))
            
            return ParsedDocument(
                doc_id=filename,
                title=filename,
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                pages=pages,
                total_pages=len(pages),
                processing_time=time.time() - time.time()
            )
            
        except Exception as e:
            log_error(e, f"Error parsing DOCX {filename}")
            raise
    
    def _parse_text(self, content: bytes, filename: str) -> ParsedDocument:
        """Parse plain text document"""
        try:
            text = content.decode('utf-8', errors='ignore')
            
            # Split into pages (simple approach)
            lines = text.split('\n')
            pages = []
            current_page_text = ""
            page_num = 1
            
            for line in lines:
                current_page_text += line + "\n"
                
                # Simple page break detection
                if len(current_page_text) > 2000:  # Arbitrary page size
                    pages.append(ParsedPage(
                        page_number=page_num,
                        text=current_page_text.strip(),
                        has_text=True,
                        needs_ocr=False
                    ))
                    current_page_text = ""
                    page_num += 1
            
            # Add remaining text as last page
            if current_page_text.strip():
                pages.append(ParsedPage(
                    page_number=page_num,
                    text=current_page_text.strip(),
                    has_text=True,
                    needs_ocr=False
                ))
            
            return ParsedDocument(
                doc_id=filename,
                title=filename,
                mime_type="text/plain",
                pages=pages,
                total_pages=len(pages),
                processing_time=time.time() - time.time()
            )
            
        except Exception as e:
            log_error(e, f"Error parsing text file {filename}")
            raise
    
    def chunk_document(self, parsed_doc: ParsedDocument) -> List[Dict]:
        """Chunk document into smaller pieces for embedding"""
        chunks = []
        
        for page in parsed_doc.pages:
            if not page.has_text:
                continue
            
            # Split page text into chunks
            page_chunks = chunk_text(page.text, self.settings.chunk_size, self.settings.chunk_overlap)
            
            for chunk_idx, chunk_content in enumerate(page_chunks):
                chunk_data = {
                    "tenant": "",  # Will be set by caller
                    "doc_id": parsed_doc.doc_id,
                    "title": parsed_doc.title,
                    "drive_path": "",  # Will be set by caller
                    "mime_type": parsed_doc.mime_type,
                    "page": page.page_number,
                    "chunk_idx": chunk_idx,
                    "sha256": "",  # Will be set by caller
                    "text": chunk_content
                }
                chunks.append(chunk_data)
        
        return chunks
