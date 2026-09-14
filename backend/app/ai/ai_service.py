import os
import shutil
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from fastapi import UploadFile
from google import genai
from pypdf import PdfReader
import chromadb


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# GEMINI CLIENT
# ============================================================

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


# ============================================================
# CHROMADB
# ============================================================

CHROMA_DB_PATH = Path(__file__).parent / "chroma_db"

chroma_client = chromadb.PersistentClient(
    path=str(CHROMA_DB_PATH)
)

collection = chroma_client.get_or_create_collection(
    name="documents"
)


# ============================================================
# SQLITE CHAT DATABASE
# ============================================================

CHAT_DB_PATH = Path(__file__).parent / "chat_sessions.db"


def get_chat_db():
    """
    Creates and returns a SQLite database connection
    for persistent chat-session storage.

    The database stores:
    - Chat sessions
    - Individual messages belonging to each session
    """

    connection = sqlite3.connect(str(CHAT_DB_PATH))

    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.commit()

    # --------------------------------------------------------
    # Chat containers
    #
    # A session can contain multiple independent chats.
    # --------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS chats (
            chat_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.commit()

    # --------------------------------------------------------
    # Migration: add created_at column if missing
    # (for databases created before this column existed)
    # --------------------------------------------------------

    existing_columns = [
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(chat_sessions)"
        ).fetchall()
    ]

    if "created_at" not in existing_columns:
        connection.execute(
            """
            ALTER TABLE chat_sessions
            ADD COLUMN created_at TEXT
            """
        )
        connection.commit()

    if "chat_id" not in existing_columns:
        connection.execute(
            """
            ALTER TABLE chat_sessions
            ADD COLUMN chat_id TEXT
            """
        )
        connection.commit()

    # --------------------------------------------------------
    # Backward compatibility
    #
    # If chat_sessions already existed from the previous
    # implementation, register its existing session IDs
    # in the new sessions table.
    # --------------------------------------------------------

    existing_sessions = connection.execute(
        """
        SELECT DISTINCT session_id
        FROM chat_sessions
        """
    ).fetchall()

    for row in existing_sessions:
        connection.execute(
            """
            INSERT OR IGNORE INTO sessions (session_id)
            VALUES (?)
            """,
            (row["session_id"],)
        )

    connection.commit()

    # --------------------------------------------------------
    # Projects table
    # --------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.commit()

    # --------------------------------------------------------
    # Migration: add project_id column to sessions if missing
    # --------------------------------------------------------

    session_columns = [
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(sessions)"
        ).fetchall()
    ]

    if "project_id" not in session_columns:
        connection.execute(
            """
            ALTER TABLE sessions
            ADD COLUMN project_id TEXT
            """
        )
        connection.commit()

    return connection



def list_chats(session_id: str) -> dict:
    """
    Returns all individual chats belonging to a session.
    """

    session_id = session_id.strip()

    connection = get_chat_db()

    rows = connection.execute(
        """
        SELECT chat_id, session_id, title, created_at
        FROM chats
        WHERE session_id = ?
        ORDER BY created_at DESC, rowid DESC
        """,
        (session_id,)
    ).fetchall()

    connection.close()

    chats = [
        {
            "chat_id": row["chat_id"],
            "session_id": row["session_id"],
            "title": row["title"],
            "created_at": row["created_at"]
        }
        for row in rows
    ]

    return {
        "status": "success",
        "session_id": session_id,
        "chats": chats
    }

def create_chat(chat_id: str, session_id: str, title: str) -> dict:
    """
    Creates a new individual chat inside a persistent session.
    """

    chat_id = chat_id.strip()
    session_id = session_id.strip()
    title = title.strip()

    if not chat_id or not session_id or not title:
        return {
            "status": "error",
            "message": "Chat ID, session ID and title are required"
        }

    connection = get_chat_db()

    existing_session = connection.execute(
        """
        SELECT session_id
        FROM sessions
        WHERE session_id = ?
        """,
        (session_id,)
    ).fetchone()

    if existing_session is None:
        connection.execute(
            """
            INSERT INTO sessions (session_id)
            VALUES (?)
            """,
            (session_id,)
        )

    existing_chat = connection.execute(
        """
        SELECT chat_id
        FROM chats
        WHERE chat_id = ?
        """,
        (chat_id,)
    ).fetchone()

    if existing_chat is not None:
        connection.close()
        return {
            "chat_id": chat_id,
            "status": "error",
            "message": "Chat already exists"
        }

    connection.execute(
        """
        INSERT INTO chats (chat_id, session_id, title)
        VALUES (?, ?, ?)
        """,
        (chat_id, session_id, title)
    )

    connection.commit()
    connection.close()

    return {
        "chat_id": chat_id,
        "session_id": session_id,
        "title": title,
        "status": "success",
        "message": "Chat created"
    }

