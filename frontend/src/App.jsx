import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { Send, Loader2, Bot, User, ChevronDown, ChevronUp } from 'lucide-react';
import './App.css';

function parseMessage(text) {
  let thinkStart = text.indexOf('<think>');
  let thinkEnd = text.indexOf('</think>');
  let startTagLength = 7;
  let endTagLength = 8;
  
  if (thinkStart === -1) {
    thinkStart = text.indexOf('<thought>');
    thinkEnd = text.indexOf('</thought>');
    startTagLength = 9;
    endTagLength = 10;
  }
  if (thinkStart === -1) {
    thinkStart = text.indexOf('[Begin thinking]');
    thinkEnd = text.indexOf('[End thinking]');
    startTagLength = 16;
    endTagLength = 14;
  }

  if (thinkStart !== -1) {
    if (thinkEnd !== -1) {
      const before = text.substring(0, thinkStart);
      const thinking = text.substring(thinkStart + startTagLength, thinkEnd);
      const after = text.substring(thinkEnd + endTagLength);
      return { thinking, content: before + after, isThinkingFinished: true };
    } else {
      const before = text.substring(0, thinkStart);
      const thinking = text.substring(thinkStart + startTagLength);
      return { thinking, content: before, isThinkingFinished: false };
    }
  }
  return { thinking: null, content: text, isThinkingFinished: true };
}

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

function App() {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [systemStatus, setSystemStatus] = useState('');
  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [isServerReady, setIsServerReady] = useState(false);

  useEffect(() => {
    let isMounted = true;
    const checkServer = async () => {
      try {
        const response = await fetch(`http://127.0.0.1:${import.meta.env.VITE_BACKEND_PORT || 8000}/api/health`);
        if (response.ok && isMounted) {
          setIsServerReady(true);
        } else if (isMounted) {
          setTimeout(checkServer, 3000);
        }
      } catch (error) {
        if (isMounted) setTimeout(checkServer, 3000);
      }
    };
    checkServer();
    return () => { isMounted = false; };
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
  }, [messages, systemStatus]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim() || isLoading || !isServerReady) return;

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
        {messages.map((msg, index) => {
          if (msg.role === 'user') {
            return (
              <div key={index} className="message-row user-row">
                <div className="message-bubble user-bubble">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
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
        {!isServerReady && (
          <div style={{ padding: '10px 16px', fontSize: '14px', color: '#854d0e', backgroundColor: '#fef08a', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Loader2 className="spinner" size={16} />
            <span>Hệ thống đang khởi động và nạp mô hình AI. Vui lòng chờ trong giây lát...</span>
          </div>
        )}
        <form onSubmit={handleSubmit} className="input-form">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={isServerReady ? "Hỏi về tài liệu của bạn..." : "Đang chờ hệ thống sẵn sàng..."}
            disabled={isLoading || !isServerReady}
          />
          <button type="submit" disabled={isLoading || !query.trim() || !isServerReady}>
            <Send size={20} />
          </button>
        </form>
      </footer>
    </div>
  );
}

export default App;
