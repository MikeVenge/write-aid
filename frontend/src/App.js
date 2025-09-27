import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

// API configuration - Updated to use Railway backend
const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? 'https://write-aid-production.up.railway.app' 
  : 'http://localhost:5001';

function App() {
  const [paragraph, setParagraph] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [processingDirection, setProcessingDirection] = useState('first-to-last');
  const [reprocessingRounds, setReprocessingRounds] = useState(0);

  const handleAnalyze = async () => {
    if (!paragraph.trim()) {
      setError('Please enter a paragraph to analyze');
      return;
    }

    setIsAnalyzing(true);
    setError(null);
    setResults(null);

    try {
      // Start async analysis
      const startResponse = await axios.post(`${API_BASE_URL}/api/analyze-async`, {
        paragraph: paragraph.trim(),
        processing_direction: processingDirection,
        reprocessing_rounds: reprocessingRounds
      }, {
        timeout: 30000, // 30 second timeout for starting the job
        headers: {
          'Content-Type': 'application/json'
        }
      });

      const jobId = startResponse.data.job_id;
      console.log(`🚀 Analysis started with job ID: ${jobId}`);
      console.log('⏳ Polling for results - this may take several minutes for long paragraphs...');

      // Poll for results
      const pollForResults = async () => {
        while (true) {
          try {
            const statusResponse = await axios.get(`${API_BASE_URL}/api/job/${jobId}`, {
              timeout: 10000 // 10 second timeout for status checks
            });

            const jobData = statusResponse.data;
            
            if (jobData.status === 'completed') {
              console.log('✅ Analysis completed successfully!');
              setResults(jobData.result);
              break;
            } else if (jobData.status === 'failed') {
              setError(jobData.error || 'Analysis failed');
              break;
            } else {
              // Still processing, wait and poll again
              console.log(`⏳ Status: ${jobData.status} - ${jobData.progress || 'Processing...'}`);
              await new Promise(resolve => setTimeout(resolve, 5000)); // Wait 5 seconds
            }
          } catch (pollErr) {
            console.error('Polling error:', pollErr);
            setError('Failed to get analysis results. Please try again.');
            break;
          }
        }
      };

      await pollForResults();
      
    } catch (err) {
      console.error('Analysis error:', err);
      setError(err.response?.data?.error || 'Failed to start analysis. Please try again.');
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

            <div className="processing-direction-section">
              <label htmlFor="processing-direction" className="input-label">
                Processing Direction:
              </label>
              <div className="direction-toggle">
                <label className={`radio-option ${processingDirection === 'first-to-last' ? 'selected' : ''} ${isAnalyzing ? 'disabled' : ''}`}>
                  <input
                    type="radio"
                    name="processing-direction"
                    value="first-to-last"
                    checked={processingDirection === 'first-to-last'}
                    onChange={(e) => setProcessingDirection(e.target.value)}
                    disabled={isAnalyzing}
                  />
                  <span className="radio-label">First to Last Sentence</span>
                  <span className="radio-description">Process from the beginning to the end</span>
                </label>
                <label className={`radio-option ${processingDirection === 'last-to-first' ? 'selected' : ''} ${isAnalyzing ? 'disabled' : ''}`}>
                  <input
                    type="radio"
                    name="processing-direction"
                    value="last-to-first"
                    checked={processingDirection === 'last-to-first'}
                    onChange={(e) => setProcessingDirection(e.target.value)}
                    disabled={isAnalyzing}
                  />
                  <span className="radio-label">Last to First Sentence</span>
                  <span className="radio-description">Process from the end to the beginning</span>
                </label>
              </div>
            </div>

            <div className="reprocessing-rounds-section">
              <label htmlFor="reprocessing-rounds" className="input-label">
                Reprocessing Rounds:
              </label>
              <div className="rounds-selector">
                <label className={`round-option ${reprocessingRounds === 0 ? 'selected' : ''} ${isAnalyzing ? 'disabled' : ''}`}>
                  <input
                    type="radio"
                    name="reprocessing-rounds"
                    value="0"
                    checked={reprocessingRounds === 0}
                    onChange={(e) => setReprocessingRounds(parseInt(e.target.value))}
                    disabled={isAnalyzing}
                  />
                  <span className="round-label">0 Rounds</span>
                  <span className="round-description">Process once only (default)</span>
                </label>
                <label className={`round-option ${reprocessingRounds === 1 ? 'selected' : ''} ${isAnalyzing ? 'disabled' : ''}`}>
                  <input
                    type="radio"
                    name="reprocessing-rounds"
                    value="1"
                    checked={reprocessingRounds === 1}
                    onChange={(e) => setReprocessingRounds(parseInt(e.target.value))}
                    disabled={isAnalyzing}
                  />
                  <span className="round-label">1 Round</span>
                  <span className="round-description">Reprocess the improved paragraph once more</span>
                </label>
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
                {results.sentence_results && results.sentence_results.length > 0 ? (
                  results.sentence_results.map((result, index) => (
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
                  ))
                ) : (
                  <div className="no-results">
                    <p>No sentence analysis results available.</p>
                  </div>
                )}
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
