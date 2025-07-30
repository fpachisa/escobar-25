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
      <header style={{ backgroundColor: 'white', boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1)', borderBottom: '1px solid #e5e7eb' }}>
        <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '0 1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '4rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div style={{ fontSize: '1.5rem' }}>📊</div>
              <h1 style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#111827' }}>RTM Monitor</h1>
            </div>
            <div style={{ fontSize: '0.875rem', color: '#6b7280', textAlign: 'right' }}>
              {getCurrentData().lastUpdated ? (
                <div>
                  <div>Last Updated:</div>
                  <div style={{ fontWeight: '500' }}>
                    {new Date(getCurrentData().lastUpdated).toLocaleDateString()} {new Date(getCurrentData().lastUpdated).toLocaleTimeString()}
                  </div>
                </div>
              ) : (
                <div>Real-time RTM Analysis</div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main style={{ maxWidth: '80rem', margin: '0 auto', padding: '2rem 1rem' }}>
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
      <footer style={{ backgroundColor: 'white', borderTop: '1px solid #e5e7eb', marginTop: '4rem' }}>
        <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1rem' }}>
          <div style={{ textAlign: 'center', fontSize: '0.875rem', color: '#6b7280' }}>
            Escobar by Farhat
          </div>
        </div>
      </footer>
    </div>
  )
}

export default App
