import React from 'react';
import Sparkline from './Sparkline';

const RTMCard = ({ instrument, rtmH1, rtmH4, error, bias }) => {
  const getRTMValueClass = (value) => {
    if (value > 0) return 'rtm-positive';
    if (value < 0) return 'rtm-negative';
    return 'rtm-neutral';
  };

  const formatValue = (value) => {
    if (Math.abs(value) >= 1000) {
      return `${(value / 1000).toFixed(1)}k`;
    }
    return value.toString();
  };

  // Check if bias and RTM trend are aligned for highlighting (using H1 data)
  const getLastThreeTrend = (values) => {
    if (!values || values.length < 3) return null;
    
    const lastThree = values.slice(-3);
    
    // Check if strictly increasing
    if (lastThree[0] < lastThree[1] && lastThree[1] < lastThree[2]) {
      return 'increasing';
    }
    
    // Check if strictly decreasing
    if (lastThree[0] > lastThree[1] && lastThree[1] > lastThree[2]) {
      return 'decreasing';
    }
    
    return null;
  };

  const h1Trend = getLastThreeTrend(rtmH1);
  
  // Highlight based on H1 data alignment with bias
  const shouldHighlight = () => {
    if (!bias || !h1Trend) return false;
    return (bias === 'Up' && h1Trend === 'increasing') || 
           (bias === 'Down' && h1Trend === 'decreasing');
  };

  const isHighlighted = shouldHighlight();


  return (
    <div 
      className="rtm-card" 
      style={{
        ...(isHighlighted && bias === 'Up' && {
          border: '2px solid var(--green-500)',
          boxShadow: 'var(--shadow-green)'
        }),
        ...(isHighlighted && bias === 'Down' && {
          border: '2px solid var(--red-500)',
          boxShadow: 'var(--shadow-red)'
        })
      }}
    >
      {/* Header */}
      <div className="card-header">
        <div className="card-title">
          <h3>{instrument}</h3>
        </div>
        {error && (
          <span className="badge badge-red">Error</span>
        )}
      </div>

      {/* H1-20EMA Timeframe (Top) */}
      <div className="timeframe-section">
        <div className="timeframe-label">H1 - 20EMA</div>
        
        {/* H1-20EMA Sparkline */}
        <div className="sparkline">
          <Sparkline values={rtmH1 || []} />
        </div>

        {/* H1-20EMA RTM chips */}
        <div className="chips">
          {(rtmH1 || []).map((value, idx) => (
            <span
              key={`h1-20-${idx}`}
              className={`chip ${getRTMValueClass(value)}`}
              title={`H1-20EMA RTM ${6 - idx}: ${value}`}
            >
              {formatValue(value)}
            </span>
          ))}
        </div>
      </div>

      {/* H1-34EMA Timeframe (Bottom) */}
      <div className="timeframe-section">
        <div className="timeframe-label">H1 - 34EMA</div>
        
        {/* H1-34EMA Sparkline */}
        <div className="sparkline">
          <Sparkline values={rtmH4 || []} />
        </div>

        {/* H1-34EMA RTM chips */}
        <div className="chips">
          {(rtmH4 || []).map((value, idx) => (
            <span
              key={`h1-34-${idx}`}
              className={`chip ${getRTMValueClass(value)}`}
              title={`H1-34EMA RTM ${6 - idx}: ${value}`}
            >
              {formatValue(value)}
            </span>
          ))}
        </div>
      </div>

      {/* Footer - Only show error if present */}
      {error && (
        <div className="error-text">{error}</div>
      )}
    </div>
  );
};

export default RTMCard;