# ============================================================
# CHAT SESSION FUNCTIONS
# ============================================================

def update_chat_title(chat_id: str, title: str) -> dict:
    """
    Updates the title of an existing individual chat.
    """

    chat_id = chat_id.strip()
    title = title.strip()

    if not chat_id or not title:
        return {
            "status": "error",
            "message": "Chat ID and title are required"
        }

    connection = get_chat_db()

    existing = connection.execute(
        """
        SELECT chat_id
        FROM chats
        WHERE chat_id = ?
        """,
        (chat_id,)
    ).fetchone()

    if existing is None:
        connection.close()

        return {
            "status": "error",
            "message": "Chat not found"
        }

    connection.execute(
        """
        UPDATE chats
        SET title = ?
        WHERE chat_id = ?
        """,
        (title, chat_id)
    )

    connection.commit()
    connection.close()

    return {
        "status": "success",
        "chat_id": chat_id,
        "title": title,
        "message": "Chat title updated"
    }

def create_chat_session(session_id: str) -> dict:
    """
    Creates a new persistent chat session.

    A session exists independently from its messages, which
    means an empty session can still be recognized as valid.
    """

    connection = get_chat_db()

    existing = connection.execute(
        """
        SELECT session_id
        FROM sessions
        WHERE session_id = ?
        """,
        (session_id,)
    ).fetchone()

    if existing is not None:
        connection.close()

        return {
            "session_id": session_id,
            "status": "error",
            "message": "Session already exists"
        }

    connection.execute(
        """
        INSERT INTO sessions (session_id)
        VALUES (?)
        """,
        (session_id,)
    )

    connection.commit()
    connection.close()

    return {
        "session_id": session_id,
        "status": "success",
        "message": "Chat session created"
    }


def list_chat_sessions() -> dict:
    """
    Returns a list of all existing chat sessions, including
    each session's message count and project_id, ordered by
    most recent activity first.
    """

    connection = get_chat_db()

    rows = connection.execute(
        """
        SELECT
            s.session_id,
            s.project_id,
            COUNT(c.id) AS message_count,
            MAX(c.id) AS last_message_id
        FROM sessions s
        LEFT JOIN chats ch
            ON s.session_id = ch.session_id
        LEFT JOIN chat_sessions c
            ON ch.chat_id = c.chat_id
        WHERE s.session_id != '__standalone_chats__'
        GROUP BY s.session_id
        ORDER BY last_message_id DESC
        """
    ).fetchall()

    connection.close()

    sessions = [
        {
            "session_id": row["session_id"],
            "project_id": row["project_id"],
            "message_count": row["message_count"]
        }
        for row in rows
    ]

    return {
        "status": "success",
        "sessions": sessions
    }



def create_project(name: str) -> dict:
    """
    Creates a new project (a folder that groups chat sessions).
    """

    project_id = name.strip().lower().replace(" ", "-")

    if not project_id:
        return {
            "status": "error",
            "message": "Project name is required"
        }

    connection = get_chat_db()

    existing = connection.execute(
        """
        SELECT project_id
        FROM projects
        WHERE project_id = ?
        """,
        (project_id,)
    ).fetchone()

    if existing is not None:
        connection.close()
        return {
            "project_id": project_id,
            "status": "error",
            "message": "Project already exists"
        }

    connection.execute(
        """
        INSERT INTO projects (project_id, name)
        VALUES (?, ?)
        """,
        (project_id, name.strip())
    )

    connection.commit()
    connection.close()

    return {
        "project_id": project_id,
        "name": name.strip(),
        "status": "success",
        "message": "Project created"
    }


def list_projects() -> dict:
    """
    Returns all projects with their name and id.
    """

    connection = get_chat_db()

    rows = connection.execute(
        """
        SELECT project_id, name
        FROM projects
        ORDER BY created_at ASC
        """
    ).fetchall()

    connection.close()

    projects = [
        {
            "project_id": row["project_id"],
            "name": row["name"]
        }
        for row in rows
    ]

    return {
        "status": "success",
        "projects": projects
    }


