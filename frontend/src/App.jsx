import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { Send, Loader2, Bot, User, ChevronDown, ChevronUp, Image as ImageIcon, X, Check, ShieldAlert } from 'lucide-react';

import './App.css';

function parseMessage(text) {
  if (!text) return { thinking: null, content: '', isThinkingFinished: true };

  let normalized = text
    .split('<thought>').join('<think>')
    .split('</thought>').join('</think>')
    .split('[Begin thinking]').join('<think>')
    .split('[End thinking]').join('</think>');

  const thinkParts = [];
  const contentParts = [];
  let isThinkingFinished = true;

  let remaining = normalized;
  while (remaining.length > 0) {
    const thinkStart = remaining.indexOf('<think>');
    if (thinkStart === -1) {
      contentParts.push(remaining);
      break;
    }

    if (thinkStart > 0) {
      contentParts.push(remaining.substring(0, thinkStart));
    }

    const afterStart = remaining.substring(thinkStart + 7);
    const thinkEnd = afterStart.indexOf('</think>');
    if (thinkEnd !== -1) {
      thinkParts.push(afterStart.substring(0, thinkEnd));
      remaining = afterStart.substring(thinkEnd + 8);
    } else {
      thinkParts.push(afterStart);
      isThinkingFinished = false;
      remaining = '';
    }
  }

  const thinking = thinkParts.length > 0 
    ? thinkParts.join('\n\n').split('<think>').join('').split('</think>').join('').trim() 
    : null;
  const content = contentParts.join('').trimStart();
  return { thinking, content, isThinkingFinished };
}

const renderWithLineBreaks = (children) => {
  if (typeof children === 'string') {
    if (!children.includes('<br>') && !children.includes('<br/>') && !children.includes('<br />')) {
      return children;
    }
    const parts = children.split(/<br\s*\/?>/gi);
    return parts.map((part, idx) => (
      <React.Fragment key={idx}>
        {idx > 0 && <br />}
        {part}
      </React.Fragment>
    ));
  }
  if (Array.isArray(children)) {
    return children.map((child, idx) => (
      <React.Fragment key={idx}>{renderWithLineBreaks(child)}</React.Fragment>
    ));
  }
  return children;
};

const markdownComponents = {
  td: ({ children, ...props }) => <td {...props}>{renderWithLineBreaks(children)}</td>,
  th: ({ children, ...props }) => <th {...props}>{renderWithLineBreaks(children)}</th>,
  p: ({ children, ...props }) => <p {...props}>{renderWithLineBreaks(children)}</p>,
  li: ({ children, ...props }) => <li {...props}>{renderWithLineBreaks(children)}</li>,
};

const SystemLogBlock = ({ logs, isFinished, hasStartedThinking }) => {
  const [isOpen, setIsOpen] = useState(true);
  const prevStarted = useRef(hasStartedThinking);

  useEffect(() => {
    if (isFinished) {
      setIsOpen(false);
    }
  }, [isFinished]);

  useEffect(() => {
    if (!prevStarted.current && hasStartedThinking) {
      setIsOpen(false);
    }
    prevStarted.current = hasStartedThinking;
  }, [hasStartedThinking]);

  if (!logs || logs.length === 0) return null;

  return (
    <div className="log-block">
      {isOpen && (
        <div className="log-content">
          {logs.map((log, i) => (
             <div key={i} className="log-item">{log}</div>
          ))}
        </div>
      )}
      <button className="collapse-btn" onClick={() => setIsOpen(!isOpen)}>
        {isOpen ? (
          <><ChevronUp size={14} /> Thu gọn tiến trình hệ thống</>
        ) : (
          <><ChevronDown size={14} /> Xem tiến trình hệ thống</>
        )}
      </button>
    </div>
  );
};

