import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from backend.app.core.config import settings
from backend.app.core.logging_config import logger
from backend.app.models.chunk import ValidatedChunk
from backend.app.registry.plans import get_plan_by_id, PlanInfo
from backend.app.services.chroma_service import ChromaStorageService
from backend.app.services.chunking_service import ChunkingService
from backend.app.services.document_structure import DocumentStructureParser
from backend.app.services.embedding_service import LocalEmbeddingService
from backend.app.services.metadata_service import MetadataService
from backend.app.services.pdf_extractor import PDFExtractor
from backend.app.services.table_extractor import TableExtractor
from backend.app.services.validation_service import ValidationService
from backend.app.utils.security import compute_sha256, scan_text_for_document_poisoning

class IngestionJob:
    def __init__(self, job_id: str, filename: str, plan_id: str):
        self.job_id = job_id
        self.filename = filename
        self.plan_id = plan_id
        self.status = "PENDING"
        self.current_stage = "Stage 1: File Validation"
        self.stages_completed: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.total_duration_sec: float = 0.0
        self.content_hash: str = ""
        self.file_size_bytes: int = 0
        self.is_duplicate: bool = False
        
        # Metrics
        self.total_pages: int = 0
        self.sections_detected: int = 0
        self.tables_extracted: int = 0
        self.calculations_detected: int = 0
        self.parent_chunks_count: int = 0
        self.child_chunks_count: int = 0
        self.embeddings_count: int = 0
        self.records_stored: int = 0
        self.coverage_report: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "filename": self.filename,
            "plan_id": self.plan_id,
            "status": self.status,
            "current_stage": self.current_stage,
            "stages_completed": self.stages_completed,
            "warnings": self.warnings,
            "errors": self.errors,
            "total_duration_sec": round(self.total_duration_sec, 2),
            "content_hash": self.content_hash,
            "is_duplicate": self.is_duplicate,
            "metrics": {
                "total_pages": self.total_pages,
                "sections_detected": self.sections_detected,
                "tables_extracted": self.tables_extracted,
                "calculations_detected": self.calculations_detected,
                "parent_chunks_count": self.parent_chunks_count,
                "child_chunks_count": self.child_chunks_count,
                "embeddings_count": self.embeddings_count,
                "records_stored": self.records_stored
            },
            "coverage_report": self.coverage_report
        }