def assign_session_to_project(session_id: str, project_id: str) -> dict:
    """
    Assigns an existing chat session to a project.
    Pass an empty project_id to remove it from any project.
    """

    connection = get_chat_db()

    existing = connection.execute(
        """
        SELECT session_id
        FROM sessions
        WHERE session_id = ?
        """,
        (session_id,)
    ).fetchone()

    if existing is None:
        connection.close()
        return {
            "status": "error",
            "message": "Session not found"
        }

    value = project_id if project_id else None

    connection.execute(
        """
        UPDATE sessions
        SET project_id = ?
        WHERE session_id = ?
        """,
        (value, session_id)
    )

    connection.commit()
    connection.close()

    return {
        "session_id": session_id,
        "project_id": value,
        "status": "success",
        "message": "Session assigned"
    }


def get_chat_history(chat_id: str) -> dict:
    """
    Returns the conversation history for a specific chat
    from persistent SQLite storage.
    """

    connection = get_chat_db()

    chat = connection.execute(
        """
        SELECT chat_id, session_id, title
        FROM chats
        WHERE chat_id = ?
        """,
        (chat_id,)
    ).fetchone()

    if chat is None:
        connection.close()

        return {
            "status": "error",
            "message": "Chat not found",
            "messages": []
        }

    rows = connection.execute(
        """
        SELECT role, content, created_at
        FROM chat_sessions
        WHERE chat_id = ?
        ORDER BY id ASC
        """,
        (chat_id,)
    ).fetchall()

    connection.close()

    history = [
        {
            "role": row["role"],
            "content": row["content"],
            "created_at": row["created_at"]
        }
        for row in rows
    ]

    return {
        "status": "success",
        "chat_id": chat["chat_id"],
        "session_id": chat["session_id"],
        "title": chat["title"],
        "messages": history
    }


def add_to_chat_history(
    chat_id: str,
    role: str,
    content: str
) -> None:
    """
    Adds a message to a specific chat and permanently stores it in SQLite.
    The parent session_id is preserved for backward compatibility.
    """

    connection = get_chat_db()

    chat = connection.execute(
        """
        SELECT chat_id, session_id
        FROM chats
        WHERE chat_id = ?
        """,
        (chat_id,)
    ).fetchone()

    if chat is None:
        connection.close()
        raise ValueError(f"Chat '{chat_id}' does not exist.")

    connection.execute(
        """
        INSERT INTO chat_sessions (
            chat_id,
            session_id,
            role,
            content,
            created_at
        )
        VALUES (?, ?, ?, ?, datetime('now'))
        """,
        (
            chat["chat_id"],
            chat["session_id"],
            role,
            content
        )
    )

    connection.commit()
    connection.close()



# ============================================================
# AI STATUS
# ============================================================

def get_ai_status() -> dict:
    """
    Confirms that the AI module is wired up correctly.
    """

    return {
        "module": "ai",
        "status": "ok",
        "message": "AI service module is active"
    }


# ============================================================
# FILE UPLOAD
# ============================================================

UPLOAD_DIR = Path(__file__).parent / "uploads"


def save_uploaded_file(file: UploadFile) -> dict:
    """
    Saves an uploaded file after validating its filename
    and file type.

    Automatically:
    1. Saves the file
    2. Extracts its text
    3. Splits it into chunks
    4. Generates embeddings
    5. Stores the chunks in ChromaDB
    """

    ALLOWED_EXTENSIONS = {
        ".txt",
        ".pdf"
    }

    if not file.filename:
        return {
            "status": "error",
            "message": "Filename is required"
        }

    original_filename = file.filename

    safe_filename = Path(original_filename).name

    suffix = Path(safe_filename).suffix.lower()

    # --------------------------------------------------------
    # Prevent unsafe/path-traversal filenames
    # --------------------------------------------------------

    if safe_filename != original_filename:
        return {
            "filename": original_filename,
            "status": "error",
            "message": "Invalid filename"
        }

    # --------------------------------------------------------
    # Validate file type
    # --------------------------------------------------------

    if suffix not in ALLOWED_EXTENSIONS:
        return {
            "filename": safe_filename,
            "status": "error",
            "message": (
                "Unsupported file type. "
                "Only .txt and .pdf files are allowed."
            )
        }

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    file_path = UPLOAD_DIR / safe_filename

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(
                file.file,
                buffer
            )

        stored = store_document_chunks(
            safe_filename
        )

        if stored["status"] != "success":

            # Remove uploaded file if processing failed
            if file_path.exists():
                file_path.unlink()

            return {
                "filename": safe_filename,
                "status": "error",
                "message": stored.get(
                    "message",
                    "File uploaded but could not be processed"
                )
            }

        return {
            "filename": safe_filename,
            "status": "success",
            "message": "File uploaded and processed successfully",
            "saved_to": str(file_path),
            "file_type": suffix,
            "file_size": file_path.stat().st_size,
            "chunks_stored": stored["chunks_stored"]
        }

    except Exception as e:

        if file_path.exists():
            file_path.unlink()

        return {
            "filename": safe_filename,
            "status": "error",
            "message": f"Upload failed: {str(e)}"
        }


