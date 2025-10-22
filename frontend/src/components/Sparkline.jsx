import React from 'react';

const Sparkline = ({ values = [], width = 200, height = 48, stroke = '#3b82f6', fill = 'rgba(59,130,246,0.08)' }) => {
  if (!values || values.length === 0) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * (width - 8) + 4; // padding 4
    const y = height - 4 - ((v - min) / range) * (height - 8); // padding 4
    return `${x},${y}`;
  }).join(' ');

  // Area under the curve
  const firstX = 4;
  const lastX = width - 4;
  const areaPoints = `${firstX},${height - 4} ${points} ${lastX},${height - 4}`;

  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
      <polyline points={areaPoints} fill={fill} stroke="none" />
      <polyline points={points} fill="none" stroke={stroke} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
};

export default Sparkline;
