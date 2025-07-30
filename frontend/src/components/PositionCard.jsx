import React from 'react';

const PositionCard = ({ 
  instrument, 
  direction, 
  units,
  unrealized_pnl,
  rtmValues, 
  error 
}) => {
  const formatValue = (value) => {
    if (Math.abs(value) >= 1000) {
      return `${(value / 1000).toFixed(1)}k`;
    }
    return value.toString();
  };

  const detectDirectionChange = (rtmValues) => {
    if (rtmValues.length < 6) return false;
    
    const getSign = (value) => value > 0 ? 1 : value < 0 ? -1 : 0;
    const signs = rtmValues.map(getSign);
    
    // Check pattern 1: First 4 vs Last 2
    const first4Positive = signs.slice(0, 4).filter(s => s > 0).length;
    const first4Negative = signs.slice(0, 4).filter(s => s < 0).length;
    const last2Positive = signs.slice(4).filter(s => s > 0).length;
    const last2Negative = signs.slice(4).filter(s => s < 0).length;
    
    // Pattern 1: Need at least 3 out of 4 same sign, then at least 1 out of 2 opposite sign
    if ((first4Positive >= 3 && last2Negative >= 1) || (first4Negative >= 3 && last2Positive >= 1)) {
      return true;
    }
    
    // Check pattern 2: First 3 vs Last 3
    const first3Positive = signs.slice(0, 3).filter(s => s > 0).length;
    const first3Negative = signs.slice(0, 3).filter(s => s < 0).length;
    const last3Positive = signs.slice(3).filter(s => s > 0).length;
    const last3Negative = signs.slice(3).filter(s => s < 0).length;
    
    // Pattern 2: Need at least 2 out of 3 same sign, then at least 2 out of 3 opposite sign
    if ((first3Positive >= 2 && last3Negative >= 2) || (first3Negative >= 2 && last3Positive >= 2)) {
      return true;
    }
    
    return false;
  };

  const hasDirectionChange = detectDirectionChange(rtmValues);
  const pnlColor = unrealized_pnl >= 0 ? '#166534' : '#991b1b';
  const pnlBgColor = unrealized_pnl >= 0 ? '#dcfce7' : '#fef2f2';
  const directionColor = direction === 'Long' ? '#166534' : '#991b1b';
  const directionBgColor = direction === 'Long' ? '#dcfce7' : '#fef2f2';

  return (
    <div 
      className="rtm-card" 
      style={{ 
        ...(hasDirectionChange && {
          border: '2px solid #f59e0b',
          boxShadow: '0 4px 6px -1px rgba(245, 158, 11, 0.2)'
        })
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <h3 style={{ fontWeight: '600', fontSize: '1.125rem', color: '#1f2937' }}>{instrument}</h3>
          {hasDirectionChange && (
            <span style={{ 
              fontSize: '0.75rem', 
              color: '#f59e0b', 
              backgroundColor: '#fef3c7', 
              padding: '0.25rem 0.5rem', 
              borderRadius: '0.25rem',
              fontWeight: '600'
            }}>
              🔄 Direction Change
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
      
      {/* RTM Table */}
      <div style={{ overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
          <thead>
            <tr style={{ backgroundColor: '#f8fafc' }}>
              <th style={{ padding: '0.5rem', textAlign: 'center', fontWeight: '600', color: '#374151', border: '1px solid #e5e7eb' }}>RTM-6</th>
              <th style={{ padding: '0.5rem', textAlign: 'center', fontWeight: '600', color: '#374151', border: '1px solid #e5e7eb' }}>RTM-5</th>
              <th style={{ padding: '0.5rem', textAlign: 'center', fontWeight: '600', color: '#374151', border: '1px solid #e5e7eb' }}>RTM-4</th>
              <th style={{ padding: '0.5rem', textAlign: 'center', fontWeight: '600', color: '#374151', border: '1px solid #e5e7eb' }}>RTM-3</th>
              <th style={{ padding: '0.5rem', textAlign: 'center', fontWeight: '600', color: '#374151', border: '1px solid #e5e7eb' }}>RTM-2</th>
              <th style={{ padding: '0.5rem', textAlign: 'center', fontWeight: '600', color: '#374151', border: '1px solid #e5e7eb' }}>RTM-1</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              {rtmValues.map((value, index) => (
                <td
                  key={index}
                  style={{
                    padding: '0.75rem 0.5rem',
                    textAlign: 'center',
                    fontWeight: '500',
                    border: '1px solid #e5e7eb',
                    backgroundColor: value > 0 ? '#dcfce7' : value < 0 ? '#fef2f2' : '#f3f4f6',
                    color: value > 0 ? '#166534' : value < 0 ? '#991b1b' : '#374151'
                  }}
                  title={`RTM ${6-index}: ${value}`}
                >
                  {formatValue(value)}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
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