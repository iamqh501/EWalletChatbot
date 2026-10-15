import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { Send, Loader2, Bot, User, ChevronDown, ChevronUp } from 'lucide-react';
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
  td: ({ node, children, ...props }) => <td {...props}>{renderWithLineBreaks(children)}</td>,
  th: ({ node, children, ...props }) => <th {...props}>{renderWithLineBreaks(children)}</th>,
  p: ({ node, children, ...props }) => <p {...props}>{renderWithLineBreaks(children)}</p>,
  li: ({ node, children, ...props }) => <li {...props}>{renderWithLineBreaks(children)}</li>,
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
  const [query, setQuery] = useState('');
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
      const port = import.meta.env.VITE_BACKEND_PORT || 8000;
      try {
        const response = await fetch(`http://127.0.0.1:${port}/api/init-stream`, {
          signal: abortController.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop();

          let currentEvent = 'message';
          for (const line of lines) {
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
              } catch (e) {
                console.error("Lỗi parse SSE init data:", e);
              }
            }
          }
        }
      } catch (err) {
        if (!isMounted || abortController.signal.aborted) return;
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
  }, [messages, systemStatus, loadedComponents, initLoadingText]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim() || isLoading || !isSystemReady) return;

    const userMessage = { role: 'user', content: query };
    setMessages((prev) => [...prev, userMessage]);
    setQuery('');
    setIsLoading(true);
    setSystemStatus('Đang khởi tạo...');
    setAutoScroll(true);
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 100);

    let assistantMessage = { role: 'assistant', rawContent: '', stats: null, logs: [], isFinished: false };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      const response = await fetch(`http://127.0.0.1:${import.meta.env.VITE_BACKEND_PORT || 8000}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMessage.content }),
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep incomplete line

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            var eventType = line.substring(7).trim();
          } else if (line.startsWith('data: ')) {
            const dataStr = line.substring(6);
            if (dataStr === '[DONE]') continue;
            
            try {
              const data = JSON.parse(dataStr);
              
              if (eventType === 'status') {
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
              } else if (eventType === 'token') {
                if (data.text) {
                  setSystemStatus(''); // clear system status when typing starts
                }
                setMessages((prev) => {
                  const newMsgs = [...prev];
                  const lastIndex = newMsgs.length - 1;
                  newMsgs[lastIndex] = {
                    ...newMsgs[lastIndex],
                    rawContent: newMsgs[lastIndex].rawContent + data.text
                  };
                  return newMsgs;
                });
              } else if (eventType === 'stats') {
                setMessages((prev) => {
                  const newMsgs = [...prev];
                  const lastIndex = newMsgs.length - 1;
                  newMsgs[lastIndex] = {
                    ...newMsgs[lastIndex],
                    stats: data.text
                  };
                  return newMsgs;
                });
              }
            } catch (e) {
              console.error("Error parsing SSE data", e);
            }
          }
        }
      }
    } catch (error) {
      console.error("Fetch error:", error);
      setSystemStatus('Có lỗi xảy ra: ' + error.message);
    } finally {
      setIsLoading(false);
      setMessages((prev) => {
        const newMsgs = [...prev];
        if (newMsgs.length > 0) {
          const lastIndex = newMsgs.length - 1;
          newMsgs[lastIndex] = { ...newMsgs[lastIndex], isFinished: true };
        }
        return newMsgs;
      });
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
                  <ReactMarkdown components={markdownComponents}>{msg.content}</ReactMarkdown>
                </div>
                <div className="avatar user-avatar"><User size={20} /></div>
              </div>
            );
          } else {
            const parsed = parseMessage(msg.rawContent);
            const hasStartedThinking = parsed.thinking !== null;
            return (
              <div key={index} className="message-row bot-row">
                <div className="avatar bot-avatar"><Bot size={20} /></div>
                <div className="message-bubble bot-bubble">
                  <SystemLogBlock logs={msg.logs} isFinished={msg.isFinished} hasStartedThinking={hasStartedThinking} />
                  <ThinkingBlock thinking={parsed.thinking} isFinished={parsed.isThinkingFinished} />
                  <div className="markdown-body">
                    <ReactMarkdown 
                      remarkPlugins={[remarkMath, remarkGfm]} 
                      rehypePlugins={[rehypeKatex]}
                      components={markdownComponents}
                    >
                      {parsed.content}
                    </ReactMarkdown>
                  </div>
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
        <form onSubmit={handleSubmit} className="input-form">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Hỏi về tài liệu của bạn..."
            disabled={isLoading}
          />
          <button 
            type="submit" 
            disabled={isLoading || !query.trim() || !isSystemReady}
            title={!isSystemReady ? "System loading..." : "Gửi"}
          >
            {isLoading ? <Loader2 className="spinner" size={20} /> : <Send size={20} />}
          </button>
        </form>
      </footer>
    </div>
  );
}

export default App;
