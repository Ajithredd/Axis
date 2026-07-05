"""
Document uploads API for adding context to projects.
"""

import uuid
import logging
from typing import List

import fitz  # PyMuPDF
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.project import Project
from app.models.document import ProjectDocument
from app.services.embedding import chunk_text, content_hash
from app.services.vector_sync import sync_node_to_vector_store

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

@router.post("/upload")
async def upload_document(
    project_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a document (PDF, TXT, MD) to provide additional context for a project.
    """
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project_id format")

    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == pid))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Read file content
    content_bytes = await file.read()
    size_bytes = len(content_bytes)

    # Check file size limit
    if size_bytes > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {MAX_FILE_SIZE // (1024*1024)}MB limit."
        )

    # Parse text based on content type or extension
    filename = file.filename or "unknown"
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    
    extracted_text = ""
    
    try:
        if ext == "pdf" or file.content_type == "application/pdf":
            # Use PyMuPDF to extract text
            pdf_document = fitz.open(stream=content_bytes, filetype="pdf")
            pages_text = []
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                pages_text.append(page.get_text())
            extracted_text = "\n".join(pages_text)
            pdf_document.close()
        elif ext in ["txt", "md"] or file.content_type in ["text/plain", "text/markdown"]:
            extracted_text = content_bytes.decode("utf-8")
        else:
            raise HTTPException(
                status_code=400, 
                detail="Unsupported file type. Please upload a PDF, TXT, or MD file."
            )
    except Exception as e:
        logger.error(f"Error parsing document {filename}: {e}")
        raise HTTPException(status_code=400, detail="Failed to parse document content.")

    if not extracted_text.strip():
        raise HTTPException(status_code=400, detail="No readable text found in the document.")

    # Save metadata to postgres
    doc = ProjectDocument(
        project_id=pid,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=size_bytes
    )
    db.add(doc)
    await db.flush()  # to get doc.id

    # Chunk text
    chunks = chunk_text(extracted_text)
    
    # Store chunks in Qdrant vector store
    synced_chunks = 0
    for i, chunk in enumerate(chunks):
        chunk_id = uuid.uuid5(doc.id, f"chunk-{i}")
        ok = await sync_node_to_vector_store(
            collection_name="events",  # using same collection for hybrid search
            node_id=chunk_id,
            project_id=pid,
            node_type="document",
            content=chunk,
            metadata={
                "title": filename,
                "event_type": "document_upload",
                "source_url": None,
                "chunk_index": i,
                "document_id": str(doc.id),
                "content_hash": content_hash(chunk),
            }
        )
        if ok:
            synced_chunks += 1

    await db.commit()

    return {
        "status": "success",
        "message": f"Successfully uploaded and processed {filename}",
        "document_id": str(doc.id),
        "chunks_indexed": synced_chunks
    }

@router.get("/{project_id}")
async def list_documents(
    project_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    List all uploaded documents for a project.
    """
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project_id format")

    result = await db.execute(select(ProjectDocument).where(ProjectDocument.project_id == pid))
    docs = result.scalars().all()
    
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "content_type": d.content_type,
            "size_bytes": d.size_bytes,
            "created_at": d.created_at.isoformat()
        } for d in docs
    ]
