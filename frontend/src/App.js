import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

// API configuration
const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? '/api' 
  : 'http://localhost:5001';

function App() {
  const [paragraph, setParagraph] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const handleAnalyze = async () => {
    if (!paragraph.trim()) {
      setError('Please enter a paragraph to analyze');
      return;
    }

    setIsAnalyzing(true);
    setError(null);
    setResults(null);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/analyze`, {
        paragraph: paragraph.trim()
      });

      setResults(response.data);
    } catch (err) {
      console.error('Analysis error:', err);
      setError(err.response?.data?.error || 'Failed to analyze paragraph. Please try again.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleClear = () => {
    setParagraph('');
    setResults(null);
    setError(null);
  };

  const handleExampleLoad = () => {
    const exampleParagraph = "Writing is both an art and a craft that requires constant practice and refinement. The best writers understand that their first draft is rarely their final product. Through careful revision and thoughtful editing, a piece of writing can be transformed from a rough collection of ideas into a polished work that communicates clearly and effectively with its intended audience.";
    setParagraph(exampleParagraph);
  };

  return (
    <div className="App">
      <div className="container">
        <header className="header">
          <h1>Write Aid</h1>
          <p className="subtitle">Sentence-by-sentence writing analysis powered by FinChat</p>
        </header>

        <div className="main-content">
          <div className="input-section">
            <div className="textarea-container">
              <label htmlFor="paragraph-input" className="input-label">
                Enter your paragraph for analysis:
              </label>
              <textarea
                id="paragraph-input"
                value={paragraph}
                onChange={(e) => setParagraph(e.target.value)}
                placeholder="Paste or type your paragraph here. Each sentence will be analyzed individually for writing improvements..."
                className="paragraph-input"
                rows="6"
                disabled={isAnalyzing}
              />
              <div className="character-count">
                {paragraph.length} characters
              </div>
            </div>

            <div className="button-group">
              <button
                onClick={handleAnalyze}
                disabled={isAnalyzing || !paragraph.trim()}
                className="analyze-btn"
              >
                {isAnalyzing ? (
                  <>
                    <span className="spinner"></span>
                    Analyzing...
                  </>
                ) : (
                  'Analyze Writing'
                )}
              </button>
              
              <button
                onClick={handleExampleLoad}
                disabled={isAnalyzing}
                className="example-btn"
              >
                Load Example
              </button>
              
              <button
                onClick={handleClear}
                disabled={isAnalyzing}
                className="clear-btn"
              >
                Clear
              </button>
            </div>
          </div>

          {error && (
            <div className="error-message">
              <h3>Error</h3>
              <p>{error}</p>
            </div>
          )}

          {results && (
            <div className="results-section">
              <div className="results-header">
                <h2>Analysis Results</h2>
                <div className="results-summary">
                  <div className="summary-stats">
                    <div className="stat">
                      <span className="stat-number">{results.total_sentences}</span>
                      <span className="stat-label">Total Sentences</span>
                    </div>
                    <div className="stat">
                      <span className="stat-number">{results.successful_analyses}</span>
                      <span className="stat-label">Analyzed</span>
                    </div>
                    <div className="stat">
                      <span className="stat-number">{results.summary.processing_success_rate.toFixed(1)}%</span>
                      <span className="stat-label">Success Rate</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="original-paragraph">
                <h3>Original Paragraph</h3>
                <p className="paragraph-text">{results.original_paragraph}</p>
              </div>

              <div className="improved-paragraph-section">
                <h3>Progressively Improved Paragraph</h3>
                <div className="improved-paragraph">
                  {results.final_paragraph || results.original_paragraph}
                </div>
                <div className="improvement-note">
                  {results.summary?.paragraph_updated 
                    ? "✨ This paragraph was progressively updated - each improved sentence provided context for the next"
                    : results.sentence_results?.some(result => result.success && result.improved_sentence)
                    ? "✨ This paragraph combines the improved sentences from FinChat analysis"
                    : "📝 Original paragraph (no improvements available)"}
                </div>
              </div>

              <div className="sentence-results">
                <h3>Sentence-by-Sentence Analysis</h3>
                {results.sentence_results.map((result, index) => (
                  <div key={index} className={`sentence-result ${result.success ? 'success' : 'error'}`}>
                    <div className="sentence-header">
                      <span className="sentence-number">Sentence {result.sentence_index + 1}</span>
                      <span className={`status-badge ${result.success ? 'success' : 'error'}`}>
                        {result.success ? 'Analyzed' : 'Failed'}
                      </span>
                    </div>
                    
                    <div className="sentence-content">
                      <p className="sentence-text">"{result.sentence}"</p>
                      
                      {result.success ? (
                        <div className="analysis-content">
                          {result.session_url && (
                            <div className="session-link">
                              <a 
                                href={result.session_url} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                className="finchat-link"
                              >
                                View Detailed Analysis in FinChat →
                              </a>
                            </div>
                          )}
                          
                          {result.analysis && (
                            <div className="analysis-preview">
                              <h4>Analysis Preview</h4>
                              <pre className="analysis-text">
                                {JSON.stringify(result.analysis, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="error-content">
                          <p className="error-text">Error: {result.error}</p>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {results.session_urls && results.session_urls.length > 0 && (
                <div className="all-sessions">
                  <h3>All Analysis Sessions</h3>
                  <div className="session-links">
                    {results.session_urls.map((url, index) => (
                      <a
                        key={index}
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="session-link-item"
                      >
                        Session {index + 1} →
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