# ============================================================
# DOCUMENT TEXT EXTRACTION
# ============================================================

def extract_text_from_file(filename: str) -> dict:
    """
    Extracts text content from a previously uploaded file.

    Supports:
    - .txt
    - .pdf
    """

    file_path = UPLOAD_DIR / filename

    if not file_path.exists():
        return {
            "filename": filename,
            "status": "error",
            "message": "File not found in uploads directory"
        }

    suffix = file_path.suffix.lower()

    # --------------------------------------------------------
    # TXT
    # --------------------------------------------------------

    if suffix == ".txt":

        text = file_path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    elif suffix == ".pdf":

        reader = PdfReader(
            str(file_path)
        )

        text = "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

    else:

        return {
            "filename": filename,
            "status": "error",
            "message": f"Unsupported file type: {suffix}"
        }

    return {
        "filename": filename,
        "status": "success",
        "character_count": len(text),
        "text_preview": text[:500],
        "full_text": text
    }


# ============================================================
# TEXT CHUNKING
# ============================================================

def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50
) -> list[str]:
    """
    Splits text into overlapping chunks.

    chunk_size:
        Maximum number of characters per chunk.

    overlap:
        Number of characters repeated between consecutive
        chunks.
    """

    if chunk_size <= overlap:
        raise ValueError(
            "chunk_size must be greater than overlap"
        )

    chunks = []

    start = 0

    text_length = len(text)

    while start < text_length:

        end = start + chunk_size

        chunk = text[start:end]

        chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


# ============================================================
# GEMINI EMBEDDINGS
# ============================================================

def get_embedding(text: str) -> list[float]:
    """
    Generates a vector embedding for a piece of text
    using Gemini.
    """

    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text
    )

    return result.embeddings[0].values


# ============================================================
# STORE DOCUMENT CHUNKS
# ============================================================

def store_document_chunks(filename: str) -> dict:
    """
    Extracts, chunks, embeds, and stores a document's content
    in ChromaDB.

    Existing chunks for the same filename are deleted first.
    """

    extracted = extract_text_from_file(
        filename
    )

    if extracted["status"] != "success":
        return extracted

    # --------------------------------------------------------
    # Remove previously stored chunks for this document
    # --------------------------------------------------------

    existing = collection.get(
        where={
            "filename": filename
        }
    )

    existing_ids = existing.get(
        "ids",
        []
    )

    if existing_ids:

        collection.delete(
            ids=existing_ids
        )

    # --------------------------------------------------------
    # Create chunks
    # --------------------------------------------------------

    chunks = chunk_text(
        extracted["full_text"]
    )

    ids = []
    embeddings = []
    documents = []
    metadatas = []

    # --------------------------------------------------------
    # Generate embeddings
    # --------------------------------------------------------

    for i, chunk in enumerate(chunks):

        chunk_id = (
            f"{filename}_chunk_{i}"
        )

        embedding = get_embedding(
            chunk
        )

        ids.append(
            chunk_id
        )

        embeddings.append(
            embedding
        )

        documents.append(
            chunk
        )

        metadatas.append(
            {
                "filename": filename,
                "chunk_index": i
            }
        )

    # --------------------------------------------------------
    # Store chunks in ChromaDB
    # --------------------------------------------------------

    if ids:

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

    return {
        "filename": filename,
        "status": "success",
        "chunks_stored": len(chunks),
        "old_chunks_deleted": len(existing_ids)
    }


# ============================================================
# DOCUMENT SEMANTIC SEARCH
# ============================================================

