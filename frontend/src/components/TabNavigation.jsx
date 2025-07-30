import React from 'react';

const TabNavigation = ({ activeTab, onTabChange }) => {
  const tabs = [
    { id: 'positions', label: 'Positions', icon: '📋' },
    { id: 'currencies', label: 'CCY', icon: '💱' },
    { id: 'indices', label: 'Indices', icon: '📈' },
    { id: 'commodities', label: 'Commodities', icon: '🛢️' }
  ];

  return (
    <div style={{ display: 'flex', justifyContent: 'center', gap: '0.25rem', backgroundColor: '#f3f4f6', padding: '0.25rem', borderRadius: '0.5rem', marginBottom: '1.5rem' }}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={`tab-button ${activeTab === tab.id ? 'tab-button-active' : 'tab-button-inactive'}`}
          style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
        >
          <span style={{ fontSize: '1.125rem' }}>{tab.icon}</span>
          <span>{tab.label}</span>
        </button>
      ))}
    </div>
  );
};

export default TabNavigation;