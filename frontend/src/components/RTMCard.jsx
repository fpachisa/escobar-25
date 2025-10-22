import React, { useState } from 'react';

const RTMCard = ({ instrument, rtmH1, rtmH4, rtmD1_20, rtmD1_34, dailyCondition, dailyReasoning, error }) => {
  const [showReasoning, setShowReasoning] = useState(false);

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
        {error && (
          <span className="badge badge-red">Error</span>
        )}
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
        <div className="error-text">{error}</div>
      )}
    </div>
  );
};

export default RTMCard;