const ThinkingBlock = ({ thinking, isFinished }) => {
  const [isOpen, setIsOpen] = useState(isFinished ? false : true);
  const prevFinished = useRef(isFinished);

  useEffect(() => {
    if (prevFinished.current && !isFinished) {
      setIsOpen(true);
    }
    if (!prevFinished.current && isFinished) {
      setIsOpen(false);
    }
    prevFinished.current = isFinished;
  }, [isFinished]);

  if (!thinking) return null;

  return (
    <div className="thinking-block">
      {isOpen && (
        <div className="thinking-content markdown-body">
          <ReactMarkdown 
            remarkPlugins={[remarkMath, remarkGfm]} 
            rehypePlugins={[rehypeKatex]}
            components={markdownComponents}
          >
            {thinking}
          </ReactMarkdown>
        </div>
      )}
      <button className="collapse-btn" onClick={() => setIsOpen(!isOpen)}>
        {isOpen ? (
          <><ChevronUp size={14} /> Thu gọn suy nghĩ</>
        ) : (
          <><ChevronDown size={14} /> Xem quá trình suy nghĩ</>
        )}
      </button>
    </div>
  );
};

const getInitBubbleContent = (components, isReady, loadingText) => {
  const lines = components.map((comp) => `${comp}.  Loaded.`);
  if (!isReady && loadingText) {
    lines.push(loadingText);
  } else if (isReady) {
    lines.push('System ready.');
  }
  return lines.join('\n');
};

