import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'

function SidebarScrollText({ text, className }) {
  const wrapperRef = useRef(null)
  const textRef = useRef(null)

  const handleMouseEnter = () => {
    const wrapper = wrapperRef.current
    const textElement = textRef.current

    if (!wrapper || !textElement) return

    const overflow = textElement.scrollWidth - wrapper.clientWidth

    if (overflow > 0) {
      textElement.style.setProperty('--scroll-distance', `${overflow}px`)
      textElement.classList.add('scrolling')
    }
  }

  const handleMouseLeave = () => {
    const textElement = textRef.current

    if (!textElement) return

    textElement.classList.remove('scrolling')
    textElement.style.removeProperty('--scroll-distance')
  }

  return (
    <span
      ref={wrapperRef}
      className={`sidebar-scroll-text ${className || ''}`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <span ref={textRef} className="sidebar-scroll-text-inner">
        {text}
      </span>
    </span>
  )
}
import './App.css'

const API_URL = import.meta.env.VITE_API_URL

function generateSessionId() {
  return 'chat-' + Date.now()
}

function App() {
  const [sessionId, setSessionId] = useState(null)
  const [sessions, setSessions] = useState([])
  const [selectedSession, setSelectedSession] = useState(null)
  const [expandedSessions, setExpandedSessions] = useState({})
  const [sessionChats, setSessionChats] = useState({})
  const [standaloneChats, setStandaloneChats] = useState([])
const [deleteModal, setDeleteModal] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [sidebarExpanded, setSidebarExpanded] = useState(true)
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const [newSessionName, setNewSessionName] = useState('')
  const [showNewSessionInput, setShowNewSessionInput] = useState(false)

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')

  const [loading, setLoading] = useState(false)
  const [historyLoaded, setHistoryLoaded] = useState(true)

  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState(null)
  const [pendingDocument, setPendingDocument] = useState(null)
  const fileInputRef = useRef(null)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  const loadSessions = useCallback(async () => {
    try {
      const url = `${API_URL}/ai/sessions`
      const res = await fetch(url, { cache: 'no-store' })
      const data = await res.json()
      setSessions(data.sessions || [])
    } catch (err) {
      console.error('Failed to load sessions:', err)
    }
  }, [])

  const loadHistory = useCallback(async (id) => {
    setHistoryLoaded(false)
    try {
      const url = `${API_URL}/ai/chat-history?chat_id=${encodeURIComponent(id)}`
      const res = await fetch(url, { cache: 'no-store' })
      const data = await res.json()

      if (data.status === 'success') {
        setMessages(data.messages || [])
        return true
      }

      if (data.message === 'Chat not found') {
        localStorage.removeItem('study_assistant_active_chat')
        localStorage.removeItem('study_assistant_active_session')
        setSessionId(null)
        setSelectedSession(null)
        setMessages([])
      }

      return false
    } catch (err) {
      console.error('Failed to load chat history:', err)
      return false
    } finally {
      setHistoryLoaded(true)
    }
  }, [])

  const loadStandaloneChats = useCallback(async () => {
    try {
      const url = `${API_URL}/ai/chats?session_id=${encodeURIComponent('__standalone_chats__')}`
      const res = await fetch(url, { cache: 'no-store' })
      const data = await res.json()

      if (data.status === 'success') {
        setStandaloneChats(data.chats || [])
      }
    } catch (err) {
      console.error('Failed to load standalone chats:', err)
    }
  }, [])
  useEffect(() => {
    loadSessions()
    loadStandaloneChats()
  }, [loadStandaloneChats])

  useEffect(() => {
    const savedChatId = localStorage.getItem('study_assistant_active_chat')
    const savedSessionId = localStorage.getItem('study_assistant_active_session')

    if (savedChatId) {
      setSessionId(savedChatId)
      loadHistory(savedChatId)

      if (savedSessionId) {
        setSelectedSession(savedSessionId)
        setExpandedSessions((prev) => ({
          ...prev,
          [savedSessionId]: true
        }))
        loadSessionChats(savedSessionId)
      }
    }
  }, [loadHistory])

  useEffect(() => {
    if (messages.length > 0 || loading) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, loading])
  useEffect(() => {
    if (!searchTerm.trim() || sessions.length === 0) return

    let cancelled = false

    const loadChatsForSearch = async () => {
      try {
        const results = await Promise.all(
          sessions.map(async (session) => {
            const url =
              `${API_URL}/ai/chats?session_id=${encodeURIComponent(session.session_id)}`

            const res = await fetch(url, { cache: 'no-store' })
            const data = await res.json()

            return {
              sessionId: session.session_id,
              chats: data.status === 'success' ? (data.chats || []) : []
            }
          })
        )

        if (cancelled) return

        setSessionChats((prev) => {
          const next = { ...prev }

          results.forEach((result) => {
            next[result.sessionId] = result.chats
          })

          return next
        })
      } catch (err) {
        console.error('Failed to load chats for search:', err)
      }
    }

    loadChatsForSearch()

    return () => {
      cancelled = true
    }
  }, [searchTerm, sessions])

  const startNewChat = (parentSessionId = null) => {
    localStorage.removeItem('study_assistant_active_chat')

    if (parentSessionId) {
      localStorage.setItem('study_assistant_active_session', parentSessionId)
    } else {
      localStorage.removeItem('study_assistant_active_session')
    }

    setSessionId(null)
    setMessages([])
    setHistoryLoaded(true)
    setUploadStatus(null)

    if (parentSessionId) {
      setSelectedSession(parentSessionId)
      setExpandedSessions((prev) => ({
        ...prev,
        [parentSessionId]: true
      }))
    } else {
      setSelectedSession(null)
    }

    setTimeout(() => inputRef.current?.focus(), 0)
  }

  const loadSessionChats = useCallback(async (id) => {
    if (!id) return

    try {
      const url = `${API_URL}/ai/chats?session_id=${encodeURIComponent(id)}`
      const res = await fetch(url, { cache: 'no-store' })
      const data = await res.json()

      if (data.status === 'success') {
        setSessionChats((prev) => ({
          ...prev,
          [id]: data.chats || []
        }))
      }
    } catch (err) {
      console.error('Failed to load session chats:', err)
    }
  }, [])

  const switchSession = (chatId, parentSessionId) => {
  if (chatId === sessionId) return

  setSessionId(chatId)
  setSelectedSession(parentSessionId)

  localStorage.setItem('study_assistant_active_chat', chatId)
  localStorage.setItem('study_assistant_active_session', parentSessionId)

  setExpandedSessions((prev) => ({
    ...prev,
    [parentSessionId]: true
  }))

  setUploadStatus(null)
  loadHistory(chatId)
}
const toggleSession = (name) => {
    setExpandedSessions((prev) => ({
      ...prev,
      [name]: !prev[name]
    }))
  }
    const toggleSidebar = () => {
      if (window.innerWidth <= 768) {
        setMobileSidebarOpen(false)
        return
      }
      setSidebarExpanded((prev) => !prev)
    }

  const createSession = async () => {
  const name = newSessionName.trim()
  if (!name) return

  try {
    const url = `${API_URL}/ai/sessions?session_id=${encodeURIComponent(name)}`
    const res = await fetch(url, { method: 'POST', cache: 'no-store' })
    const data = await res.json()

    if (data.status === 'success') {
      setNewSessionName('')
      setShowNewSessionInput(false)

      await loadSessions()
      await loadSessionChats(name)

      setSelectedSession(name)
      setExpandedSessions((prev) => ({
        ...prev,
        [name]: true
      }))

      setSessionId(null)
      setMessages([])
      setHistoryLoaded(true)
      setUploadStatus(null)

      setTimeout(() => inputRef.current?.focus(), 0)
    } else {
      alert(data.message || 'Could not create session')
    }
  } catch (err) {
    alert('Error: could not reach backend.')
  }
}
const deleteSession = (id, e) => {
  e.stopPropagation()

  setDeleteModal({
    type: 'session',
    id: id,
    title: id
  })
}

const deleteChat = (chatId, parentSessionId, e) => {
  e.stopPropagation()

  const allChats = [
    ...Object.values(sessionChats).flat(),
    ...standaloneChats
  ]

  const chat = allChats.find((item) => item.chat_id === chatId)

  setDeleteModal({
    type: 'chat',
    id: chatId,
    parentSessionId: parentSessionId,
    title: chat?.title || 'this chat'
  })
}

const confirmDelete = async () => {
  if (!deleteModal) return

  const { type, id, parentSessionId } = deleteModal

  setDeleteModal(null)

  try {
    if (type === 'session') {
      const url = `${API_URL}/ai/sessions/${encodeURIComponent(id)}`
      const res = await fetch(url, {
        method: 'DELETE',
        cache: 'no-store'
      })
      const data = await res.json()

      if (data.status === 'success') {
        setSessionChats((prev) => {
          const next = { ...prev }
          delete next[id]
          return next
        })

        await loadSessions()

        if (id === selectedSession) {
          setSelectedSession(null)
          setSessionId(null)
          setMessages([])
          setHistoryLoaded(true)
          setUploadStatus(null)
        }
      } else {
        alert(data.message || 'Could not delete session')
      }
    } else {
      const url = `${API_URL}/ai/chats/${encodeURIComponent(id)}`
      const res = await fetch(url, {
        method: 'DELETE',
        cache: 'no-store'
      })

      const data = await res.json()

      if (data.status === 'success') {
        setSessionChats((prev) => ({
          ...prev,
          [parentSessionId]: (prev[parentSessionId] || []).filter(
            (chat) => chat.chat_id !== id
          )
        }))

        if (parentSessionId === '__standalone_chats__') {
          setStandaloneChats((prev) =>
            prev.filter((chat) => chat.chat_id !== id)
          )
        }

        if (id === sessionId) {
          setSessionId(null)
          setMessages([])
          setHistoryLoaded(true)
          setUploadStatus(null)
          setTimeout(() => inputRef.current?.focus(), 0)
        }
      } else {
        alert(data.message || 'Could not delete chat')
      }
    }
  } catch (err) {
    alert('Error: could not reach backend.')
  }
}
const sendMessage = async () => {
    if (!input.trim()) return

    const question = input
    setInput('')

    let activeChatId = sessionId

    if (!activeChatId) {
      const parentSessionId = selectedSession || '__standalone_chats__'

      activeChatId = generateSessionId()

      const chatTitle = question.length > 45
        ? `${question.slice(0, 45)}...`
        : question

      try {
        const createChatUrl =
          `${API_URL}/ai/chats?chat_id=${encodeURIComponent(activeChatId)}` +
          `&session_id=${encodeURIComponent(parentSessionId)}` +
          `&title=${encodeURIComponent(chatTitle)}`

        const createChatRes = await fetch(createChatUrl, {
          method: 'POST',
          cache: 'no-store'
        })

        const createChatData = await createChatRes.json()

        if (createChatData.status !== 'success') {
          alert(createChatData.message || 'Could not create chat.')
          setInput(question)
          return
        }

        setSessionId(activeChatId)
        localStorage.setItem('study_assistant_active_chat', activeChatId)
        localStorage.setItem('study_assistant_active_session', parentSessionId)
        await loadSessionChats(parentSessionId)
      } catch (err) {
        alert('Error: could not create chat.')
        setInput(question)
        return
      }
    }

    const attachedDocument = pendingDocument

    setMessages((prev) => [...prev, { role: 'user', content: question, created_at: null, attachment: attachedDocument }])
    setPendingDocument(null)
    setLoading(true)

    try {
      const url = `${API_URL}/ai/ask?query=${encodeURIComponent(question)}&n_results=3&chat_id=${activeChatId}`
      const res = await fetch(url, { cache: 'no-store' })
      const data = await res.json()

      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.answer || 'No answer returned.', sources: data.sources || [], created_at: null }
      ])
      await loadSessions()

      if (selectedSession) {
        await loadSessionChats(selectedSession)
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Error: could not reach backend.', created_at: null }
      ])
    } finally {
      setLoading(false)
    }
  }
    const handleKeyDown = (e) => {
    if (e.key === 'Enter') sendMessage()
  }

  const handleFileSelect = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    setUploadStatus(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const url = `${API_URL}/ai/upload`
      const res = await fetch(url, {
        method: 'POST',
        body: formData,
        cache: 'no-store'
      })
      const data = await res.json()

      if (data.status === 'success') {
        setPendingDocument({
          filename: data.filename,
          fileType: data.filename.toLowerCase().endsWith('.pdf') ? 'PDF' : 'TXT'
        })
        setUploadStatus(null)
      } else {
        setUploadStatus({
          type: 'error',
          text: data.message || 'Upload failed.'
        })
      }
    } catch (err) {
      setUploadStatus({
        type: 'error',
        text: 'Error: could not reach backend.'
      })
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const filteredStandaloneChats = useMemo(() => {
    const term = searchTerm.trim().toLowerCase()

    if (!term) return standaloneChats

    return standaloneChats.filter((chat) =>
      (chat.title || '').toLowerCase().includes(term)
    )
  }, [standaloneChats, searchTerm])

  const filteredSessions = useMemo(() => {
    const term = searchTerm.trim().toLowerCase()

    if (!term) return sessions

    return sessions.filter((s) => {
      const sessionId = (s.session_id || '').toLowerCase()
      const chats = sessionChats[s.session_id] || []

      const sessionMatches = sessionId.includes(term)

      const chatMatches = chats.some((chat) =>
        (chat.title || '').toLowerCase().includes(term)
      )

      return sessionMatches || chatMatches
    })
  }, [sessions, sessionChats, searchTerm])

  const sessionGroups = useMemo(() => {
    const term = searchTerm.trim().toLowerCase()

    return filteredSessions.map((s) => {
      const allChats = sessionChats[s.session_id] || []

      if (!term) {
        return {
          ...s,
          title: s.session_id,
          chats: allChats
        }
      }

      const sessionMatches = s.session_id.toLowerCase().includes(term)

      return {
        ...s,
        title: s.session_id,
        chats: sessionMatches
          ? allChats
          : allChats.filter((chat) =>
              (chat.title || '').toLowerCase().includes(term)
            )
      }
    })
  }, [filteredSessions, sessionChats, searchTerm])
  const isLanding = messages.length === 0 && !loading

  const attachButton = (
    <button
      type="button"
      className="attach-btn"
      onClick={handleFileSelect}
      disabled={uploading}
      title="Upload document (.txt / .pdf)"
    >
      {uploading ? '...' : '+'}
    </button>
  )

  const inputBar = (
    <div className={`chat-input ${pendingDocument ? 'has-document' : ''}`}>
      <input
        type="file"
        ref={fileInputRef}
        accept=".txt,.pdf"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />

      {pendingDocument && (
        <div className="uploaded-document">
          <div className="document-icon">
            {pendingDocument.fileType}
          </div>
          <div className="document-info">
            <div className="document-name">{pendingDocument.filename}</div>
            <div className="document-type">{pendingDocument.fileType}</div>
          </div>
          <button
            type="button"
            className="remove-document-btn"
            onClick={() => setPendingDocument(null)}
            aria-label="Remove uploaded document"
            title="Remove document"
          >
            &times;
          </button>
        </div>
      )}

      <div className="chat-input-row">
        {attachButton}

        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything about your documents..."
          autoFocus
        />

        <button
          onClick={sendMessage}
          disabled={loading || !input.trim()}
          aria-label="Send message"
          title="Send message"
        >
          &uarr;
        </button>
      </div>
    </div>
  )

  return (
    <div className="app-layout">
      <aside className={`sidebar ${sidebarExpanded ? 'sidebar-expanded' : 'sidebar-collapsed'} ${mobileSidebarOpen ? 'mobile-sidebar-open' : ''} `}>
          <div className="sidebar-header">
            <div className="sidebar-title">Study Assistant</div>

            <button
              type="button"
              className="sidebar-toggle-btn"
              onClick={toggleSidebar}
              title={sidebarExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
            >
              {sidebarExpanded ? String.fromCharCode(171) : String.fromCharCode(187)}
            </button>
          </div>

          <div className="sidebar-top-row">
          <button type="button" className="new-chat-btn" onClick={() => startNewChat()}>
            + New chat
          </button>
          <button
            type="button"
            className="name-session-toggle"
            onClick={() => setShowNewSessionInput((v) => !v)}
            title="Create a named session"
          >
            +
          </button>
        </div>

        <div className="sidebar-search">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search chats"
          />
        </div>
        {showNewSessionInput && (
          <div className="new-session">
            <input
              type="text"
              value={newSessionName}
              onChange={(e) => setNewSessionName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && createSession()}
              placeholder="Session name"
              autoFocus
            />
            <button onClick={createSession}>Create</button>
          </div>
        )}

        <div className="sidebar-label">Chats</div>

        {standaloneChats.length > 0 && (
          <div className="standalone-chat-list">
            {filteredStandaloneChats.map((chat) => (
              <div
                key={chat.chat_id}
                className={`standalone-chat ${
                  chat.chat_id === sessionId ? 'active-chat' : ''
                }`}
                onClick={() => {
                  setSessionId(chat.chat_id)
                  setSelectedSession(null)
                  localStorage.setItem(
                    'study_assistant_active_chat',
                    chat.chat_id
                  )
                  localStorage.removeItem(
                    'study_assistant_active_session'
                  )
                  setUploadStatus(null)
                  loadHistory(chat.chat_id)
                }}
              >
                <SidebarScrollText
                  className="chat-title"
                  text={chat.title}
                />
                <button
                  type="button"
                  className="delete-chat-btn"
                  onClick={(e) => {
                    deleteChat(
                      chat.chat_id,
                      '__standalone_chats__',
                      e
                    )
                  }}
                  title="Delete chat"
                >
                  &times;
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="sidebar-label projects-label">Projects</div>

        <ul className="session-list">
          {sessionGroups.map((s) => {
            const isSearchActive = searchTerm.trim().length > 0
              const sessionNameMatches = isSearchActive && s.session_id.toLowerCase().includes(searchTerm.trim().toLowerCase())
              const hasChatSearchMatch = isSearchActive && s.chats.some((chat) =>
                (chat.title || '').toLowerCase().includes(searchTerm.trim().toLowerCase())
              )
              const isExpanded = expandedSessions[s.session_id] || (hasChatSearchMatch && !sessionNameMatches)
            const isSelected = selectedSession === s.session_id

            return (
              <li
                key={s.session_id}
                className={`session-container ${isSelected ? 'selected-session' : ''}`}
              >
                <div
                  className="session-header"
                  onClick={async () => {
                    setSelectedSession(s.session_id)

                    const isCurrentlyExpanded = expandedSessions[s.session_id] || false

                    if (!isCurrentlyExpanded) {
                      await loadSessionChats(s.session_id)
                    }

                    toggleSession(s.session_id)
                  }}
                >
                  <span className="session-arrow">
                    {isExpanded ? String.fromCharCode(9660) : String.fromCharCode(9654)}
                  </span>

                  <SidebarScrollText className="session-name" text={s.title} />

                  <button
                    type="button"
                    className="session-add-chat-btn"
                    onClick={(e) => {
                      e.stopPropagation()
                      startNewChat(s.session_id)
                    }}
                    title="New chat in this session"
                  >
                    +
                  </button>

                  <button
                    type="button"
                    className="delete-session-btn"
                    onClick={(e) => deleteSession(s.session_id, e)}
                    title="Delete session"
                  >
                    &times;
                  </button>
                </div>

                {isExpanded && (
                  <div className="session-chats">
                    {s.chats.map((chat) => (
                      <div
                        key={chat.chat_id}
                        className={`session-chat ${
                          chat.chat_id === sessionId ? 'active-chat' : ''
                        }`}
                        onClick={() => switchSession(chat.chat_id, s.session_id)}
                      >
                        <SidebarScrollText className="chat-title" text={chat.title} />
                        <span className="session-count">{chat.message_count}</span>
                        <button
                          type="button"
                          className="delete-chat-btn"
                          onClick={(e) => deleteChat(chat.chat_id, s.session_id, e)}
                          title="Delete chat"
                        >
                          &times;
                        </button>
                      </div>
                    ))}


                  </div>
                )}
              </li>
            )
          })}

          {sessionGroups.length === 0 && (
            <li className="no-results">No sessions found</li>
          )}
        </ul>
      </aside>

      <div className="main-panel">
        <button type="button" className="mobile-menu-btn" onClick={() => setMobileSidebarOpen(prev => !prev)} aria-label="Open sidebar" title="Open sidebar">{mobileSidebarOpen ? String.fromCharCode(171) : String.fromCharCode(187)}</button>
        {isLanding ? (
          <div className="landing">
            <h1 className="landing-title">What would you like to study?</h1>
            {uploadStatus && (
              <div className={`upload-status ${uploadStatus.type}`}>
                {uploadStatus.text}
              </div>
            )}
            <div className="landing-input-wrap">
              {inputBar}
            </div>
          </div>
        ) : (
          <div className="chat-container">
            <p className="current-session">
              {(() => {
                const activeChat = Object.values(sessionChats)
                  .flat()
                  .find((chat) => chat.chat_id === sessionId)

                return activeChat?.title || 'New Chat'
              })()}
            </p>

            {uploadStatus && (
              <div className={`upload-status ${uploadStatus.type}`}>
                {uploadStatus.text}
              </div>
            )}

            <div className="chat-window">
              {historyLoaded && messages.length === 0 && (
                <p className="empty-state">Ask a question about your uploaded documents.</p>
              )}
              {messages.map((msg, i) => (
                <div key={i} className={`message ${msg.role}`}>
                  <div>
                    {msg.role === 'assistant' && <strong>Assistant:</strong>}
                    {msg.role === 'assistant' ? (
                      <div className="markdown-content">
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </div>
                    ) : (
                      <>
                        <div className="user-message-wrapper">
  {msg.attachment && (
    <div className="uploaded-document message-attachment">
      <div className="document-icon">
        {msg.attachment.fileType}
      </div>
      <div className="document-info">
        <div className="document-name">{msg.attachment.filename}</div>
        <div className="document-type">{msg.attachment.fileType}</div>
      </div>
    </div>
  )}
                          <div className="user-message-bubble">
                            <strong>You:</strong>
                            <span className="user-message-content">{msg.content}</span>
                          </div>


                        </div>
                      </>
                    )}
                  </div>

                  {msg.role === 'assistant' && msg.sources?.length > 0 && (
                    <div className="message-sources">
                      <div className="sources-label">Sources</div>
                      {msg.sources.map((source, sourceIndex) => (
                        <div key={sourceIndex} className="source-item">
                          <span className="source-file">{source.filename}</span>
                          <span className="source-chunk">Chunk {source.chunk}</span>
                        </div>
                      ))}
                    </div>
                  )}


                </div>
              ))}
              {loading && (
                <div className="message assistant thinking">
                  Assistant is thinking
                  <span className="dot-flashing"></span>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {inputBar}
          </div>
        )}
      </div>

      {deleteModal && (
        <div
          className="delete-modal-overlay"
          onClick={() => setDeleteModal(null)}
        >
          <div
            className="delete-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <h2>Delete {deleteModal.type === 'session' ? 'project' : 'chat'}?</h2>

            <p>
              This will delete <strong>{deleteModal.title}</strong>.
            </p>

            <div className="delete-modal-actions">
              <button
                type="button"
                className="delete-modal-cancel"
                onClick={() => setDeleteModal(null)}
              >
                Cancel
              </button>

              <button
                type="button"
                className="delete-modal-confirm"
                onClick={confirmDelete}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App