def search_documents(
    query: str,
    n_results: int = 3
) -> dict:
    """
    Searches ChromaDB for relevant document chunks.

    Results above the configured distance threshold
    are excluded.
    """

    query_embedding = get_embedding(
        query
    )

    results = collection.query(
        query_embeddings=[
            query_embedding
        ],
        n_results=n_results
    )

    documents = results.get(
        "documents",
        [[]]
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]]
    )[0]

    distances = results.get(
        "distances",
        [[]]
    )[0]

    print(f"DEBUG Chroma distances for query {query!r}: {distances}")

    MAX_DISTANCE = 0.90

    matches = []

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances
    ):

        if distance <= MAX_DISTANCE:

            matches.append(
                {
                    "document": document,
                    "metadata": metadata,
                    "distance": distance
                }
            )

    return {
        "query": query,
        "results": matches
    }


# ============================================================
# RAG ANSWER GENERATION
# ============================================================

def generate_chat_title(question: str) -> str:
    """
    Generates a short, descriptive title for a new chat
    based on the user's first question.
    """

    question = question.strip()

    if not question:
        return "New Chat"

    try:
        title_prompt = f"""
Create a short, descriptive title for a chat based on this
user question.

User question:
{question}

Rules:
- Return ONLY the title.
- Do not use quotation marks.
- Do not add punctuation at the end.
- Keep it between 2 and 7 words.
- Make it clear and specific.
- Do not start with words like "Chat about" or "Question about".
"""

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=title_prompt
        )

        title = (response.text or "").strip()

        title = title.replace('"', "").replace("'", "")

        if not title:
            return question[:45]

        return title[:80]

    except Exception as err:
        print(f"Failed to generate chat title: {err}")
        return question[:45]

def generate_answer(
    query: str,
    chat_id: str,
    n_results: int = 3
) -> dict:
    """
    Generates an answer using:

    1. Semantic document search
    2. Retrieved document context
    3. Persistent conversation history
    4. Gemini
    5. Source citations
    """

    # --------------------------------------------------------
    # Search uploaded documents
    # --------------------------------------------------------

    results = search_documents(
        query,
        n_results
    )

    # --------------------------------------------------------
    # Build document context
    # --------------------------------------------------------

    context_parts = []

    for result in results["results"]:

        context_parts.append(
            f"Source: "
            f"{result['metadata']['filename']}\n"
            f"Content:\n"
            f"{result['document']}"
        )

    context = "\n\n".join(
        context_parts
    )

    # --------------------------------------------------------
    # Retrieve persistent conversation history
    # --------------------------------------------------------
    history = get_chat_history(
        chat_id
    )



    is_new_chat = len(history.get("messages", [])) == 0

    recent_messages = history["messages"][-6:]

    conversation = ""

    for message in recent_messages:
        role_label = message["role"].upper()
        conversation += role_label + ": " + message["content"] + "\n"
    # --------------------------------------------------------
    # Build RAG prompt
    # --------------------------------------------------------

    prompt = f"""
You are an AI study assistant helping a student understand their
uploaded course materials.

Answer the current question using the document context below and
the recent conversation for follow-up context.

Previous conversation:
{conversation}

Document context:
{context}

Current user question:
{query}

Guidelines:
- Base your answer on the document context, but you may reasonably
  summarize, paraphrase, or connect related information within it
  to answer the question, even if the wording differs from the
  question.
- If the documents partially relate to the question, answer with
  what is available and note what is missing, rather than refusing
  entirely.
- Only say you could not find the answer if the documents are truly
  unrelated to the question.
- Do not invent facts that are not supported by the documents.
- Keep the answer clear and concise.
"""

    # --------------------------------------------------------
    # Generate answer using Gemini
    # --------------------------------------------------------

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )

    answer = response.text



    # --------------------------------------------------------
    # Generate a title for a new chat
    # --------------------------------------------------------

    if is_new_chat:
        generated_title = generate_chat_title(query)

        if generated_title:
            update_chat_title(
                chat_id,
                generated_title
            )

    # --------------------------------------------------------
    # Save conversation permanently
    # --------------------------------------------------------

    add_to_chat_history(
        chat_id,
        "user",
        query
    )

    add_to_chat_history(
        chat_id,
        "assistant",
        answer
    )

    # --------------------------------------------------------
    # Return answer + sources
    # --------------------------------------------------------

    return {
        "query": query,
        "chat_id": chat_id,
        "answer": answer,
        "sources": [
            {
                "filename": result["metadata"]["filename"],
                "chunk": result["metadata"]["chunk_index"]
            }
            for result in results["results"]
        ]
    }


# ============================================================
# LIST DOCUMENTS
# ============================================================

