from fastapi import APIRouter, UploadFile, File

from app.ai.ai_service import (
    get_ai_status,
    save_uploaded_file,
    extract_text_from_file,
    chunk_text,
    get_embedding,
    store_document_chunks,
    search_documents,
    generate_answer,
    get_chat_history,
    clear_chat_history,
    delete_chat_session,
    delete_parent_session,
    create_chat_session,
    list_chat_sessions,
    create_chat,
      update_chat_title,
    list_chats,
    create_project,
    list_projects,
    assign_session_to_project,
    list_documents,
    delete_document,
)

router = APIRouter(
    prefix="/ai",
    tags=["AI"]
)


@router.get("/status")
def ai_status():
    return get_ai_status()


@router.post("/upload")
def upload_document(file: UploadFile = File(...)):
    return save_uploaded_file(file)


@router.get("/extract")
def extract_document(filename: str):
    return extract_text_from_file(filename)


@router.get("/chunk")
def chunk_document(filename: str):
    extracted = extract_text_from_file(filename)

    if extracted["status"] != "success":
        return extracted

    chunks = chunk_text(extracted["full_text"])

    return {
        "filename": filename,
        "status": "success",
        "chunk_count": len(chunks),
        "chunks": chunks
    }


@router.get("/embed-test")
def embed_test(text: str):
    embedding = get_embedding(text)

    return {
        "text": text,
        "embedding_length": len(embedding),
        "embedding_preview": embedding[:5]
    }


@router.post("/store")
def store_document(filename: str):
    return store_document_chunks(filename)


@router.get("/search")
def search_document(
    query: str,
    n_results: int = 3
):
    return search_documents(
        query,
        n_results
    )


@router.get("/ask")
def ask_question(
    query: str,
    n_results: int = 3,
    chat_id: str = "default"
):
    return generate_answer(
        query=query,
        chat_id=chat_id,
        n_results=n_results
    )


@router.post("/chats")
def create_chat_endpoint(
    chat_id: str,
    session_id: str,
    title: str
):
    return create_chat(
        chat_id=chat_id,
        session_id=session_id,
        title=title
    )


@router.get("/chats")
def list_chats_endpoint(session_id: str):
    return list_chats(session_id)

@router.get("/chat-history")
def chat_history(
    chat_id: str
):
    return get_chat_history(chat_id)


@router.delete("/chat-history/{chat_id}")
def clear_chat_history_route(chat_id: str):
    return clear_chat_history(chat_id)


@router.delete("/chats/{chat_id}")
def delete_chat_route(chat_id: str):
    return delete_chat_session(chat_id)

@router.delete("/sessions/{session_id}")
def delete_session_route(session_id: str):
    return delete_parent_session(session_id)


@router.post("/sessions")
def create_session(session_id: str):
    return create_chat_session(session_id)


@router.get("/sessions")
def get_sessions():
    return list_chat_sessions()


@router.get("/documents")
def get_documents():
    return list_documents()


@router.delete("/documents/{filename}")
def delete_document_route(filename: str):
    return delete_document(filename)



@router.post("/projects")
def create_project_route(name: str):
    return create_project(name)


@router.get("/projects")
def get_projects():
    return list_projects()


@router.put("/sessions/{session_id}/project")
def assign_session_to_project_route(session_id: str, project_id: str = ""):
    return assign_session_to_project(session_id, project_id)