function App() {
  const [sessionId] = useState(() => {
    try {
      const saved = sessionStorage.getItem('ewallet_session_id');
      if (saved) return saved;
      const newId = 'session_' + Date.now() + '_' + Math.random().toString(36).substring(2, 8);
      sessionStorage.setItem('ewallet_session_id', newId);
      return newId;
    } catch {
      return 'session_' + Date.now();
    }
  });
  const [query, setQuery] = useState('');
  const [selectedImage, setSelectedImage] = useState(null);
  const [lightboxImage, setLightboxImage] = useState(null);
  const fileInputRef = useRef(null);

  const handleImageSelect = (file) => {
    if (!file || !file.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      setSelectedImage({
        file,
        dataUrl: e.target.result,
        name: file.name
      });
    };
    reader.readAsDataURL(file);
  };

  const handlePaste = (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith('image/')) {
        const file = items[i].getAsFile();
        if (file) {
          handleImageSelect(file);
          e.preventDefault();
          break;
        }
      }
    }
  };

  const removeImage = () => {
    setSelectedImage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [systemStatus, setSystemStatus] = useState('');
  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);
  const [autoScroll, setAutoScroll] = useState(true);
  // Trạng thái khởi tạo & nạp mô hình hệ thống
  const [isSystemReady, setIsSystemReady] = useState(false);
  const [loadedComponents, setLoadedComponents] = useState([]);
  const [initLoadingText, setInitLoadingText] = useState('Connecting server...');


  useEffect(() => {
    let isMounted = true;
    let abortController = new AbortController();

    const connectInitStream = async () => {
      try {
        const response = await fetch('/api/init-stream', {
          signal: abortController.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        let currentEvent = 'message';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop();

          for (const rawLine of lines) {
            const line = rawLine.replace(/\r$/, '');
            if (line.startsWith('event: ')) {
              currentEvent = line.substring(7).trim();
            } else if (line.startsWith('data: ')) {
              const dataStr = line.substring(6);
              try {
                const data = JSON.parse(dataStr);
                if (currentEvent === 'loading') {
                  if (isMounted) setInitLoadingText(data.text);
                } else if (currentEvent === 'loaded') {
                  if (isMounted && data.component) {
                    setLoadedComponents((prev) =>
                      prev.includes(data.component) ? prev : [...prev, data.component]
                    );
                  }
                } else if (currentEvent === 'complete') {
                  if (isMounted) {
                    setIsSystemReady(true);
                    setInitLoadingText('');
                  }
                } else if (currentEvent === 'error') {
                  if (isMounted) {
                    setInitLoadingText(`Error: ${data.text}`);
                  }
                }
              } catch (parseErr) {
                console.error("Lỗi parse SSE init data:", parseErr);
              }
            } else if (line.trim() === '') {
              currentEvent = 'message';
            }
          }
        }
      } catch (err) {
        if (!isMounted || abortController.signal.aborted) return;
        console.warn("Init stream connection error:", err);
        setInitLoadingText('Connecting server...');
        setTimeout(() => {
          if (isMounted && !abortController.signal.aborted) {
            connectInitStream();
          }
        }, 2000);
      }
    };

    connectInitStream();

    return () => {
      isMounted = false;
      abortController.abort();
    };
  }, []);

  const handleScroll = () => {
    if (!chatContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    setAutoScroll(isNearBottom);
  };

  useEffect(() => {
    if (autoScroll) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
    }
  }, [messages, systemStatus, loadedComponents, initLoadingText, autoScroll]);

  const sendQuery = async (textToSend, imageToSend = null) => {
    if ((!textToSend.trim() && !imageToSend) || isLoading || !isSystemReady) return;

    const userMessage = { 
      role: 'user', 
      content: textToSend.trim(), 
      image: imageToSend 
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setSystemStatus('Đang khởi tạo...');
    setAutoScroll(true);
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 100);

    let assistantMessage = { 
      role: 'assistant', 
      thinking: '',
      content: '',
      rawContent: '', 
      stats: null, 
      logs: [], 
      isFinished: false,
      isThinking: false,
      consentRequired: false,
      consentAnswered: null
    };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      const response = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query: textToSend.trim() || 'Hãy phân tích hình ảnh này và cung cấp thông tin liên quan.',
          image: imageToSend,
          session_id: sessionId
        }),
      });

      if (!response.ok) {
        let errDetail = `HTTP ${response.status}`;
        try {
          const errJson = await response.json();
          if (errJson.detail) errDetail = errJson.detail;
        } catch {
          // ignore non-JSON error body
        }
        throw new Error(errDetail);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      
      let buffer = '';
      let currentEvent = 'message';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep incomplete line

        for (const rawLine of lines) {
          const line = rawLine.replace(/\r$/, '');
          if (line.startsWith('event: ')) {
            currentEvent = line.substring(7).trim();
          } else if (line.startsWith('data: ')) {
            const dataStr = line.substring(6);
            if (dataStr === '[DONE]') continue;
            
            try {
              const data = JSON.parse(dataStr);
              
              if (currentEvent === 'status') {
                setSystemStatus(data.text);
                setMessages((prev) => {
                  const newMsgs = [...prev];
                  const lastIndex = newMsgs.length - 1;
                  newMsgs[lastIndex] = {
                    ...newMsgs[lastIndex],
                    logs: [...(newMsgs[lastIndex].logs || []), data.text]
                  };
                  return newMsgs;
                });
              } else if (currentEvent === 'thinking') {
                if (data.text) {
                  setSystemStatus('');
                }
                setMessages((prev) => {
                  const newMsgs = [...prev];
                  const lastIndex = newMsgs.length - 1;
                  newMsgs[lastIndex] = {
                    ...newMsgs[lastIndex],
                    thinking: (newMsgs[lastIndex].thinking || '') + data.text,
                    isThinking: true
                  };
                  return newMsgs;
                });
              } else if (currentEvent === 'token') {
                if (data.text) {
                  setSystemStatus('');
                }
                setMessages((prev) => {
                  const newMsgs = [...prev];
                  const lastIndex = newMsgs.length - 1;
                  newMsgs[lastIndex] = {
                    ...newMsgs[lastIndex],
                    content: (newMsgs[lastIndex].content || '') + data.text,
                    rawContent: (newMsgs[lastIndex].rawContent || '') + data.text,
                    isThinking: false
                  };
                  return newMsgs;
                });
              } else if (currentEvent === 'stats') {
                setMessages((prev) => {
                  const newMsgs = [...prev];
                  const lastIndex = newMsgs.length - 1;
                  newMsgs[lastIndex] = {
                    ...newMsgs[lastIndex],
                    stats: data.text
                  };
                  return newMsgs;
                });
              } else if (currentEvent === 'consent_required') {
                setMessages((prev) => {
                  const newMsgs = [...prev];
                  const lastIndex = newMsgs.length - 1;
                  newMsgs[lastIndex] = {
                    ...newMsgs[lastIndex],
                    consentRequired: true
                  };
                  return newMsgs;
                });
              }
            } catch (parseErr) {
              console.error("Error parsing SSE data", parseErr);
            }
          } else if (line.trim() === '') {
            currentEvent = 'message';
          }
        }
      }
    } catch (error) {
      console.error("Fetch error:", error);
      const errMsg = `Có lỗi xảy ra: ${error.message}`;
      setSystemStatus(errMsg);
      setMessages((prev) => {
        const newMsgs = [...prev];
        if (newMsgs.length > 0) {
          const lastIndex = newMsgs.length - 1;
          if (!newMsgs[lastIndex].content) {
            newMsgs[lastIndex] = {
              ...newMsgs[lastIndex],
              content: `⚠️ ${errMsg}`
            };
          }
        }
        return newMsgs;
      });
    } finally {
      setIsLoading(false);
      setMessages((prev) => {
        const newMsgs = [...prev];
        if (newMsgs.length > 0) {
          const lastIndex = newMsgs.length - 1;
          newMsgs[lastIndex] = { ...newMsgs[lastIndex], isFinished: true, isThinking: false };
        }
        return newMsgs;
      });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if ((!query.trim() && !selectedImage) || isLoading || !isSystemReady) return;

    const currentText = query.trim();
    const currentImage = selectedImage ? selectedImage.dataUrl : null;
    setSelectedImage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    setQuery('');
    await sendQuery(currentText, currentImage);
  };

  const handleConsentResponse = async (index, allowed) => {
    if (isLoading) return;

    setMessages((prev) => {
      const newMsgs = [...prev];
      newMsgs[index] = {
        ...newMsgs[index],
        consentAnswered: allowed ? 'allow' : 'deny'
      };
      return newMsgs;
    });

    try {
      await fetch('/api/consent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, consent: allowed }),
      });
    } catch (err) {
      console.error("Lỗi khi cập nhật consent:", err);
    }

    if (allowed) {
      await sendQuery("Tôi đồng ý cấp quyền, hãy hiển thị lịch sử giao dịch của tôi");
    } else {
      await sendQuery("Tôi không đồng ý cấp quyền truy cập thông tin cá nhân");
    }
  };

  return (
    <div className="app-container">
      <header className="header">
        <h1>EWallet Chatbot</h1>
      </header>

      <main className="chat-container" ref={chatContainerRef} onScroll={handleScroll}>
        {/* Bong bóng chat khởi tạo hệ thống riêng biệt, luôn hiển thị đầu tiên */}
        <div className="message-row bot-row system-init-row">
          <div className="avatar bot-avatar"><Bot size={20} /></div>
          <div className="message-bubble bot-bubble system-init-bubble">
            {getInitBubbleContent(loadedComponents, isSystemReady, initLoadingText)}
          </div>
        </div>

        {messages.map((msg, index) => {
          if (msg.role === 'user') {
            return (
              <div key={index} className="message-row user-row">
                <div className="message-bubble user-bubble">
                  {msg.image && (
                    <div className="user-image-container">
                      <img 
                        src={msg.image} 
                        alt="Đính kèm từ người dùng" 
                        className="user-attached-image" 
                        onClick={() => setLightboxImage(msg.image)}
                        title="Click để xem ảnh kích thước gốc"
                      />
                    </div>
                  )}
                  {msg.content && (
                    <ReactMarkdown components={markdownComponents}>{msg.content}</ReactMarkdown>
                  )}
                </div>
                <div className="avatar user-avatar"><User size={20} /></div>
              </div>
            );
          } else {
            const hasDirectContent = msg.content !== undefined && msg.content !== '';
            const hasDirectThinking = msg.thinking !== undefined && msg.thinking !== '';
            let thinkingText = msg.thinking || null;
            let answerContent = msg.content || '';
            let isThinkingFinished = !msg.isThinking || msg.isFinished || Boolean(answerContent && answerContent.trim());

            if (!hasDirectContent && !hasDirectThinking && msg.rawContent) {
              const parsed = parseMessage(msg.rawContent);
              thinkingText = parsed.thinking;
              answerContent = parsed.content;
              isThinkingFinished = parsed.isThinkingFinished;
            }

            const hasStartedThinking = Boolean(thinkingText);
            return (
              <div key={index} className="message-row bot-row">
                <div className="avatar bot-avatar"><Bot size={20} /></div>
                <div className="message-bubble bot-bubble">
                  <SystemLogBlock logs={msg.logs} isFinished={msg.isFinished} hasStartedThinking={hasStartedThinking} />
                  <ThinkingBlock thinking={thinkingText} isFinished={isThinkingFinished} />
                  <div className="markdown-body">
                    <ReactMarkdown 
                      remarkPlugins={[remarkMath, remarkGfm]} 
                      rehypePlugins={[rehypeKatex]}
                      components={markdownComponents}
                    >
                      {answerContent}
                    </ReactMarkdown>
                  </div>
                  {msg.consentRequired && (
                    <div className="consent-card">
                      <div className="consent-header">
                        <ShieldAlert size={18} className="consent-icon" />
                        <span>Xác nhận quyền truy cập thông tin cá nhân</span>
                      </div>
                      <p className="consent-text">
                        Để tra cứu và hiển thị lịch sử giao dịch của bạn, hệ thống cần bạn cấp quyền truy cập thông tin cá nhân. Bạn có đồng ý cho phép không?
                      </p>
                      <div className="consent-actions">
                        <button
                          type="button"
                          className="consent-btn consent-btn-allow"
                          disabled={isLoading || Boolean(msg.consentAnswered)}
                          onClick={() => handleConsentResponse(index, true)}
                        >
                          <Check size={16} /> Cho phép
                        </button>
                        <button
                          type="button"
                          className="consent-btn consent-btn-deny"
                          disabled={isLoading || Boolean(msg.consentAnswered)}
                          onClick={() => handleConsentResponse(index, false)}
                        >
                          <X size={16} /> Không cho phép
                        </button>
                      </div>
                      {msg.consentAnswered && (
                        <div className={`consent-feedback ${msg.consentAnswered === 'allow' ? 'feedback-allow' : 'feedback-deny'}`}>
                          {msg.consentAnswered === 'allow' 
                            ? '✓ Bạn đã chọn Cho phép. Đang tải lịch sử giao dịch...' 
                            : '✕ Bạn đã chọn Không cho phép.'}
                        </div>
                      )}
                    </div>
                  )}
                  {msg.stats && <div className="stats-block">{msg.stats}</div>}
                </div>
              </div>
            );
          }
        })}
        {isLoading && systemStatus && (
          <div className="status-indicator">
            <Loader2 className="spinner" size={16} />
            <span>{systemStatus}</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </main>

      <footer className="input-area">
        {!isSystemReady && (
          <div className="init-loading-banner">
            <Loader2 className="spinner" size={14} />
            <span>{initLoadingText || 'Loading...'}</span>
          </div>
        )}
        {selectedImage && (
          <div className="image-preview-container">
            <div className="image-preview-thumbnail-wrap">
              <img src={selectedImage.dataUrl} alt="Preview" className="image-preview-thumbnail" />
              <button 
                type="button" 
                className="image-preview-remove-btn" 
                onClick={removeImage}
                title="Xóa ảnh đính kèm"
              >
                <X size={14} />
              </button>
            </div>
            <div className="image-preview-meta">
              <span className="image-preview-filename">{selectedImage.name || 'Ảnh đính kèm'}</span>
              <span className="image-preview-hint">Đã sẵn sàng gửi kèm câu hỏi</span>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="input-form">
          <input 
            type="file" 
            ref={fileInputRef} 
            accept="image/*" 
            style={{ display: 'none' }} 
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                handleImageSelect(e.target.files[0]);
              }
            }} 
          />
          <button 
            type="button" 
            className="attach-btn" 
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading || !isSystemReady}
            title="Đính kèm hình ảnh (hoặc dán ảnh từ clipboard)"
          >
            <ImageIcon size={20} />
          </button>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onPaste={handlePaste}
            placeholder={selectedImage ? "Nhập thêm câu hỏi kèm theo ảnh (hoặc Enter để gửi)..." : "Hỏi về tài liệu của bạn (hoặc dán/đính kèm ảnh)..."}
            disabled={isLoading}
          />
          <button 
            type="submit" 
            disabled={isLoading || (!query.trim() && !selectedImage) || !isSystemReady}
            title={!isSystemReady ? "System loading..." : "Gửi"}
          >
            {isLoading ? <Loader2 className="spinner" size={20} /> : <Send size={20} />}
          </button>
        </form>
      </footer>

      {lightboxImage && (
        <div className="lightbox-overlay" onClick={() => setLightboxImage(null)}>
          <div className="lightbox-content" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="lightbox-close-btn"
              onClick={() => setLightboxImage(null)}
              title="Đóng ảnh xem trước"
            >
              <X size={18} />
            </button>
            <img src={lightboxImage} alt="Xem trước ảnh gốc" className="lightbox-image" />
          </div>
        </div>
      )}

    </div>
  );
}

export default App;
