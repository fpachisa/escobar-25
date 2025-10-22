import React, { useState, useEffect } from 'react';
import RTMCard from './RTMCard';
import PositionCard from './PositionCard';

const RTMGrid = ({ category, rtmData, onDataUpdate }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filterType, setFilterType] = useState('all'); // all|dc|inc|dec
  const [conditionFilter, setConditionFilter] = useState('all'); // all|trending_up|trending_down|ranging|change

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

  // Helpers to classify signals for sorting/highlighting (using H1 data)
  const detectDirectionChange = (rtmValues) => {
    if (!rtmValues || rtmValues.length < 6) return false;
    const sign = (v) => (v > 0 ? 1 : v < 0 ? -1 : 0);
    const signs = rtmValues.map(sign);
    const f4p = signs.slice(0, 4).filter(s => s > 0).length;
    const f4n = signs.slice(0, 4).filter(s => s < 0).length;
    const l2p = signs.slice(4).filter(s => s > 0).length;
    const l2n = signs.slice(4).filter(s => s < 0).length;
    if ((f4p >= 3 && l2n >= 1) || (f4n >= 3 && l2p >= 1)) return true;
    const f3p = signs.slice(0, 3).filter(s => s > 0).length;
    const f3n = signs.slice(0, 3).filter(s => s < 0).length;
    const l3p = signs.slice(3).filter(s => s > 0).length;
    const l3n = signs.slice(3).filter(s => s < 0).length;
    if ((f3p >= 2 && l3n >= 2) || (f3n >= 2 && l3p >= 2)) return true;
    return false;
  };

  const getLastThreeTrend = (rtmValues) => {
    if (!rtmValues || rtmValues.length < 3) return null;
    const a = rtmValues.slice(-3);
    if (a[0] < a[1] && a[1] < a[2]) return 'increasing';
    if (a[0] > a[1] && a[1] > a[2]) return 'decreasing';
    return null;
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
        <button onClick={fetchRTMData} className="btn primary">Generate RTM Data</button>
      </div>
    );
  }

  // Filter and prepare data
  const prepareFilteredData = () => {
    let source = rtmData?.data || [];

    // Apply RTM pattern filter (using H1 data)
    if (filterType !== 'all') {
      source = source.filter((item) => {
        const h1Vals = item.rtm_h1_20 || item.rtm_values || [];
        if (filterType === 'dc') return detectDirectionChange(h1Vals);
        const t = getLastThreeTrend(h1Vals);
        if (filterType === 'inc') return t === 'increasing';
        if (filterType === 'dec') return t === 'decreasing';
        return true;
      });
    }

    // Apply daily condition filter
    if (conditionFilter !== 'all') {
      source = source.filter((item) => {
        const condition = item.daily_condition || '';
        if (conditionFilter === 'trending_up') return condition === 'Trending Up';
        if (conditionFilter === 'trending_down') return condition === 'Trending Down';
        if (conditionFilter === 'ranging') return condition === 'Ranging';
        if (conditionFilter === 'change') return condition === 'Direction Change Imminent';
        return true;
      });
    }

    return source;
  };

  const filteredData = prepareFilteredData();
  const hasAnyData = filteredData.length > 0;

  const renderInstrumentCards = () => {
    return (
      <div className={`cards-grid ${category === 'positions' ? 'positions' : 'instruments'}`}>
        {filteredData.map((item) => {
          if (category === 'positions') {
            return (
              <PositionCard
                key={`${item.instrument}-${item.direction}`}
                instrument={item.instrument}
                direction={item.direction}
                units={item.units}
                unrealized_pnl={item.unrealized_pnl}
                rtmH1={item.rtm_h1_20 || item.rtm_values || []}
                rtmH4={item.rtm_h1_34 || []}
                rtmD1_20={item.rtm_d1_20 || []}
                rtmD1_34={item.rtm_d1_34 || []}
                dailyCondition={item.daily_condition}
                dailyReasoning={item.daily_reasoning}
                error={item.error}
              />
            );
          } else {
            return (
              <RTMCard
                key={item.instrument}
                instrument={item.instrument}
                rtmH1={item.rtm_h1_20 || item.rtm_values || []}
                rtmH4={item.rtm_h1_34 || []}
                rtmD1_20={item.rtm_d1_20 || []}
                rtmD1_34={item.rtm_d1_34 || []}
                dailyCondition={item.daily_condition}
                dailyReasoning={item.daily_reasoning}
                error={item.error}
              />
            );
          }
        })}
      </div>
    );
  };

  return (
    <div>
      {/* Toolbar */}
      <div className="toolbar">
        <div className="toolbar-row">
          <div className="toolbar-group">
            <label className="label">RTM Pattern</label>
            <select className="select" value={filterType} onChange={(e) => setFilterType(e.target.value)}>
              <option value="all">All</option>
              <option value="dc">Direction Change</option>
              <option value="inc">RTM Increasing</option>
              <option value="dec">RTM Decreasing</option>
            </select>
          </div>
          <div className="toolbar-group">
            <label className="label">Daily Condition</label>
            <select className="select" value={conditionFilter} onChange={(e) => setConditionFilter(e.target.value)}>
              <option value="all">All Conditions</option>
              <option value="trending_up">Trending Up</option>
              <option value="trending_down">Trending Down</option>
              <option value="ranging">Ranging</option>
              <option value="change">Direction Change Imminent</option>
            </select>
          </div>
          <div className="toolbar-actions">
            <button onClick={fetchRTMData} disabled={loading} className="btn primary">
              {loading ? 'Generating…' : 'Generate RTM Data'}
            </button>
          </div>
        </div>
      </div>

      {/* RTM Data Grid */}
      {hasAnyData && renderInstrumentCards()}
    </div>
  );
};

export default RTMGrid;
