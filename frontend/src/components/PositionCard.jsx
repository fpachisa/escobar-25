import React, { useState } from 'react';

const PositionCard = ({
  instrument,
  direction,
  units,
  unrealized_pnl,
  rtmH1,
  rtmH4,
  rtmD1_20,
  rtmD1_34,
  dailyCondition,
  dailyReasoning,
  error
}) => {
  const [showReasoning, setShowReasoning] = useState(false);
  const formatValue = (value) => {
    if (Math.abs(value) >= 1000) {
      return `${(value / 1000).toFixed(1)}k`;
    }
    return value.toString();
  };

  const getRTMValueClass = (value) => {
    if (value > 0) return 'rtm-positive';
    if (value < 0) return 'rtm-negative';
    return 'rtm-neutral';
  };

  // Get styling based on condition
  const getConditionStyle = () => {
    switch(dailyCondition) {
      case 'Trending Up':
        return {
          border: '2px solid var(--green-500)',
          boxShadow: 'var(--shadow-green)'
        };
      case 'Trending Down':
        return {
          border: '2px solid var(--red-500)',
          boxShadow: 'var(--shadow-red)'
        };
      case 'Direction Change Imminent':
        return {
          border: '2px solid var(--amber-500)',
          boxShadow: 'var(--shadow-amber)'
        };
      case 'Ranging':
        return {
          border: '2px solid #3b82f6',
          boxShadow: '0 6px 12px rgba(59, 130, 246, 0.18)'
        };
      default:
        return {};
    }
  };

  const getConditionBadgeClass = () => {
    switch(dailyCondition) {
      case 'Trending Up':
        return 'condition-badge-up';
      case 'Trending Down':
        return 'condition-badge-down';
      case 'Direction Change Imminent':
        return 'condition-badge-change';
      case 'Ranging':
        return 'condition-badge-ranging';
      default:
        return 'condition-badge-unavailable';
    }
  };

  const pnlColor = unrealized_pnl >= 0 ? 'var(--green-700)' : 'var(--red-700)';
  const pnlBgColor = unrealized_pnl >= 0 ? 'var(--green-50)' : 'var(--red-50)';
  const directionColor = direction === 'Long' ? 'var(--green-700)' : 'var(--red-700)';
  const directionBgColor = direction === 'Long' ? 'var(--green-50)' : 'var(--red-50)';


  return (
    <div
      className="rtm-card"
      style={getConditionStyle()}
    >
      {/* Header */}
      <div className="card-header">
        <div className="card-title">
          <h3>{instrument}</h3>
          {dailyCondition && (
            <span className={`condition-badge-inline ${getConditionBadgeClass()}`}>
              {dailyCondition}
            </span>
          )}
        </div>
      </div>

      {/* Trade Details */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
        <div>
          <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>Direction</div>
          <div style={{ 
            fontSize: '0.875rem', 
            fontWeight: '600',
            color: directionColor,
            backgroundColor: directionBgColor,
            padding: '0.25rem 0.5rem',
            borderRadius: '0.25rem',
            display: 'inline-block'
          }}>
            {direction}
          </div>
        </div>
        
        <div>
          <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>Units</div>
          <div style={{ fontSize: '0.875rem', fontWeight: '500' }}>
            {units.toLocaleString()}
          </div>
        </div>
        
        
        <div>
          <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>P&L</div>
          <div style={{ 
            fontSize: '0.875rem', 
            fontWeight: '600',
            color: pnlColor,
            backgroundColor: pnlBgColor,
            padding: '0.25rem 0.5rem',
            borderRadius: '0.25rem',
            display: 'inline-block'
          }}>
            {unrealized_pnl >= 0 ? '+' : ''}{unrealized_pnl.toFixed(2)}
          </div>
        </div>
      </div>
      
      {/* H1-20EMA Timeframe (Top) */}
      <div className="timeframe-section">
        <div className="timeframe-label">H1 - 20EMA</div>

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

      {/* H1-34EMA Timeframe */}
      <div className="timeframe-section">
        <div className="timeframe-label">H1 - 34EMA</div>

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

      {/* D1-20EMA Timeframe */}
      <div className="timeframe-section daily">
        <div className="timeframe-label">D1 - 20EMA</div>

        {/* D1-20EMA RTM chips */}
        <div className="chips chips-daily">
          {(rtmD1_20 || []).map((value, idx) => (
            <span
              key={`d1-20-${idx}`}
              className={`chip ${getRTMValueClass(value)}`}
              title={`D1-20EMA RTM ${20 - idx}: ${value}`}
            >
              {formatValue(value)}
            </span>
          ))}
        </div>
      </div>

      {/* D1-34EMA Timeframe */}
      <div className="timeframe-section daily">
        <div className="timeframe-label">D1 - 34EMA</div>

        {/* D1-34EMA RTM chips */}
        <div className="chips chips-daily">
          {(rtmD1_34 || []).map((value, idx) => (
            <span
              key={`d1-34-${idx}`}
              className={`chip ${getRTMValueClass(value)}`}
              title={`D1-34EMA RTM ${20 - idx}: ${value}`}
            >
              {formatValue(value)}
            </span>
          ))}
        </div>
      </div>

      {/* AI Reasoning Section */}
      {dailyReasoning && dailyCondition !== 'Analysis Unavailable' && dailyCondition !== 'Analysis Error' && (
        <div className="reasoning-section">
          <button
            className="reasoning-toggle"
            onClick={() => setShowReasoning(!showReasoning)}
          >
            {showReasoning ? '▼' : '▶'} AI Analysis
          </button>
          {showReasoning && (
            <div className="reasoning-content">
              {dailyReasoning}
            </div>
          )}
        </div>
      )}

      {/* Footer - Only show error if present */}
      {error && (
        <div style={{ fontSize: '0.75rem', color: '#ef4444', textAlign: 'center', marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid #e5e7eb' }}>
          {error}
        </div>
      )}
    </div>
  );
};

export default PositionCard;
