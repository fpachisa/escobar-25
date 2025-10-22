import { useState } from 'react'
import TabNavigation from './components/TabNavigation'
import RTMGrid from './components/RTMGrid'

function App() {
  const [activeTab, setActiveTab] = useState('positions')
  
  // State to persist RTM data across tabs
  const [rtmData, setRtmData] = useState({
    positions: { data: [], lastUpdated: null },
    currencies: { data: [], lastUpdated: null },
    indices: { data: [], lastUpdated: null },
    commodities: { data: [], lastUpdated: null }
  })

  const updateRtmData = (category, data, lastUpdated) => {
    setRtmData(prev => ({
      ...prev,
      [category]: { data, lastUpdated }
    }))
  }

  const getCurrentData = () => rtmData[activeTab]

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f9fafb' }}>
      {/* Header */}
      <header className="app-header">
        <div className="app-header-inner">
          <div className="brand">
            <div className="brand-icon">📊</div>
            <div>
              <h1>RTM Monitor</h1>
              <div className="subtitle">Return-to-Mean Signals for OANDA instruments</div>
            </div>
          </div>
          <div className="status">
            {getCurrentData().lastUpdated ? (
              <div>
                <div className="label">Last Updated</div>
                <div className="value">
                  {new Date(getCurrentData().lastUpdated).toLocaleDateString()} {new Date(getCurrentData().lastUpdated).toLocaleTimeString()}
                </div>
              </div>
            ) : (
              <div className="value">Real-time RTM Analysis</div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container">
        {/* Tab Navigation */}
        <TabNavigation
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />

        {/* RTM Data Grid */}
        <RTMGrid 
          category={activeTab} 
          rtmData={getCurrentData()}
          onDataUpdate={updateRtmData}
        />
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <div className="app-footer-inner">Escobar by Farhat</div>
      </footer>
    </div>
  )
}

export default App
