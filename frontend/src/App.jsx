import React, { useState } from 'react';
import axios from 'axios';
import { Upload, FileSpreadsheet, Search, CheckCircle2, AlertCircle, Loader2, Download } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

function App() {
  const [source, setSource] = useState('akakce');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [resultFileId, setResultFileId] = useState(null);
  const [error, setError] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [manualName, setManualName] = useState('');
  const [manualBrand, setManualBrand] = useState('');
  const [manualResult, setManualResult] = useState(null);
  const [manualLoading, setManualLoading] = useState(false);

  const [activeTab, setActiveTab] = useState('single'); // 'single' or 'bulk'

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile && (selectedFile.name.endsWith('.xlsx') || selectedFile.name.endsWith('.xls'))) {
      setFile(selectedFile);
      setError(null);
    } else {
      setError('Lütfen geçerli bir Excel dosyası (.xlsx veya .xls) seçin.');
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && (droppedFile.name.endsWith('.xlsx') || droppedFile.name.endsWith('.xls'))) {
      setFile(droppedFile);
      setError(null);
    } else {
      setError('Lütfen geçerli bir Excel dosyası (.xlsx veya .xls) seçin.');
    }
  };

  const processFile = async () => {
    if (!file) return;
    
    setLoading(true);
    setProgress(0);
    setError(null);
    setResultFileId(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('source', source);

    try {
      const response = await axios.post('/api/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (response.data.jobId) {
        const jobId = response.data.jobId;
        
        // Start polling
        const pollInterval = setInterval(async () => {
          try {
            const statusRes = await axios.get(`/api/status/${jobId}`);
            const { status, progress, total, fileId, error: jobError } = statusRes.data;
            
            if (total > 0) {
              const percentage = Math.round((progress / total) * 100);
              setProgress(percentage);
              // Store current progress state to show in UI
              setProcessingInfo({ progress, total });
            }

            if (status === 'completed') {
              clearInterval(pollInterval);
              setResultFileId(fileId);
              setLoading(false);
            } else if (status === 'failed') {
              clearInterval(pollInterval);
              setError('Hata: ' + jobError);
              setLoading(false);
            }
          } catch (err) {
            clearInterval(pollInterval);
            setError('Durum sorgulanırken hata oluştu.');
            setLoading(false);
          }
        }, 1500);
      } else {
        setError('İşlem başlatılamadı.');
        setLoading(false);
      }
    } catch (err) {
      setError('Bağlantı hatası: ' + (err.response?.data?.detail || err.message));
      setLoading(false);
    }
  };

  const [processingInfo, setProcessingInfo] = useState({ progress: 0, total: 0 });

  const downloadResult = () => {
    window.open(`/api/download/${resultFileId}`, '_blank');
  };

  const handleManualSearch = async (e) => {
    e.preventDefault();
    if (!manualName) return;
    
    setManualLoading(true);
    setManualResult(null);
    setError(null);

    const formData = new FormData();
    formData.append('source', source);
    formData.append('name', manualName);
    formData.append('brand', manualBrand);

    try {
      const response = await axios.post('/api/search', formData);
      if (response.data.success) {
        setManualResult(response.data.url);
      } else {
        setError(response.data.message || 'Ürün bulunamadı.');
      }
    } catch (err) {
      setError('Arama sırasında bir hata oluştu.');
    } finally {
      setManualLoading(false);
    }
  };

  return (
    <div className="container">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="card"
      >
        <header>
          <h1>Ürün URL Bulucu</h1>
          <p>Excel listenizdeki ürünlerin Akakçe veya Cimri üzerindeki en ucuz fiyatlı linklerini saniyeler içinde bulun.</p>
        </header>

        <div className="options-container">
          <motion.div 
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className={`option-card ${source === 'akakce' ? 'active' : ''}`}
            onClick={() => setSource('akakce')}
          >
            <div className="source-icon">A</div>
            <span>Akakçe</span>
          </motion.div>

          <motion.div 
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className={`option-card ${source === 'cimri' ? 'active' : ''}`}
            onClick={() => setSource('cimri')}
          >
            <div className="source-icon">C</div>
            <span>Cimri</span>
          </motion.div>
        </div>

        <div className="tab-container">
          <button 
            className={`tab ${activeTab === 'single' ? 'active' : ''}`} 
            onClick={() => setActiveTab('single')}
          >
            Tekli Arama
          </button>
          <button 
            className={`tab ${activeTab === 'bulk' ? 'active' : ''}`} 
            onClick={() => setActiveTab('bulk')}
          >
            Toplu Excel
          </button>
        </div>

        {activeTab === 'single' ? (
          <form className="manual-search-form" onSubmit={handleManualSearch}>
            <div className="input-group">
              <input 
                type="text" 
                placeholder="Ürün Adı (Örn: Bosch GWS 750)" 
                value={manualName}
                onChange={(e) => setManualName(e.target.value)}
                className="text-input"
              />
              <input 
                type="text" 
                placeholder="Marka (Opsiyonel)" 
                value={manualBrand}
                onChange={(e) => setManualBrand(e.target.value)}
                className="text-input brand-input"
              />
            </div>
            <button className="btn search-btn" type="submit" disabled={manualLoading || !manualName}>
              {manualLoading ? <Loader2 className="animate-spin" size={20} /> : <Search size={20} />}
              <span>{manualLoading ? 'Aranıyor...' : 'Hemen Bul'}</span>
            </button>

            <AnimatePresence>
              {manualResult && (
                <motion.div 
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="manual-result-card"
                >
                  <div className="result-header">
                    <CheckCircle2 size={24} color="#22c55e" />
                    <span>Ürün Bulundu!</span>
                  </div>
                  <a href={manualResult} target="_blank" rel="noopener noreferrer" className="result-link">
                    {manualResult}
                  </a>
                </motion.div>
              )}
            </AnimatePresence>
          </form>
        ) : (
          <div 
            className={`upload-zone ${dragging ? 'dragging' : ''} ${loading ? 'processing' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => !loading && document.getElementById('fileInput').click()}
          >
            <input 
              type="file" 
              id="fileInput" 
              hidden 
              onChange={handleFileChange}
              accept=".xlsx, .xls"
            />
            {file ? (
              <div className="file-info">
                <FileSpreadsheet size={48} color="#3b82f6" />
                <div className="file-details">
                  <strong>{file.name}</strong>
                  <span>{(file.size / 1024).toFixed(1)} KB</span>
                </div>
                {!loading && (
                  <button className="remove-file" onClick={(e) => { e.stopPropagation(); setFile(null); }}>&times;</button>
                )}
              </div>
            ) : (
              <div className="upload-prompt">
                <Upload size={48} color="#64748b" />
                <p>Excel dosyasını buraya sürükleyin veya <span style={{color: '#3b82f6'}}>tıklayarak seçin</span></p>
              </div>
            )}
          </div>
        )}

        {error && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="error-msg"
          >
            <AlertCircle size={20} />
            <span>{error}</span>
          </motion.div>
        )}

        <div className="actions">
          {!resultFileId ? (
            <button 
              className="btn" 
              disabled={!file || loading}
              onClick={processFile}
            >
              {loading ? (
                <>
                  <Loader2 className="animate-spin" size={20} />
                  <span>İşleniyor...</span>
                </>
              ) : (
                <>
                  <Search size={20} />
                  <span>Linkleri Bul</span>
                </>
              )}
            </button>
          ) : (
            <button className="btn success-btn" onClick={downloadResult}>
              <Download size={20} />
              <span>Sonuçları İndir</span>
            </button>
          )}
        </div>

        <AnimatePresence>
          {loading && (
            <motion.div 
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="status-container"
            >
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${progress}%` }}></div>
              </div>
              <p className="pulse">
                {processingInfo.total > 0 
                  ? `Ürünler taranıyor: ${processingInfo.progress} / ${processingInfo.total} (%${progress})` 
                  : "Dosya hazırlanıyor..."}
              </p>
            </motion.div>
          )}
        </AnimatePresence>


        {resultFileId && (
          <motion.div 
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="success-container"
          >
            <CheckCircle2 size={48} color="#22c55e" />
            <h3>Tamamlandı!</h3>
            <p>Tüm ürünler başarıyla tarandı ve URL'ler Excel dosyanıza eklendi.</p>
          </motion.div>
        )}
      </motion.div>
      
      <style>{`
        .tab-container {
          display: flex;
          gap: 1rem;
          margin-bottom: 2rem;
          background: rgba(15, 23, 42, 0.4);
          padding: 0.4rem;
          border-radius: 14px;
        }
        .tab {
          flex: 1;
          padding: 0.75rem;
          border: none;
          background: transparent;
          color: #94a3b8;
          cursor: pointer;
          border-radius: 10px;
          font-weight: 600;
          transition: all 0.2s;
        }
        .tab.active {
          background: #3b82f6;
          color: white;
          box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
        }
        .manual-search-form {
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
          margin-bottom: 2rem;
        }
        .input-group {
          display: flex;
          gap: 1rem;
        }
        .text-input {
          flex: 2;
          background: rgba(15, 23, 42, 0.6);
          border: 1px solid rgba(255, 255, 255, 0.1);
          padding: 1rem 1.5rem;
          border-radius: 12px;
          color: white;
          font-size: 1rem;
          outline: none;
          transition: all 0.2s;
        }
        .text-input:focus {
          border-color: #3b82f6;
          background: rgba(15, 23, 42, 0.8);
        }
        .brand-input {
          flex: 1;
        }
        .manual-result-card {
          background: rgba(34, 197, 94, 0.1);
          border: 1px solid rgba(34, 197, 94, 0.2);
          padding: 1.5rem;
          border-radius: 16px;
          text-align: left;
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }
        .result-header {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-weight: 600;
          color: #22c55e;
        }
        .result-link {
          color: #3b82f6;
          text-decoration: none;
          word-break: break-all;
          font-size: 0.9rem;
          border-bottom: 1px solid transparent;
          transition: all 0.2s;
        }
        .result-link:hover {
          border-color: #3b82f6;
        }
        .remove-file {
          background: rgba(239, 68, 68, 0.2);
          color: #ef4444;
          border: none;
          width: 32px;
          height: 32px;
          border-radius: 50%;
          cursor: pointer;
          font-size: 1.5rem;
          display: flex;
          align-items: center;
          justify-content: center;
          margin-left: auto;
        }
      `}</style>
    </div>
  );
}

export default App;
