import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Folder, Upload, Trash2, Edit3, RefreshCw, Plus, X, 
  Check, AlertCircle, FileSpreadsheet, FileText, Search, Loader2, ArrowLeft, Save, ExternalLink
} from 'lucide-react';
import './AdminApp.css';

const CATEGORIES = [
  { id: 'all', label: 'Tất cả' },
  { id: 'knowledge', label: 'Chính sách (knowledge)' },
  { id: 'faq', label: 'Hỏi đáp (faq)' },
  { id: 'telecom', label: 'Gói cước (telecom)' },
  { id: 'navigation', label: 'Điều hướng (navigation)' },
];

export default function AdminApp() {
  const [docs, setDocs] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [uploadCategory, setUploadCategory] = useState('auto');
  const [notification, setNotification] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [backendOnline, setBackendOnline] = useState(null);

  // Editor State
  const [editingDoc, setEditingDoc] = useState(null);
  const [textContent, setTextContent] = useState('');
  const [excelRows, setExcelRows] = useState([]);
  const [excelCols, setExcelCols] = useState([]);
  const [excelIsQa, setExcelIsQa] = useState(true);
  const [excelQCol, setExcelQCol] = useState('question');
  const [excelACol, setExcelACol] = useState('answer');
  const [excelSearch, setExcelSearch] = useState('');

  const fileInputRef = useRef(null);
  const notifTimerRef = useRef(null);
  const backendPort = import.meta.env.VITE_BACKEND_PORT || 8000;
  const userPort = import.meta.env.VITE_USER_PORT || 3000;
  const baseUrl = '/api';
  const fallbackBaseUrl = `http://127.0.0.1:${backendPort}/api`;
  const userChatbotUrl = `http://127.0.0.1:${userPort}`;

  const showNotif = useCallback((text, type = 'success') => {
    if (notifTimerRef.current) {
      clearTimeout(notifTimerRef.current);
    }
    setNotification({ text, type });
    notifTimerRef.current = setTimeout(() => {
      setNotification(null);
      notifTimerRef.current = null;
    }, 4500);
  }, []);

  useEffect(() => {
    return () => {
      if (notifTimerRef.current) {
        clearTimeout(notifTimerRef.current);
      }
    };
  }, []);

  const checkBackendHealth = useCallback(async () => {
    try {
      let res = await fetch(`${baseUrl}/health`);
      if (!res.ok) {
        res = await fetch(`${fallbackBaseUrl}/health`);
      }
      setBackendOnline(res.ok);
    } catch {
      try {
        const fbRes = await fetch(`${fallbackBaseUrl}/health`);
        setBackendOnline(fbRes.ok);
      } catch {
        setBackendOnline(false);
      }
    }
  }, [baseUrl, fallbackBaseUrl]);

  const fetchDocs = useCallback(async () => {
    setIsLoading(true);
    try {
      let res = await fetch(`${baseUrl}/docs`);
      if (!res.ok) {
        res = await fetch(`${fallbackBaseUrl}/docs`);
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setDocs(data.documents || []);
      setBackendOnline(true);
    } catch (err) {
      console.warn('Proxy fetch failed, attempting direct fallback...', err);
      try {
        const fbRes = await fetch(`${fallbackBaseUrl}/docs`);
        if (fbRes.ok) {
          const fbData = await fbRes.json();
          setDocs(fbData.documents || []);
          setBackendOnline(true);
          return;
        }
      } catch (fbErr) {
        console.error('Direct fallback fetch failed:', fbErr);
      }
      showNotif(`Lỗi: ${err.message}`, 'error');
      setBackendOnline(false);
    } finally {
      setIsLoading(false);
    }
  }, [baseUrl, fallbackBaseUrl, showNotif]);

  useEffect(() => {
    fetchDocs();
    checkBackendHealth();
    const interval = setInterval(checkBackendHealth, 15000);
    return () => clearInterval(interval);
  }, [fetchDocs, checkBackendHealth]);

  const handleUpload = async (file) => {
    if (!file) return;
    setActionLoading(true);
    const formData = new FormData();
    formData.append('file', file);
    if (uploadCategory && uploadCategory !== 'auto') {
      formData.append('category', uploadCategory);
    }

    try {
      const res = await fetch(`${baseUrl}/docs/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Lỗi khi upload file');
      if (data.index_result?.status === 'error') {
        showNotif(`Đã lưu file ${file.name} nhưng lỗi index: ${data.index_result.reason}`, 'error');
      } else {
        showNotif(`Đã tải lên vào ${data.category}/ và cập nhật thành công: ${file.name}`);
      }
      fetchDocs();
    } catch (err) {
      showNotif(`Upload thất bại: ${err.message}`, 'error');
    } finally {
      setActionLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (doc) => {
    const targetKey = doc.relative_path || doc.filename;
    if (!window.confirm(`Bạn có chắc chắn muốn xóa tài liệu "${targetKey}"? Dữ liệu vector trong hệ thống sẽ được gỡ bỏ hoàn toàn.`)) {
      return;
    }
    setActionLoading(true);
    try {
      const res = await fetch(`${baseUrl}/docs/${encodeURIComponent(targetKey)}`, {
        method: 'DELETE',
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Lỗi khi xóa file');
      showNotif(`Đã xóa thành công: ${targetKey}`);
      fetchDocs();
    } catch (err) {
      showNotif(`Lỗi xóa file: ${err.message}`, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReindex = async (doc) => {
    const targetKey = doc.relative_path || doc.filename;
    setActionLoading(true);
    try {
      const res = await fetch(`${baseUrl}/docs/${encodeURIComponent(targetKey)}/reindex`, {
        method: 'POST',
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Lỗi khi index lại');
      showNotif(`Đã index lại thành công ${targetKey} (${data.chunks_count || 0} chunks)`);
      fetchDocs();
    } catch (err) {
      showNotif(`Lỗi re-index: ${err.message}`, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSyncAll = async () => {
    setActionLoading(true);
    try {
      const res = await fetch(`${baseUrl}/docs/sync`, {
        method: 'POST',
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Lỗi khi đồng bộ');
      const total = data.total_changes || 0;
      showNotif(`Đồng bộ hoàn tất! (Phát hiện và xử lý ${total} thay đổi trên các danh mục)`);
      fetchDocs();
    } catch (err) {
      showNotif(`Lỗi đồng bộ: ${err.message}`, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleStartEdit = async (doc) => {
    const targetKey = doc.relative_path || doc.filename;
    setActionLoading(true);
    try {
      const res = await fetch(`${baseUrl}/docs/${encodeURIComponent(targetKey)}`);
      if (!res.ok) throw new Error('Không thể tải nội dung file');
      const data = await res.json();
      setEditingDoc(doc);
      if (data.type === 'excel') {
        setExcelRows(data.rows || []);
        setExcelCols(data.columns || ['question', 'answer']);
        setExcelIsQa(Boolean(data.is_qa ?? (doc.category === 'faq')));
        setExcelQCol(data.q_col || data.columns?.[0] || 'question');
        setExcelACol(data.a_col || data.columns?.[1] || 'answer');
        setExcelSearch('');
      } else {
        setTextContent(data.content || '');
      }
    } catch (err) {
      showNotif(`Không thể mở chỉnh sửa: ${err.message}`, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveTextEdit = async () => {
    if (!editingDoc) return;
    const targetKey = editingDoc.relative_path || editingDoc.filename;
    setActionLoading(true);
    try {
      const res = await fetch(`${baseUrl}/docs/${encodeURIComponent(targetKey)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: textContent }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Lỗi lưu tài liệu');
      if (data.index_result?.status === 'error') {
        showNotif(`Đã lưu ${targetKey} nhưng lỗi index: ${data.index_result.reason}`, 'error');
      } else {
        showNotif(`Đã lưu và cập nhật cho ${targetKey}`);
      }
      setEditingDoc(null);
      fetchDocs();
    } catch (err) {
      showNotif(`Lỗi khi lưu: ${err.message}`, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveExcelEdit = async () => {
    if (!editingDoc) return;
    const targetKey = editingDoc.relative_path || editingDoc.filename;
    setActionLoading(true);
    try {
      const res = await fetch(`${baseUrl}/docs/${encodeURIComponent(targetKey)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows: excelRows, columns: excelCols }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Lỗi lưu bảng Excel');
      if (data.index_result?.status === 'error') {
        showNotif(`Đã lưu ${targetKey} nhưng lỗi index: ${data.index_result.reason}`, 'error');
      } else {
        showNotif(`Đã lưu và cập nhật thành công ${targetKey} (${excelRows.length} dòng)`);
      }
      setEditingDoc(null);
      fetchDocs();
    } catch (err) {
      showNotif(`Lỗi khi lưu Excel: ${err.message}`, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleAddExcelRow = () => {
    const newRow = {};
    excelCols.forEach((col) => {
      newRow[col] = '';
    });
    setExcelRows([newRow, ...excelRows]);
  };

  const handleDeleteExcelRow = (idx) => {
    const updated = [...excelRows];
    updated.splice(idx, 1);
    setExcelRows(updated);
  };

  const handleUpdateExcelField = (idx, field, value) => {
    const updated = [...excelRows];
    updated[idx] = { ...updated[idx], [field]: value };
    setExcelRows(updated);
  };

  // Filter docs by category and search query
  const filteredDocs = (docs || []).filter((d) => {
    if (!d) return false;
    if (activeTab !== 'all' && d.category !== activeTab) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return (
        (d.filename && d.filename.toLowerCase().includes(q)) ||
        (d.relative_path && d.relative_path.toLowerCase().includes(q))
      );
    }
    return true;
  });

  return (
    <div className="admin-container">
      {/* Top Header */}
      <header className="admin-header">
        <div className="admin-header-inner">
          <div className="admin-brand">
            <Folder size={24} color="#60a5fa" />
            <h1>E-Wallet Assistant | Quản lý Tài liệu & Tri thức</h1>
            <span className="admin-badge">{docs.length} tài liệu</span>
          </div>

          <div className="admin-header-actions">
            <div className="status-chip" title={`Kết nối Backend API (Port ${backendPort})`}>
              <span className={`status-dot ${backendOnline ? 'online' : ''}`} />
              <span>{backendOnline ? `Backend :${backendPort}` : 'Backend Offline'}</span>
            </div>

            <a 
              href={userChatbotUrl} 
              target="_blank" 
              rel="noopener noreferrer" 
              className="btn-action btn-outline"
              title="Mở giao diện Chatbot của Người dùng trên tab mới"
            >
              <ExternalLink size={14} />
              <span>Giao diện Chatbot ({userPort})</span>
            </a>

            {!editingDoc && (
              <>
                <button 
                  className="btn-action btn-secondary" 
                  onClick={handleSyncAll}
                  disabled={actionLoading || isLoading}
                  title="Kiểm tra và đồng bộ lại các file đã thay đổi trên toàn bộ thư mục docs/"
                >
                  <RefreshCw size={14} className={actionLoading ? 'spin-icon' : ''} />
                  <span>Đồng bộ tất cả</span>
                </button>

                <input 
                  type="file" 
                  ref={fileInputRef} 
                  style={{ display: 'none' }} 
                  accept=".md,.xlsx,.xls,.json,.txt"
                  onChange={(e) => {
                    if (e.target.files?.[0]) handleUpload(e.target.files[0]);
                  }}
                />
                <button 
                  className="btn-action btn-primary" 
                  onClick={() => fileInputRef.current?.click()}
                  disabled={actionLoading || isLoading}
                  title="Tải lên tài liệu mới vào thư mục tương ứng"
                >
                  <Upload size={14} />
                  <span>Tải lên file</span>
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="admin-main">
        {notification && (
          <div className={`admin-notification admin-notif-${notification.type}`}>
            <span>{notification.text}</span>
            <button onClick={() => setNotification(null)} className="btn-close-sm">
              <X size={15} />
            </button>
          </div>
        )}

        {/* EDITING VIEW */}
        {editingDoc ? (
          <div className="editor-container">
            <div className="editor-header">
              <div className="editor-title">
                <button 
                  className="btn-action btn-secondary" 
                  onClick={() => setEditingDoc(null)}
                  disabled={actionLoading}
                >
                  <ArrowLeft size={16} /> Danh sách tài liệu
                </button>
                <h3>
                  Đang chỉnh sửa: <span style={{ color: '#60a5fa' }}>{editingDoc.relative_path || editingDoc.filename}</span>
                </h3>
              </div>

              <div className="editor-actions">
                {editingDoc.file_type === 'excel' ? (
                  <button 
                    className="btn-action btn-primary" 
                    onClick={handleSaveExcelEdit}
                    disabled={actionLoading}
                  >
                    {actionLoading ? <Loader2 size={15} className="spin-icon" /> : <Save size={15} />}
                    <span>Lưu thay đổi & Re-index</span>
                  </button>
                ) : (
                  <button 
                    className="btn-action btn-primary" 
                    onClick={handleSaveTextEdit}
                    disabled={actionLoading}
                  >
                    {actionLoading ? <Loader2 size={15} className="spin-icon" /> : <Save size={15} />}
                    <span>Lưu nội dung & Re-index</span>
                  </button>
                )}
              </div>
            </div>

            {/* Excel Q&A / Multi-column Table Visual Editor */}
            {editingDoc.file_type === 'excel' ? (
              <div className="excel-qa-editor">
                <div className="excel-qa-toolbar">
                  <div className="excel-qa-stats">
                    {excelIsQa ? (
                      <>
                        Tổng số cặp Q&amp;A: <strong>{excelRows.length}</strong> | Cột câu hỏi: <strong>{excelQCol}</strong> | Cột câu trả lời: <strong>{excelACol}</strong>
                      </>
                    ) : (
                      <>
                        Tổng số dòng dữ liệu: <strong>{excelRows.length}</strong> | Các cột ({excelCols.length}): <strong>{excelCols.join(', ')}</strong>
                      </>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 10 }}>
                    <input 
                      type="text" 
                      placeholder={excelIsQa ? "Tìm kiếm trong bảng câu hỏi..." : "Tìm kiếm trong bảng dữ liệu..."} 
                      value={excelSearch}
                      onChange={(e) => setExcelSearch(e.target.value)}
                      style={{
                        background: '#1f2937',
                        border: '1px solid #334155',
                        borderRadius: 6,
                        padding: '6px 12px',
                        color: '#f3f4f6',
                        fontSize: '0.82rem',
                        width: '240px'
                      }}
                    />
                    <button className="btn-action btn-secondary" onClick={handleAddExcelRow}>
                      <Plus size={14} /> {excelIsQa ? 'Thêm câu hỏi mới' : 'Thêm dòng mới'}
                    </button>
                  </div>
                </div>

                <div className="excel-qa-rows-list">
                  {excelRows
                    .map((row, originalIdx) => ({ row, originalIdx }))
                    .filter(({ row }) => {
                      if (!excelSearch.trim()) return true;
                      const s = excelSearch.toLowerCase();
                      if (excelIsQa) {
                        return (
                          String(row[excelQCol] || '').toLowerCase().includes(s) ||
                          String(row[excelACol] || '').toLowerCase().includes(s)
                        );
                      }
                      return excelCols.some((col) => String(row[col] || '').toLowerCase().includes(s));
                    })
                    .map(({ row, originalIdx }) => (
                      <div key={originalIdx} className="qa-card">
                        <div className="qa-card-header">
                          <span className="qa-card-index">Dòng {originalIdx + 1}</span>
                          <button 
                            className="btn-icon btn-icon-danger" 
                            onClick={() => handleDeleteExcelRow(originalIdx)}
                            title="Xóa dòng này"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                        {excelIsQa ? (
                          <>
                            <div className="qa-field">
                              <label>Câu hỏi (Question - Chỉ tạo vector embedding cột này):</label>
                              <input 
                                type="text" 
                                value={row[excelQCol] || ''}
                                onChange={(e) => handleUpdateExcelField(originalIdx, excelQCol, e.target.value)}
                                placeholder="Nhập câu hỏi mẫu..."
                              />
                            </div>
                            <div className="qa-field">
                              <label>Câu trả lời (Answer - Lưu vào metadata, đưa nguyên văn vào ngữ cảnh LLM):</label>
                              <textarea 
                                value={row[excelACol] || ''}
                                onChange={(e) => handleUpdateExcelField(originalIdx, excelACol, e.target.value)}
                                placeholder="Nhập câu trả lời chi tiết..."
                              />
                            </div>
                          </>
                        ) : (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
                            {excelCols.map((col) => (
                              <div key={col} className="qa-field">
                                <label>{col}:</label>
                                <input 
                                  type="text" 
                                  value={row[col] ?? ''}
                                  onChange={(e) => handleUpdateExcelField(originalIdx, col, e.target.value)}
                                  placeholder={`Nhập ${col}...`}
                                />
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                </div>
              </div>
            ) : (
              /* Text/Markdown Editor */
              <textarea 
                className="text-editor-textarea"
                value={textContent}
                onChange={(e) => setTextContent(e.target.value)}
                placeholder="Nhập nội dung văn bản markdown..."
              />
            )}
          </div>
        ) : (
          /* LIST VIEW */
          <>
            {/* Category tabs and Search bar */}
            <div className="admin-controls-bar">
              <div className="admin-tabs">
                {CATEGORIES.map((cat) => {
                  const count = cat.id === 'all' 
                    ? docs.length 
                    : docs.filter((d) => d.category === cat.id).length;
                  return (
                    <button 
                      key={cat.id}
                      className={`admin-tab-btn ${activeTab === cat.id ? 'active' : ''}`}
                      onClick={() => setActiveTab(cat.id)}
                    >
                      {cat.label} ({count})
                    </button>
                  );
                })}
              </div>

              <div className="admin-search-box">
                <Search size={15} color="#9ca3af" />
                <input 
                  type="text" 
                  placeholder="Tìm tài liệu theo tên..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>

            {/* Upload Dropzone with Category Selection */}
            <div className="admin-upload-container">
              <div className="admin-upload-options">
                <span>Danh mục tiếp nhận tệp:</span>
                <select 
                  className="category-select"
                  value={uploadCategory}
                  onChange={(e) => setUploadCategory(e.target.value)}
                >
                  <option value="auto">Tự động phân loại theo tên tệp</option>
                  <option value="knowledge">knowledge/ (Chính sách, điều khoản .md)</option>
                  <option value="faq">faq/ (Hỏi đáp Excel .xlsx)</option>
                  <option value="telecom">telecom/ (Gói cước .xlsx/.json)</option>
                  <option value="navigation">navigation/ (Điều hướng app .json/.md)</option>
                </select>
              </div>
              <div 
                className="admin-dropzone" 
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  if (e.dataTransfer.files?.[0]) handleUpload(e.dataTransfer.files[0]);
                }}
              >
                <div className="dropzone-content">
                  <Upload size={24} color="#60a5fa" />
                  <span>Kéo thả tài liệu vào đây hoặc nhấp để chọn tệp từ máy tính</span>
                  <span className="dropzone-hint">Định dạng hỗ trợ: .md, .xlsx, .json, .txt. Hệ thống sẽ tự động lưu và re-index vector vào Qdrant.</span>
                </div>
              </div>
            </div>

            {/* Document Table */}
            <div className="admin-table-wrap">
              {isLoading ? (
                <div style={{ textAlign: 'center', padding: 50, color: '#9ca3af' }}>
                  <Loader2 size={32} className="spin-icon" style={{ margin: '0 auto 12px' }} />
                  <p>Đang tải danh sách tài liệu từ Backend...</p>
                </div>
              ) : filteredDocs.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 50, color: '#9ca3af' }}>
                  <p>
                    {(!docs || docs.length === 0)
                      ? (backendOnline === false
                          ? 'Không thể kết nối đến Backend (:8000). Vui lòng kiểm tra máy chủ backend.'
                          : 'Chưa có tài liệu nào trong thư mục docs/.')
                      : 'Không có tài liệu nào phù hợp với bộ lọc hiện tại.'}
                  </p>
                  {(!docs || docs.length === 0) && (
                    <button 
                      className="btn-action btn-secondary" 
                      onClick={fetchDocs} 
                      style={{ marginTop: 14 }}
                      disabled={isLoading}
                    >
                      <RefreshCw size={14} className={isLoading ? 'spin-icon' : ''} /> Thử tải lại danh sách
                    </button>
                  )}
                </div>
              ) : (
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Tên tài liệu / Đường dẫn</th>
                      <th>Danh mục</th>
                      <th>Loại file</th>
                      <th>Kích thước</th>
                      <th>Trạng thái Vector Index</th>
                      <th>Cập nhật gần nhất</th>
                      <th style={{ textAlign: 'center' }}>Thao tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredDocs.map((doc) => (
                      <tr key={doc.relative_path || doc.filename}>
                        <td>
                          <div className="doc-file-info">
                            {doc.file_type === 'excel' ? (
                              <FileSpreadsheet size={18} color="#34d399" />
                            ) : doc.file_type === 'markdown' ? (
                              <FileText size={18} color="#60a5fa" />
                            ) : (
                              <FileText size={18} color="#c084fc" />
                            )}
                            <div className="doc-file-name-wrap">
                              <span className="doc-file-name">{doc.filename}</span>
                              <span className="doc-rel-path">{doc.relative_path}</span>
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className={`category-badge cat-${doc.category}`}>
                            {doc.category}
                          </span>
                        </td>
                        <td>
                          <span className={`type-tag type-${doc.file_type}`}>
                            {doc.file_type === 'excel' ? (doc.category === 'faq' ? 'Excel Q&A' : 'Excel Table') : doc.file_type}
                          </span>
                        </td>
                        <td>{doc.size_formatted}</td>
                        <td>
                          {doc.is_indexed ? (
                            <span className="status-badge status-indexed" title="Đã nhúng vector vào Qdrant">
                              <Check size={12} /> Đã index ({doc.chunk_count} chunks)
                            </span>
                          ) : doc.is_indexable ? (
                            <span className="status-badge status-not-indexed" title="Chưa được tạo vector index">
                              <AlertCircle size={12} /> Chưa index
                            </span>
                          ) : (
                            <span className="status-badge status-non-indexable" title="Tài liệu cấu hình hoặc gói cước viễn thông chuyên dụng">
                              Bỏ qua index
                            </span>
                          )}
                        </td>
                        <td style={{ color: '#9ca3af', fontSize: '0.8rem' }}>{doc.modified_at_str}</td>
                        <td>
                          <div className="row-actions" style={{ justifyContent: 'center' }}>
                            <button 
                              className="btn-icon" 
                              title="Chỉnh sửa tài liệu"
                              onClick={() => handleStartEdit(doc)}
                              disabled={actionLoading}
                            >
                              <Edit3 size={15} />
                            </button>
                            {doc.is_indexable && (
                              <button 
                                className="btn-icon" 
                                title="Index lại file này vào Qdrant"
                                onClick={() => handleReindex(doc)}
                                disabled={actionLoading}
                              >
                                <RefreshCw size={15} />
                              </button>
                            )}
                            <button 
                              className="btn-icon btn-icon-danger" 
                              title="Xóa tài liệu và gỡ khỏi index"
                              onClick={() => handleDelete(doc)}
                              disabled={actionLoading}
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