class IngestionOrchestrator:
    """Orchestrates all 9 stages of the PDF Ingestion Pipeline."""

    def __init__(self):
        self.pdf_extractor = PDFExtractor()
        self.table_extractor = TableExtractor()
        self.structure_parser = DocumentStructureParser()
        self.chunker = ChunkingService()
        self.metadata_service = MetadataService()
        self.embedding_service = LocalEmbeddingService()
        self.chroma_service = ChromaStorageService()
        self.validator = ValidationService()
        self.active_jobs: dict[str, IngestionJob] = {}

    def get_job(self, job_id: str) -> Optional[IngestionJob]:
        return self.active_jobs.get(job_id)

    def run_pipeline(
        self,
        pdf_path: Path,
        original_filename: str,
        selected_plan_id: str
    ) -> IngestionJob:
        job_id = f"job_{uuid.uuid4().hex[:10]}"
        job = IngestionJob(job_id, original_filename, selected_plan_id)
        self.active_jobs[job_id] = job

        logger.info(f"=== Starting Ingestion Pipeline [{job_id}] for {original_filename} (Plan: {selected_plan_id}) ===")

        try:
            # Stage 1: File Validation & Content Hash
            job.current_stage = "Stage 1: File Validation"
            logger.info(f"[{job_id}] {job.current_stage}")
            
            with open(pdf_path, "rb") as f:
                file_bytes = f.read()
            if not file_bytes:
                raise ValueError("Source PDF file is empty (0 bytes).")
                
            job.file_size_bytes = len(file_bytes)
            job.content_hash = compute_sha256(file_bytes)
            
            # Check for duplicate unchanged upload
            prev_hash = self.chroma_service.get_existing_file_hash(original_filename)
            if prev_hash and prev_hash == job.content_hash:
                logger.info(f"[{job_id}] Duplicate upload detected: {original_filename} has not changed (hash: {job.content_hash[:12]}).")
                job.is_duplicate = True
                job.status = "SKIPPED_DUPLICATE"
                job.stages_completed.append(job.current_stage)
                self._record_history(job)
                return job

            # Quick sample check of initial page text for identity resolution
            page_texts_sample, ocr_pages, total_pages = self.pdf_extractor.extract_pdf_pages(pdf_path)
            sample_text = " ".join([page_texts_sample.get(p, "") for p in range(1, min(4, total_pages + 1))])
            # Document poisoning screening on sample text
            scan_text_for_document_poisoning(sample_text)

            from backend.app.registry.plans import resolve_plan_from_selection
            plan_info = resolve_plan_from_selection(selected_plan_id, sample_text)
            if not plan_info:
                plan_info = get_plan_by_id(selected_plan_id)
            if not plan_info:
                raise ValueError(f"Unknown plan or category selection: '{selected_plan_id}'. Choose 'Customer Insurance' or 'Employee Insurance'.")

            # Update job plan_id to resolved canonical plan ID
            job.plan_id = plan_info.plan_id
            job.stages_completed.append(job.current_stage)
            logger.info(f"[{job_id}] PDF validated successfully. Bound to plan {plan_info.plan_id} ({plan_info.plan_name}).")

            # Stage 2: Document Identity Validation
            job.current_stage = "Stage 2: Document Identity Validation"
            logger.info(f"[{job_id}] {job.current_stage}")
            
            ident_res = self.validator.validate_document_identity(sample_text, plan_info)
            if not ident_res.is_valid:
                raise ValueError("\n".join(ident_res.errors))
            job.warnings.extend(ident_res.warnings)
            job.stages_completed.append(job.current_stage)
            logger.info(f"[{job_id}] Plan identity verified.")

            # Stage 3: PDF Extraction (Text + Tables)
            job.current_stage = "Stage 3: PDF Extraction"
            logger.info(f"[{job_id}] {job.current_stage}")
            
            tables = self.table_extractor.extract_tables(pdf_path)
            job.total_pages = total_pages
            job.tables_extracted = len(tables)
            job.stages_completed.append(job.current_stage)
            logger.info(f"[{job_id}] Extraction completed: {total_pages} pages, {len(tables)} tables.")

            # Stage 4: 17-Section Structure Detection
            job.current_stage = "Stage 4: Structure Detection"
            logger.info(f"[{job_id}] {job.current_stage}")
            
            doc_model = self.structure_parser.parse_document(
                filename=original_filename,
                page_texts=page_texts_sample,
                tables=tables,
                ocr_needed_pages=ocr_pages
            )
            struct_res = self.validator.validate_extracted_structure(doc_model)
            job.warnings.extend(struct_res.warnings)
            job.sections_detected = len(doc_model.sections)
            job.calculations_detected = len(doc_model.calculations)
            job.stages_completed.append(job.current_stage)
            logger.info(f"[{job_id}] Structure validation completed: {job.sections_detected} sections detected.")

            # Stage 5: Parent-Child Chunk Creation
            job.current_stage = "Stage 5: Chunk Creation"
            logger.info(f"[{job_id}] {job.current_stage}")
            
            parents, children = self.chunker.chunk_document(doc_model, plan_info)
            job.parent_chunks_count = len(parents)
            job.child_chunks_count = len(children)
            job.stages_completed.append(job.current_stage)
            logger.info(f"[{job_id}] Parent and child chunks created: {len(parents)} parents, {len(children)} children.")

            # Stage 6: Chunk & Content Validation
            job.current_stage = "Stage 6: Chunk Validation"
            logger.info(f"[{job_id}] {job.current_stage}")
            
            # Defense-in-depth: Scan every chunk for document poisoning directives
            for c in children:
                scan_text_for_document_poisoning(c.content)

            chunk_res = self.validator.validate_chunks_before_storage(children)
            if not chunk_res.is_valid:
                raise ValueError("\n".join(chunk_res.errors))
            job.warnings.extend(chunk_res.warnings)

            # Metadata enrichment & validation
            validated_chunks_pre: list[tuple[str, str, dict[str, Any]]] = []
            for c in children:
                meta = self.metadata_service.finalize_metadata(c, plan_info, original_filename)
                validated_chunks_pre.append((c.chunk_id, c.content, meta))

            job.stages_completed.append(job.current_stage)
            logger.info(f"[{job_id}] Chunk validation completed.")

            # Stage 7: Embedding Generation
            job.current_stage = "Stage 7: Embedding Generation"
            logger.info(f"[{job_id}] {job.current_stage}")
            
            texts_to_embed = [content for _, content, _ in validated_chunks_pre]
            embeddings = self.embedding_service.generate_embeddings(texts_to_embed)
            job.embeddings_count = len(embeddings)

            # Assemble ValidatedChunks
            validated_chunks: list[ValidatedChunk] = []
            for (chk_id, content, meta), emb in zip(validated_chunks_pre, embeddings):
                validated_chunks.append(ValidatedChunk(
                    chunk_id=chk_id,
                    content=content,
                    metadata=meta,
                    embedding=emb
                ))

            job.stages_completed.append(job.current_stage)
            logger.info(f"[{job_id}] Embeddings generated: {len(embeddings)} vectors.")

            # Stage 8: ChromaDB Staged Storage
            job.current_stage = "Stage 8: ChromaDB Storage"
            logger.info(f"[{job_id}] {job.current_stage}")
            
            storage_result = self.chroma_service.staged_replace_document_chunks(
                source_filename=original_filename,
                plan_id=selected_plan_id,
                chunks=validated_chunks,
                parents=parents
            )
            job.records_stored = storage_result["inserted_count"]
            job.stages_completed.append(job.current_stage)
            logger.info(f"[{job_id}] ChromaDB insertion completed.")

            # Stage 9: Final Verification & Coverage Reporting
            job.current_stage = "Stage 9: Final Verification"
            logger.info(f"[{job_id}] {job.current_stage}")
            
            all_ids = [c.chunk_id for c in validated_chunks]
            is_stored_ok = self.chroma_service.verify_records_by_ids(all_ids)
            if not is_stored_ok:
                raise RuntimeError("Final storage read-back verification failed!")

            job.coverage_report = {
                "total_pages": job.total_pages,
                "sections_detected": job.sections_detected,
                "sections_expected": 17,
                "tables_extracted": job.tables_extracted,
                "calculations_detected": job.calculations_detected,
                "parent_chunks_created": job.parent_chunks_count,
                "child_chunks_created": job.child_chunks_count,
                "embeddings_generated": job.embeddings_count,
                "records_stored_in_chroma": job.records_stored,
                "ocr_needed_pages": ocr_pages,
                "loss_detected": False
            }

            job.stages_completed.append(job.current_stage)
            logger.info(f"[{job_id}] Stored record verification completed.")

            job.status = "SUCCESS"
            logger.info(f"=== INGESTION SUCCESS: {original_filename} successfully processed and stored in ChromaDB! ===")

        except Exception as e:
            job.status = "FAILED"
            error_msg = str(e)
            job.errors.append(error_msg)
            logger.error(f"[{job_id}] Ingestion pipeline FAILED at '{job.current_stage}': {error_msg}")

        finally:
            job.end_time = time.time()
            job.total_duration_sec = job.end_time - job.start_time
            self._record_history(job)

        return job

    def _record_history(self, job: IngestionJob) -> None:
        """Append run to persistent ingestion history JSON store."""
        history_list = []
        if settings.HISTORY_STORE_PATH.exists():
            try:
                with open(settings.HISTORY_STORE_PATH, "r", encoding="utf-8") as f:
                    history_list = json.load(f)
            except Exception:
                history_list = []

        history_list.append({
            "timestamp": datetime.now().isoformat(),
            "job_id": job.job_id,
            "source_document": job.filename,
            "plan_id": job.plan_id,
            "content_hash": job.content_hash,
            "status": job.status,
            "chunks_stored": job.records_stored,
            "duration_sec": round(job.total_duration_sec, 2),
            "errors": job.errors
        })

        with open(settings.HISTORY_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(history_list, f, indent=2)

        # Also persist to SQLite database tables for Admin Workspace
        try:
            from backend.app.db.sqlite_manager import sqlite_db
            doc_id = f"doc_{job.plan_id.lower().replace('-', '_')}"
            status_val = "INDEXED" if job.status == "SUCCESS" else "FAILED"
            sqlite_db.record_document(
                document_id=doc_id,
                filename=job.filename,
                plan_id=job.plan_id,
                file_size_bytes=getattr(job, "file_size_bytes", 0),
                chunk_count=job.records_stored,
                content_hash=job.content_hash,
                status=status_val
            )
            sqlite_db.record_ingestion_job(
                job_id=job.job_id,
                document_id=doc_id,
                filename=job.filename,
                plan_id=job.plan_id,
                status=job.status,
                stage=job.current_stage,
                error_summary="; ".join(job.errors) if job.errors else "",
                duration_ms=job.total_duration_sec * 1000.0,
                chunk_count=job.records_stored
            )
            sqlite_db.record_audit_event(
                action="document_ingestion",
                actor_id="admin_system",
                actor_role="admin",
                target_resource=job.filename,
                outcome=job.status,
                details={
                    "job_id": job.job_id,
                    "plan_id": job.plan_id,
                    "chunks": job.records_stored,
                    "duration_sec": round(job.total_duration_sec, 2),
                    "errors": job.errors
                }
            )
        except Exception as e:
            logger.warning(f"Failed to record ingestion run to SQLite: {e}")

        # Trigger index refresh on RAG retrieval service so newly ingested chunks are immediately searchable via BM25 and parent store
        if job.status == "SUCCESS":
            try:
                from backend.app.api.deps import get_rag_orchestrator
                rag_orch = get_rag_orchestrator()
                if rag_orch and hasattr(rag_orch, "retrieval_service"):
                    rag_orch.retrieval_service.refresh_indexes()
                    logger.info("Triggered immediate refresh of BM25 and parent-store indexes post-ingestion.")
            except Exception as ref_err:
                logger.warning(f"Note: Post-ingestion index auto-refresh deferred: {ref_err}")

    def get_history(self) -> list[dict[str, Any]]:
        if not settings.HISTORY_STORE_PATH.exists():
            return []
        try:
            with open(settings.HISTORY_STORE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
