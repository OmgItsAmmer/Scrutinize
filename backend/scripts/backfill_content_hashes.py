import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import hashlib
import requests
from sqlmodel import Session, select
from app.core.database import get_engine
from app.models.file import File

def backfill():
    engine = get_engine()
    with Session(engine) as session:
        statement = select(File).where(File.content_sha256 == None)
        files = list(session.exec(statement).all())
        print(f"Found {len(files)} files to backfill.")
        
        for f in files:
            print(f"Backfilling {f.filename} (ID: {f.id}) from {f.storage_path}...")
            try:
                # If it's a local mock storage path, we can try to open it locally.
                # If it starts with http, download it.
                if f.storage_path.startswith("http://") or f.storage_path.startswith("https://"):
                    res = requests.get(f.storage_path, timeout=30)
                    res.raise_for_status()
                    content = res.content
                else:
                    # Treat as local path
                    import os
                    if os.path.exists(f.storage_path):
                        with open(f.storage_path, "rb") as fp:
                            content = fp.read()
                    else:
                        print(f"Skipping {f.filename}: storage path not found locally.")
                        continue
                
                sha256 = hashlib.sha256(content).hexdigest()
                
                # Check if this hash already exists in this project
                existing = session.exec(
                    select(File).where(
                        File.project_id == f.project_id,
                        File.content_sha256 == sha256,
                        File.id != f.id
                    )
                ).first()
                
                if existing:
                    print(f"File {f.filename} (ID: {f.id}) is a duplicate of {existing.filename} (ID: {existing.id}). Deleting duplicate...")
                    from app.services.job_orchestrator import JobOrchestrator
                    orchestrator = JobOrchestrator(session)
                    orchestrator.delete_file(f.id)
                else:
                    f.content_sha256 = sha256
                    session.add(f)
                    session.commit()
                    print(f"Updated {f.filename} with hash {sha256}")
            except Exception as e:
                print(f"Failed to backfill {f.filename}: {e}")
                session.rollback()

if __name__ == "__main__":
    backfill()
