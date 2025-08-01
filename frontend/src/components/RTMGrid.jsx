import React, { useState, useEffect } from 'react';
import RTMCard from './RTMCard';
import PositionCard from './PositionCard';

const RTMGrid = ({ category, rtmData, onDataUpdate }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const API_BASE_URL = process.env.NODE_ENV === 'production' 
    ? 'https://rtm-monitor-api-193967718024.us-central1.run.app'  // Replace with your Cloud Run URL
    : 'http://localhost:8080';

  const fetchRTMData = async () => {
    if (!category) return;
    
    setLoading(true);
    setError(null);
    
    try {
      // Use different endpoint for positions
      const endpoint = category === 'positions' 
        ? `${API_BASE_URL}/api/positions`
        : `${API_BASE_URL}/api/rtm/${category}`;
        
      const response = await fetch(endpoint);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const result = await response.json();
      const now = new Date().toISOString();
      
      // Update the persistent data
      onDataUpdate(category, result.data || [], now);
    } catch (err) {
      setError(`Failed to fetch ${category} data: ${err.message}`);
      console.error('Error fetching RTM data:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '4rem 0' }}>
        <div style={{ 
          width: '3rem', 
          height: '3rem', 
          border: '2px solid #e5e7eb', 
          borderTop: '2px solid #3b82f6', 
          borderRadius: '50%', 
          animation: 'spin 1s linear infinite',
          marginBottom: '1rem'
        }}></div>
        <p style={{ color: '#6b7280' }}>Loading {category} RTM data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '4rem 0' }}>
        <div style={{ 
          backgroundColor: '#fef2f2', 
          border: '1px solid #fecaca', 
          borderRadius: '0.5rem', 
          padding: '1.5rem', 
          maxWidth: '28rem', 
          textAlign: 'center' 
        }}>
          <div style={{ color: '#dc2626', fontSize: '2.25rem', marginBottom: '0.5rem' }}>⚠️</div>
          <h3 style={{ color: '#991b1b', fontWeight: '600', marginBottom: '0.5rem' }}>Connection Error</h3>
          <p style={{ color: '#dc2626', fontSize: '0.875rem', marginBottom: '1rem' }}>{error}</p>
          <button
            onClick={() => window.location.reload()}
            style={{
              backgroundColor: '#dc2626',
              color: 'white',
              padding: '0.5rem 1rem',
              borderRadius: '0.5rem',
              border: 'none',
              cursor: 'pointer'
            }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!rtmData.data.length && !loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '4rem 0' }}>
        <div style={{ color: '#9ca3af', fontSize: '2.25rem', marginBottom: '0.5rem' }}>📊</div>
        <p style={{ color: '#6b7280', marginBottom: '1rem' }}>Click Generate to load {category} RTM data</p>
        <button
          onClick={fetchRTMData}
          style={{
            backgroundColor: '#3b82f6',
            color: 'white',
            padding: '0.75rem 1.5rem',
            borderRadius: '0.5rem',
            border: 'none',
            cursor: 'pointer',
            fontSize: '1rem',
            fontWeight: '500'
          }}
        >
          Generate RTM Data
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Generate Button */}
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '2rem' }}>
        <button
          onClick={fetchRTMData}
          disabled={loading}
          style={{
            backgroundColor: loading ? '#9ca3af' : '#3b82f6',
            color: 'white',
            padding: '0.75rem 1.5rem',
            borderRadius: '0.5rem',
            border: 'none',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '1rem',
            fontWeight: '500',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem'
          }}
        >
          {loading ? '🔄 Generating...' : '🔄 Generate RTM Data'}
        </button>
      </div>

      {/* RTM Data Grid */}
      {rtmData.data.length > 0 && (
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: category === 'positions' 
            ? 'repeat(auto-fit, minmax(400px, 1fr))' 
            : 'repeat(auto-fit, minmax(350px, 1fr))', 
          gap: '1rem' 
        }}>
          {rtmData.data.map((item) => {
            if (category === 'positions') {
              return (
                <PositionCard
                  key={`${item.instrument}-${item.direction}`}
                  instrument={item.instrument}
                  direction={item.direction}
                  units={item.units}
                  unrealized_pnl={item.unrealized_pnl}
                  rtmValues={item.rtm_values}
                  error={item.error}
                />
              );
            } else {
              return (
                <RTMCard
                  key={item.instrument}
                  instrument={item.instrument}
                  rtmValues={item.rtm_values}
                  error={item.error}
                />
              );
            }
          })}
        </div>
      )}
    </div>
  );
};

export default RTMGrid;