import React from 'react';
import Sparkline from './Sparkline';

const PositionCard = ({ 
  instrument, 
  direction, 
  units,
  unrealized_pnl,
  rtmH1, 
  rtmH4,
  error,
  bias 
}) => {
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

  // Check if bias and RTM trend are aligned for highlighting (using H1 data)
  const getLastThreeTrend = (values) => {
    if (!values || values.length < 3) return null;
    const lastThree = values.slice(-3);
    if (lastThree[0] < lastThree[1] && lastThree[1] < lastThree[2]) return 'increasing';
    if (lastThree[0] > lastThree[1] && lastThree[1] > lastThree[2]) return 'decreasing';
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
  const pnlColor = unrealized_pnl >= 0 ? 'var(--green-700)' : 'var(--red-700)';
  const pnlBgColor = unrealized_pnl >= 0 ? 'var(--green-50)' : 'var(--red-50)';
  const directionColor = direction === 'Long' ? 'var(--green-700)' : 'var(--red-700)';
  const directionBgColor = direction === 'Long' ? 'var(--green-50)' : 'var(--red-50)';


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
        <div style={{ fontSize: '0.75rem', color: '#ef4444', textAlign: 'center', marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid #e5e7eb' }}>
          {error}
        </div>
      )}
    </div>
  );
};

export default PositionCard;