def list_documents() -> dict:
    """
    Returns a list of unique documents stored in ChromaDB
    along with basic file metadata.
    """

    results = collection.get()

    metadatas = results.get(
        "metadatas",
        []
    )

    documents = {}

    for metadata in metadatas:

        filename = metadata.get(
            "filename"
        )

        if not filename:
            continue

        if filename not in documents:

            file_path = (
                UPLOAD_DIR / filename
            )

            file_type = (
                file_path.suffix.lower()
                if file_path.exists()
                else None
            )

            file_size = (
                file_path.stat().st_size
                if file_path.exists()
                else None
            )

            documents[filename] = {
                "filename": filename,
                "file_type": file_type,
                "file_size": file_size,
                "chunks": 0
            }

        documents[filename]["chunks"] += 1

    return {
        "documents": list(
            documents.values()
        ),
        "document_count": len(documents)
    }


# ============================================================
# DELETE DOCUMENT
# ============================================================

def delete_document(
    filename: str
) -> dict:
    """
    Deletes all stored chunks and the uploaded file
    for a document.
    """

    results = collection.get(
        where={
            "filename": filename
        }
    )

    ids = results.get(
        "ids",
        []
    )

    if not ids:

        return {
            "filename": filename,
            "status": "error",
            "message": "Document not found in ChromaDB"
        }

    # --------------------------------------------------------
    # Delete document chunks
    # --------------------------------------------------------

    collection.delete(
        ids=ids
    )

    # --------------------------------------------------------
    # Delete uploaded file
    # --------------------------------------------------------

    file_path = (
        UPLOAD_DIR / filename
    )

    if file_path.exists():
        file_path.unlink()

    return {
        "filename": filename,
        "status": "success",
        "chunks_deleted": len(ids)
    }







# ============================================================
# CLEAR CHAT HISTORY
# ============================================================

def clear_chat_history(chat_id: str) -> dict:
    """
    Deletes all messages from a specific chat while keeping
    the chat itself and its parent session.
    """

    connection = get_chat_db()

    existing = connection.execute(
        """
        SELECT chat_id
        FROM chats
        WHERE chat_id = ?
        """,
        (chat_id,)
    ).fetchone()

    if existing is None:
        connection.close()

        return {
            "status": "error",
            "message": "Chat not found"
        }

    connection.execute(
        """
        DELETE FROM chat_sessions
        WHERE chat_id = ?
        """,
        (chat_id,)
    )

    connection.commit()
    connection.close()

    return {
        "chat_id": chat_id,
        "status": "success",
        "message": "Chat history cleared"
    }


# ============================================================
# DELETE CHAT SESSION
# ============================================================


def delete_parent_session(session_id: str) -> dict:
    """
    Deletes a parent session, all chats belonging to it,
    and all messages belonging to those chats.
    """

    connection = get_chat_db()

    session = connection.execute(
        """
        SELECT session_id
        FROM sessions
        WHERE session_id = ?
        """,
        (session_id,)
    ).fetchone()

    if session is None:
        connection.close()

        return {
            "status": "error",
            "message": "Session not found"
        }

    connection.execute(
        """
        DELETE FROM chat_sessions
        WHERE chat_id IN (
            SELECT chat_id
            FROM chats
            WHERE session_id = ?
        )
        """,
        (session_id,)
    )

    connection.execute(
        """
        DELETE FROM chats
        WHERE session_id = ?
        """,
        (session_id,)
    )

    connection.execute(
        """
        DELETE FROM sessions
        WHERE session_id = ?
        """,
        (session_id,)
    )

    connection.commit()
    connection.close()

    return {
        "session_id": session_id,
        "status": "success",
        "message": "Session and all chats deleted"
    }

def delete_chat_session(chat_id: str) -> dict:
    """
    Deletes an individual chat and all of its messages.
    The parent session remains intact.
    """

    connection = get_chat_db()

    chat = connection.execute(
        """
        SELECT chat_id, session_id
        FROM chats
        WHERE chat_id = ?
        """,
        (chat_id,)
    ).fetchone()

    if chat is None:
        connection.close()

        return {
            "status": "error",
            "message": "Chat not found"
        }

    connection.execute(
        """
        DELETE FROM chat_sessions
        WHERE chat_id = ?
        """,
        (chat_id,)
    )

    connection.execute(
        """
        DELETE FROM chats
        WHERE chat_id = ?
        """,
        (chat_id,)
    )

    connection.commit()
    connection.close()

    return {
        "chat_id": chat_id,
        "session_id": chat["session_id"],
        "status": "success",
        "message": "Chat deleted"
    }


