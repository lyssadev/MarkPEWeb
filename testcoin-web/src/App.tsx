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

interface DownloadItem {
  id: string;
  title: string;
  status: 'pending' | 'downloading' | 'completed' | 'error';
  progress: number;
  totalSize: number;
  downloadedSize: number;
  speed: number;
  startTime: number;
  serverStatus?: string; // For showing server-side download status
  contentTypes?: string; // Content types (e.g., "Skin Pack + Resource Pack")
  hasMultipleTypes?: boolean; // Whether this contains multiple content types
  totalFiles?: string; // Number of files in the package
}

interface Notification {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

// API Configuration
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [noResultsError, setNoResultsError] = useState('');
  const [downloads, setDownloads] = useState<DownloadItem[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isDownloadPanelOpen, setIsDownloadPanelOpen] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);

  useEffect(() => {
    console.log(`
███╗   ███╗ █████╗ ██████╗ ██╗  ██╗ █████╗ ██████╗ ██╗
████╗ ████║██╔══██╗██╔══██╗██║ ██╔╝██╔══██╗██╔══██╗██║
██╔████╔██║███████║██████╔╝█████╔╝ ███████║██████╔╝██║
██║╚██╔╝██║██╔══██║██╔══██╗██╔═██╗ ██╔══██║██╔═══╝ ██║
██║ ╚═╝ ██║██║  ██║██║  ██║██║  ██╗██║  ██║██║     ██║
╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝

MarkAPI v1.1 - Online and Detected
Minecraft Marketplace Content Platform
`);

    // Handle initial load animation timing
    const timer = setTimeout(() => {
      setIsInitialLoad(false);
    }, 3000); // Animation completes after 3 seconds

    return () => clearTimeout(timer);
  }, []);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setLoading(true);
    setError('');
    setNoResultsError('');
    setResults([]);

    try {
      // Use Testcoin FastAPI server endpoint
      const apiUrl = `${API_BASE_URL}/api/search`;

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

  // Helper functions for downloads and notifications
  const addNotification = (message: string, type: 'success' | 'error' | 'info') => {
    const id = Date.now().toString();
    const notification: Notification = { id, message, type };
    setNotifications(prev => [...prev, notification]);

    // Auto remove after 5 seconds
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id));
    }, 5000);
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatSpeed = (bytesPerSecond: number): string => {
    return formatBytes(bytesPerSecond) + '/s';
  };

  const handleDownload = async (itemId: string, title: string) => {
    // Add notification
    addNotification(`Starting download: ${title}`, 'info');

    // Create download item with pending status
    const downloadItem: DownloadItem = {
      id: itemId,
      title,
      status: 'pending',
      progress: 0,
      totalSize: 0,
      downloadedSize: 0,
      speed: 0,
      startTime: Date.now(),
      serverStatus: 'Server fetching content...'
    };

    setDownloads(prev => [...prev.filter(d => d.id !== itemId), downloadItem]);

    // Set a timeout to update server status if it takes too long
    const serverStatusTimeout = setTimeout(() => {
      setDownloads(prev => prev.map(d =>
        d.id === itemId && d.status === 'pending' ? {
          ...d,
          serverStatus: 'Server processing... This may take a moment.'
        } : d
      ));
    }, 3000); // Show after 3 seconds

    try {
      const apiUrl = `${API_BASE_URL}/api/download`;

      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer markpe_api_key_2024'
        },
        body: JSON.stringify({
          item_id: itemId,
          process_content: true  // Enable processing like coin.py
        })
      });

      if (!response.ok) {
        throw new Error(`Download failed: ${response.status}`);
      }

      const contentLength = response.headers.get('content-length');
      const totalSize = contentLength ? parseInt(contentLength, 10) : 0;

      // Get content type information from headers
      const contentTypes = response.headers.get('x-content-types') || 'Content Pack';
      const hasMultipleTypes = response.headers.get('x-has-multiple-types') === 'true';
      const totalFiles = response.headers.get('x-total-files') || '1';
      const isProcessed = response.headers.get('x-processed') === 'true';

      // Clear the server status timeout since we got a response
      clearTimeout(serverStatusTimeout);

      // Update download item with total size, content info, and change status to downloading
      setDownloads(prev => prev.map(d =>
        d.id === itemId ? {
          ...d,
          totalSize,
          contentTypes: isProcessed ? `${contentTypes} (Processed)` : contentTypes,
          hasMultipleTypes,
          totalFiles,
          status: 'downloading',
          serverStatus: undefined // Clear server status when actual download starts
        } : d
      ));

      // Get the filename from response headers or use a default
      const contentDisposition = response.headers.get('content-disposition');
      let filename = `${title.replace(/[^a-z0-9]/gi, '_')}.zip`;

      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="(.+)"/);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      }

      // Read the response with progress tracking
      const reader = response.body?.getReader();
      const chunks: Uint8Array[] = [];
      let downloadedSize = 0;
      const startTime = Date.now();

      if (!reader) {
        throw new Error('Response body is not readable');
      }

      console.log('Starting to read response stream...');

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          console.log(`Stream reading completed. Total chunks: ${chunks.length}, Total size: ${downloadedSize} bytes`);
          break;
        }

        if (!value || value.length === 0) {
          console.warn('Received empty chunk, skipping...');
          continue;
        }

        chunks.push(value);
        downloadedSize += value.length;

        const currentTime = Date.now();
        const elapsedTime = (currentTime - startTime) / 1000; // seconds
        const speed = elapsedTime > 0 ? downloadedSize / elapsedTime : 0;
        const progress = totalSize > 0 ? (downloadedSize / totalSize) * 100 : 0;

        // Update download progress - capture values to avoid closure issues
        const currentDownloadedSize = downloadedSize;
        const currentProgress = Math.min(progress, 100);
        const currentSpeed = speed;

        // Log progress every 1MB or so
        if (downloadedSize % (1024 * 1024) < value.length) {
          console.log(`Download progress: ${formatBytes(downloadedSize)} at ${formatSpeed(speed)}`);
        }

        setDownloads(prev => prev.map(d =>
          d.id === itemId ? {
            ...d,
            downloadedSize: currentDownloadedSize,
            progress: currentProgress,
            speed: currentSpeed
          } : d
        ));
      }

      // Create blob and download
      console.log(`Creating blob from ${chunks.length} chunks, total size: ${downloadedSize} bytes`);
      const blob = new Blob(chunks, { type: 'application/zip' });
      console.log(`Blob created with size: ${blob.size} bytes`);

      if (blob.size === 0) {
        throw new Error('Downloaded file is empty - no data received from server');
      }

      // Check if browser supports downloads
      if (!window.URL || !window.URL.createObjectURL) {
        throw new Error('Browser does not support file downloads');
      }

      // Log security context info
      console.log(`Download context - HTTPS: ${window.location.protocol === 'https:'}, Secure Context: ${window.isSecureContext}`);

      // Warn if not in secure context (some browsers may block downloads)
      if (!window.isSecureContext && window.location.hostname !== 'localhost') {
        console.warn('Not in secure context - downloads may be blocked by browser');
      }

      // Try multiple download methods for better compatibility
      try {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.style.display = 'none';
        document.body.appendChild(a);

        console.log(`Triggering download for file: ${filename}`);
        a.click();

        // Notify user that download is being saved
        addNotification(`Saving ${filename} to device...`, 'info');

        // Clean up after a short delay
        setTimeout(() => {
          window.URL.revokeObjectURL(url);
          if (document.body.contains(a)) {
            document.body.removeChild(a);
          }
        }, 1000);

      } catch (downloadError) {
        console.error('Primary download method failed:', downloadError);

        // Fallback: try using a different approach
        try {
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.setAttribute('download', filename);
          link.style.display = 'none';

          // Try using mouse event
          const event = new MouseEvent('click', {
            view: window,
            bubbles: true,
            cancelable: true
          });

          document.body.appendChild(link);
          link.dispatchEvent(event);

          setTimeout(() => {
            URL.revokeObjectURL(url);
            if (document.body.contains(link)) {
              document.body.removeChild(link);
            }
          }, 1000);

        } catch (fallbackError) {
          console.error('Fallback download method also failed:', fallbackError);
          throw new Error('Unable to save file to device. Please check browser permissions.');
        }
      }

      // Mark as completed
      setDownloads(prev => prev.map(d =>
        d.id === itemId ? { ...d, status: 'completed', progress: 100 } : d
      ));

      addNotification(`Download completed: ${title}`, 'success');

      // Remove from downloads after 10 seconds
      setTimeout(() => {
        setDownloads(prev => prev.filter(d => d.id !== itemId));
      }, 10000);

    } catch (err) {
      console.error('Download error:', err);

      // Clear the server status timeout on error
      clearTimeout(serverStatusTimeout);

      // Mark as error
      setDownloads(prev => prev.map(d =>
        d.id === itemId ? { ...d, status: 'error' } : d
      ));

      addNotification(`Download failed: ${title}`, 'error');

      // Remove from downloads after 5 seconds
      setTimeout(() => {
        setDownloads(prev => prev.filter(d => d.id !== itemId));
      }, 5000);
    }
  };

  return (
    <div className={`App ${isInitialLoad ? 'initial-load' : ''}`}>
      {/* Notifications */}
      <div className="notifications-container">
        {notifications.map((notification) => (
          <div key={notification.id} className={`notification notification-${notification.type}`}>
            <div className="notification-content">
              {notification.message}
            </div>
          </div>
        ))}
      </div>

      {/* Downloads Panel */}
      <div className={`downloads-panel ${isDownloadPanelOpen ? 'open' : ''}`}>
        <div className="downloads-header">
          <h3>Downloads</h3>
          <button
            className="close-panel-btn"
            onClick={() => setIsDownloadPanelOpen(false)}
          >
            ✕
          </button>
        </div>
        <div className="downloads-content">
          {downloads.length === 0 ? (
            <div className="no-downloads">No active downloads</div>
          ) : (
            downloads.map((download) => (
              <div key={download.id} className={`download-item ${download.status}`}>
                <div className="download-info">
                  <div className="download-title">{download.title}</div>
                  {download.contentTypes && (
                    <div className="download-content-type">
                      {download.contentTypes}
                      {download.hasMultipleTypes && download.totalFiles && (
                        <span className="file-count"> ({download.totalFiles} files)</span>
                      )}
                    </div>
                  )}
                  <div className="download-progress">
                    <div className="progress-bar">
                      <div
                        className="progress-fill"
                        style={{ width: `${download.progress}%` }}
                      ></div>
                    </div>
                    <div className="progress-text">
                      {download.status === 'pending' ? 'Pending...' :
                       download.totalSize > 0 ? `${download.progress.toFixed(1)}%` :
                       download.downloadedSize > 0 ? 'Downloading...' : '0%'}
                    </div>
                  </div>
                  <div className="download-stats">
                    {download.status === 'pending' ? (
                      <span className="server-status">
                        {download.serverStatus || 'Preparing download...'}
                      </span>
                    ) : (
                      <>
                        <span className="download-size">
                          {download.totalSize > 0 ?
                            `${formatBytes(download.downloadedSize)} / ${formatBytes(download.totalSize)}` :
                            download.downloadedSize > 0 ?
                              `${formatBytes(download.downloadedSize)} downloaded` :
                              'Preparing...'
                          }
                        </span>
                        {download.status === 'downloading' && download.speed > 0 && (
                          <span className="download-speed">
                            {formatSpeed(download.speed)}
                          </span>
                        )}
                      </>
                    )}
                  </div>
                </div>
                <div className="download-status">
                  {(download.status === 'pending' || download.status === 'downloading') && <div className="spinner-small"></div>}
                  {download.status === 'completed' && <span className="status-icon">✓</span>}
                  {download.status === 'error' && <span className="status-icon error">✗</span>}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <header className="App-header">
        {/* Downloads Icon */}
        <div className="downloads-icon-container">
          <button
            className="downloads-icon"
            onClick={() => setIsDownloadPanelOpen(!isDownloadPanelOpen)}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
            </svg>
            {downloads.length > 0 && (
              <span className="download-count">{downloads.length}</span>
            )}
          </button>
        </div>

        <div className="title">
          <pre>{`
███╗   ███╗ █████╗ ██████╗ ██╗  ██╗ █████╗ ██████╗ ██╗
████╗ ████║██╔══██╗██╔══██╗██║ ██╔╝██╔══██╗██╔══██╗██║
██╔████╔██║███████║██████╔╝█████╔╝ ███████║██████╔╝██║
██║╚██╔╝██║██╔══██║██╔══██╗██╔═██╗ ██╔══██║██╔═══╝ ██║
██║ ╚═╝ ██║██║  ██║██║  ██║██║  ██╗██║  ██║██║     ██║
╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝

                    MarkPE v1.1
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
                const downloadItem = downloads.find(d => d.id === result.Id);
                const isPending = downloadItem?.status === 'pending';
                const isDownloading = downloadItem?.status === 'downloading';
                const isCompleted = downloadItem?.status === 'completed';
                const isError = downloadItem?.status === 'error';
                const isActive = isPending || isDownloading;

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
                        className={`download-button ${isPending ? 'pending' : isDownloading ? 'downloading' : isCompleted ? 'completed' : isError ? 'error' : 'idle'}`}
                        onClick={() => handleDownload(result.Id,
                          typeof result.Title === 'string' ? result.Title :
                          result.Title?.['en-US'] || 'Unknown Title')}
                        disabled={isActive}
                      >
                        {(isPending || isDownloading) && <span className="spinner"></span>}
                        {isCompleted && '✓'}
                        {isError && '✗'}
                        {!isPending && !isDownloading && !isCompleted && !isError && '⬇'}
                        <span className="download-text">
                          {isPending ? 'Preparing...' :
                           isDownloading ? 'Downloading...' :
                           isCompleted ? 'Downloaded' :
                           isError ? 'Failed' : 'Download'}
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
