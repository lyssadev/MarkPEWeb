import React, { useState, useEffect } from 'react';
import './App.css';

interface SearchResult {
  Id: string;
  Title: { 'en-US': string };
  DisplayProperties: { creatorName: string };
  ContentType: string[];
  Tags: string[];
  source?: string;
}

interface DownloadStatus {
  [key: string]: 'idle' | 'downloading' | 'completed' | 'error';
}

function App() {
  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [noResultsError, setNoResultsError] = useState('');
  const [downloadStatus, setDownloadStatus] = useState<DownloadStatus>({});

  useEffect(() => {
    console.log(`
███╗   ███╗ █████╗ ██████╗ ██╗  ██╗ █████╗ ██████╗ ██╗
████╗ ████║██╔══██╗██╔══██╗██║ ██╔╝██╔══██╗██╔══██╗██║
██╔████╔██║███████║██████╔╝█████╔╝ ███████║██████╔╝██║
██║╚██╔╝██║██╔══██║██╔══██╗██╔═██╗ ██╔══██║██╔═══╝ ██║
██║ ╚═╝ ██║██║  ██║██║  ██║██║  ██╗██║  ██║██║     ██║
╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝

MarkAPI v1.0 - Online and Detected
Minecraft Marketplace Content Platform
`);
  }, []);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setLoading(true);
    setError('');
    setNoResultsError('');
    setResults([]);

    try {
      // Use local search endpoint to bypass PlayFab rate limits
      const apiUrl = process.env.NODE_ENV === 'production'
        ? '/api/search'
        : 'http://localhost:8000/api/search';

      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer markpe_api_key_2024'
        },
        body: JSON.stringify({
          query: searchQuery,
          search_type: 'name',
          limit: 50
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.success) {
        const searchResults = data.data || [];
        setResults(searchResults);

        // Show no results error if empty
        if (searchResults.length === 0) {
          setNoResultsError(`No results found for "${searchQuery}". Please try a different search term.`);
          setTimeout(() => {
            setNoResultsError('');
          }, 3000);
        }

        if (data.source && data.source.includes('local')) {
          // Show a subtle indicator that we're using local data
          console.log('Using local data source for faster results');
        }
      } else {
        setError('Search failed. Please try again.');
      }
    } catch (err) {
      console.error('Search error:', err);
      setError('Failed to search. Please check your connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const handleDownload = async (itemId: string, title: string) => {
    setDownloadStatus(prev => ({ ...prev, [itemId]: 'downloading' }));

    try {
      const apiUrl = process.env.NODE_ENV === 'production'
        ? '/api/download'
        : 'http://localhost:8000/api/download';

      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer markpe_api_key_2024'
        },
        body: JSON.stringify({
          item_id: itemId
        })
      });

      if (!response.ok) {
        throw new Error(`Download failed: ${response.status}`);
      }

      // Get the filename from response headers or use a default
      const contentDisposition = response.headers.get('content-disposition');
      let filename = `${title.replace(/[^a-z0-9]/gi, '_')}.zip`;

      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="(.+)"/);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      }

      // Create blob and download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setDownloadStatus(prev => ({ ...prev, [itemId]: 'completed' }));

      // Reset status after 3 seconds
      setTimeout(() => {
        setDownloadStatus(prev => ({ ...prev, [itemId]: 'idle' }));
      }, 3000);

    } catch (err) {
      console.error('Download error:', err);
      setDownloadStatus(prev => ({ ...prev, [itemId]: 'error' }));

      // Reset status after 3 seconds
      setTimeout(() => {
        setDownloadStatus(prev => ({ ...prev, [itemId]: 'idle' }));
      }, 3000);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <div className="title">
          <pre>{`
███╗   ███╗ █████╗ ██████╗ ██╗  ██╗██████╗ ███████╗
████╗ ████║██╔══██╗██╔══██╗██║ ██╔╝██╔══██╗██╔════╝
██╔████╔██║███████║██████╔╝█████╔╝ ██████╔╝█████╗
██║╚██╔╝██║██╔══██║██╔══██╗██╔═██╗ ██╔═══╝ ██╔══╝
██║ ╚═╝ ██║██║  ██║██║  ██║██║  ██╗██║     ███████╗
╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚══════╝ 1.0
          `}</pre>
        </div>
        <div className="search-container">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter NAME, UUID or URL"
            className="search-input"
            disabled={loading}
          />

          <button
            onClick={handleSearch}
            className="search-button"
            disabled={loading || !searchQuery.trim()}
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>

        {error && <div className="error-message">{error}</div>}
        {noResultsError && <div className="no-results-error">{noResultsError}</div>}

        {results.length > 0 && (
          <div className="results-container">
            <h3>Search Results ({results.length})</h3>
            <div className="results-list">
              {results.map((result, index) => {
                const status = downloadStatus[result.Id] || 'idle';
                return (
                  <div key={result.Id} className="result-item">
                    <div className="result-number">{index + 1}</div>
                    <div className="result-content">
                      <div className="result-title">
                        {typeof result.Title === 'string' ? result.Title :
                         result.Title?.['en-US'] || 'Unknown Title'}
                      </div>
                      <div className="result-creator">
                        by {result.DisplayProperties?.creatorName || 'Unknown Creator'}
                      </div>
                      <div className="result-id">ID: {result.Id}</div>
                      {result.Tags && result.Tags.length > 0 && (
                        <div className="result-tags">
                          {result.Tags.slice(0, 5).map((tag, tagIndex) => (
                            <span key={tagIndex} className="tag">{tag}</span>
                          ))}
                          {result.Tags.length > 5 && <span className="tag">+{result.Tags.length - 5} more</span>}
                        </div>
                      )}
                    </div>
                    <div className="result-actions">
                      <button
                        className={`download-button ${status}`}
                        onClick={() => handleDownload(result.Id,
                          typeof result.Title === 'string' ? result.Title :
                          result.Title?.['en-US'] || 'Unknown Title')}
                        disabled={status === 'downloading'}
                      >
                        {status === 'downloading' && <span className="spinner"></span>}
                        {status === 'completed' && '✓'}
                        {status === 'error' && '✗'}
                        {status === 'idle' && '⬇'}
                        <span className="download-text">
                          {status === 'downloading' ? 'Downloading...' :
                           status === 'completed' ? 'Downloaded' :
                           status === 'error' ? 'Failed' : 'Download'}
                        </span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <footer className="app-footer">
          <div className="footer-content">
            <p className="footer-text">
              Thanks to <span className="highlight">Bluecoin Community</span> for the Open Source code & <span className="highlight">Lisa</span> for creating this website <span className="heart">❤️</span>
            </p>
          </div>
        </footer>
      </header>
    </div>
  );
}

export default App;
