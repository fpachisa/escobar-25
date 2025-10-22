import React from 'react';

const TabNavigation = ({ activeTab, onTabChange }) => {
  const tabs = [
    { id: 'positions', label: 'Positions', icon: '📋' },
    { id: 'currencies', label: 'CCY', icon: '💱' },
    { id: 'indices', label: 'Indices', icon: '📈' },
    { id: 'commodities', label: 'Commodities', icon: '🛢️' }
  ];

  return (
    <div className="tabbar">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={`tab-button ${activeTab === tab.id ? 'tab-button-active' : 'tab-button-inactive'}`}
        >
          <span className="tab-icon">{tab.icon}</span>
          <span className="tab-label">{tab.label}</span>
        </button>
      ))}
    </div>
  );
};

export default TabNavigation;
