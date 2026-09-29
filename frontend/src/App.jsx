import { useMemo, useState } from 'react'
import './App.css'

const DEFAULT_PARAMS = {
  alpha: 0.15,
  contamination: 0.07,
  decay: 0.88,
  gain: 0.13,
}

const LEVEL_COLORS = {
  LOW: '#22c55e',
  MEDIUM: '#facc15',
  HIGH: '#fb923c',
  CRITICAL: '#ef4444',
}

const riskColor = (level) => LEVEL_COLORS[level] || '#3b82f6'

const buildSparklinePoints = (values) => {
  if (!values?.length) return ''
  const max = Math.max(...values, 100)
  const min = Math.min(...values, 0)
  const width = 220
  const height = 52

  return values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width
      const y = height - ((value - min) / (max - min || 1)) * (height - 10) - 5
      return `${x},${y}`
    })
    .join(' ')
}

const buildDayMarkers = (values, dates = []) => {
  if (!values?.length) return null
  const max = Math.max(...values, 100)
  const min = Math.min(...values, 0)
  const width = 220
  const height = 52

  return values.map((value, index) => {
    const x = (index / Math.max(values.length - 1, 1)) * width
    const y = height - ((value - min) / (max - min || 1)) * (height - 10) - 5
    const dateLabel = dates[index] ? new Date(dates[index]).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    }) : `Day ${index + 1}`

    return (
      <g key={`${dateLabel}-${index}`}>
        <circle cx={x} cy={y} r="2.2" fill="#f8fafc" stroke="#0f1728" strokeWidth="1.2">
          <title>{`${dateLabel}: ${value.toFixed(1)} risk score`}</title>
        </circle>
      </g>
    )
  })
}

const buildLinePath = (values, width, height, minValue, maxValue) => {
  if (!values?.length) return ''
  return values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width
      const y = height - ((value - minValue) / (maxValue - minValue || 1)) * (height - 24) - 12
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`
    })
    .join(' ')
}

const sampleChat = [
  {
    speaker: 'assistant',
    text: 'Upload a CSV or use the sample dataset to evaluate risk posture.',
  },
]

function App() {
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState('')
  const [result, setResult] = useState(null)
  const [selectedUser, setSelectedUser] = useState(null)
  const [chat, setChat] = useState(sampleChat)
  const [question, setQuestion] = useState('')
  const [identityPassword, setIdentityPassword] = useState('')
  const [identityResult, setIdentityResult] = useState(null)
  const [identityError, setIdentityError] = useState('')

  const summaryCards = useMemo(() => {
    if (!result?.summary) return []
    const summary = result.summary
    return [
      { label: 'Users analyzed', value: summary.users },
      { label: 'Activity records', value: summary.records },
      { label: 'Day span', value: summary.days },
      { label: 'Flagged users', value: summary.flagged },
    ]
  }, [result])

  const selected = result?.users?.find((user) => user.id === selectedUser) ?? result?.users?.[0] ?? null

  const handleParamChange = (event) => {
    const { name, value } = event.target
    setParams((previous) => ({ ...previous, [name]: Number(value) }))
  }

  const handleAnalyze = async (useSample = false) => {
    const formData = new FormData()
    Object.entries(params).forEach(([key, value]) => formData.append(key, String(value)))

    if (useSample) {
      formData.append('sample', '1')
    } else if (!file) {
      window.alert('Choose a CSV file first')
      return
    } else {
      formData.append('file', file)
    }

    setStatus('Analyzing…')

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        body: formData,
      })
      const payload = await response.json()

      if (!response.ok || payload.error) {
        throw new Error(payload.error || 'Analysis failed')
      }

      setResult(payload)
      setSelectedUser(payload.users?.[0]?.id ?? null)
      setStatus('')
      setChat((previous) => [
        ...previous,
        {
          speaker: 'assistant',
          text: `Analysis complete. ${payload.summary.flagged} users are in the HIGH or CRITICAL range.`,
        },
      ])
    } catch (error) {
      setStatus(`Error: ${error.message}`)
    }
  }

  const handleAsk = async () => {
    const trimmed = question.trim()
    if (!trimmed) return

    setChat((previous) => [...previous, { speaker: 'user', text: trimmed }])
    setQuestion('')

    try {
      const response = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: trimmed }),
      })
      const payload = await response.json()
      setChat((previous) => [...previous, { speaker: 'assistant', text: payload.answer }])
    } catch (error) {
      setChat((previous) => [...previous, { speaker: 'assistant', text: `Assistant error: ${error.message}` }])
    }
  }

  const handleIdentityLookup = async () => {
    if (!selectedUser) {
      setIdentityError('Select a flagged employee first.')
      return
    }

    try {
      const response = await fetch('/api/identity-name', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: selectedUser, password: identityPassword }),
      })
      const payload = await response.json()

      if (!response.ok || !payload.authorized) {
        setIdentityResult(null)
        setIdentityError(payload.message || 'Access denied.')
        return
      }

      setIdentityResult(payload)
      setIdentityError('')
    } catch (error) {
      setIdentityResult(null)
      setIdentityError(error.message)
    }
  }

  const distributionEntries = result?.distribution ? Object.entries(result.distribution) : []

  return (
    <main className="dashboard-shell">
      <header className="page-header">
        <div>
          <p className="eyebrow">Adaptive insider risk platform</p>
          <h1>Privacy-Preserving Insider Threat Dashboard</h1>
        </div>
      </header>

      <section className="panel">
        <div className="panel-header">
          <h2>1. Upload activity log data</h2>
        </div>
        <p className="muted">
          CSV with a user column, a date column and numeric behavioural features. The backend drops
          PII and pseudonymizes employee IDs before analysis.
        </p>

        <div className="input-grid">
          {Object.entries(DEFAULT_PARAMS).map(([key, value]) => (
            <label key={key} className="slider-field">
              <span>
                {key === 'alpha' && 'Adaptive learning rate α'}
                {key === 'contamination' && 'Expected anomaly rate'}
                {key === 'decay' && 'Risk decay'}
                {key === 'gain' && 'Risk gain'}
                <strong>{params[key].toFixed(key === 'alpha' || key === 'contamination' ? 2 : 2)}</strong>
              </span>
              <input
                name={key}
                type="range"
                min={key === 'alpha' ? 0.02 : key === 'contamination' ? 0.01 : key === 'decay' ? 0.5 : 0.02}
                max={key === 'alpha' ? 0.5 : key === 'contamination' ? 0.2 : key === 'decay' ? 0.99 : 0.4}
                step="0.01"
                value={params[key]}
                onChange={handleParamChange}
              />
            </label>
          ))}
        </div>

        <div className="upload-row">
          <input type="file" accept=".csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          <button type="button" onClick={() => handleAnalyze(false)}>Analyze uploaded data</button>
          <button type="button" className="secondary" onClick={() => handleAnalyze(true)}>
            Try with sample data
          </button>
          <span className="status-text">{status}</span>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>2. Summary</h2>
        </div>

        {result ? (
          <>
            <div className="stats-grid">
              {summaryCards.map((item) => (
                <div className="stat-card" key={item.label}>
                  <strong>{item.value}</strong>
                  <span>{item.label}</span>
                </div>
              ))}
            </div>
            <p className="meta-line">
              User column: {result.summary.user_col} · date column: {result.summary.date_col} · features:{' '}
              {result.summary.features.join(', ')} · PII fields dropped: {result.summary.dropped_pii.join(', ') || 'none'} ·{' '}
              {result.summary.explain_method} · {result.summary.seconds}s
            </p>
          </>
        ) : (
          <p className="placeholder">No data analysed yet.</p>
        )}
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>3. Are there anomalous users?</h2>
        </div>

        {result ? (
          <div className="risk-overview">
            <div className="trend-panel">
              <h3>Progressive risk over time</h3>

              <div className="legend-row">
                {result.users.slice(0, 8).map((user, index) => (
                  <div key={user.id} className="legend-item">
                    <span className="legend-dot" style={{ background: `hsl(${(index * 360) / 8} 75% 65%)` }} />
                    <span>{user.id}</span>
                  </div>
                ))}
              </div>

              <div className="chart-wrap">
                <svg viewBox="0 0 760 260" className="risk-chart" role="img" aria-label="Progressive risk over time">
                  <g>
                    {[0, 25, 50, 75, 100].map((tick) => {
                      const y = 220 - (tick / 100) * 180
                      return (
                        <g key={tick}>
                          <line x1="60" y1={y} x2="700" y2={y} className="grid-line" />
                          <text x="12" y={y + 4} className="axis-label">{tick}</text>
                        </g>
                      )
                    })}

                    {[0, 25, 50, 75, 100].map((tick) => {
                      const y = 220 - (tick / 100) * 180
                      return <line key={`threshold-${tick}`} x1="60" y1={y} x2="700" y2={y} className="risk-threshold" />
                    })}

                    {result.days.map((date, index) => {
                      const x = 60 + (index / Math.max(result.days.length - 1, 1)) * 640
                      if (index % Math.max(1, Math.ceil(result.days.length / 7)) === 0 || index === result.days.length - 1) {
                        return <text key={`${date}-${index}`} x={x} y="245" className="axis-date">{new Date(date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</text>
                      }
                      return null
                    })}

                    {result.users.slice(0, 8).map((user, index) => {
                      const points = user.trend
                        .map((value, pointIndex) => {
                          const x = 60 + (pointIndex / Math.max(user.trend.length - 1, 1)) * 640
                          const y = 220 - (value / 100) * 180
                          return `${x},${y}`
                        })
                        .join(' ')

                      return (
                        <g key={user.id}>
                          <polyline
                            points={points}
                            fill="none"
                            stroke={`hsl(${(index * 360) / 8} 75% 65%)`}
                            strokeWidth="2.2"
                            strokeLinejoin="round"
                            strokeLinecap="round"
                          />
                          {user.trend.map((value, pointIndex) => {
                            const x = 60 + (pointIndex / Math.max(user.trend.length - 1, 1)) * 640
                            const y = 220 - (value / 100) * 180
                            return (
                              <circle
                                key={`${user.id}-${pointIndex}`}
                                cx={x}
                                cy={y}
                                r={pointIndex === user.trend.length - 1 ? 3.6 : 1.5}
                                fill={`hsl(${(index * 360) / 8} 75% 65%)`}
                              />
                            )
                          })}
                        </g>
                      )
                    })}
                  </g>
                </svg>
              </div>
            </div>

            <div className="donut-panel">
              <h3>Risk-level distribution</h3>
              <div className="donut-wrap">
                <div
                  className="donut-ring"
                  style={{
                    background: `conic-gradient(${distributionEntries
                      .map(([label, count], index) => {
                        const total = distributionEntries.reduce((sum, [, value]) => sum + value, 0) || 1
                        const start = distributionEntries.slice(0, index).reduce((sum, [, v]) => sum + v, 0) / total * 100
                        const end = (distributionEntries.slice(0, index + 1).reduce((sum, [, v]) => sum + v, 0) / total) * 100
                        return `${LEVEL_COLORS[label]} ${start}% ${end}%`
                      })
                      .join(', ')})`,
                  }}
                >
                  <div className="donut-hole" />
                </div>
              </div>

              <div className="distribution-stack">
                {distributionEntries.map(([label, count]) => (
                  <div key={label} className="distribution-row">
                    <div className="distribution-label">
                      <span className="pill" style={{ background: LEVEL_COLORS[label] }}>
                        {label}
                      </span>
                    </div>
                    <strong>{count}</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <p className="placeholder">No risk profile available yet.</p>
        )}
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>4. Users ranked by progressive risk</h2>
        </div>

        {result ? (
          <div className="table-layout">
            <table>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Risk</th>
                  <th>Level</th>
                  <th>Peak</th>
                  <th>Anomalous days</th>
                </tr>
              </thead>
              <tbody>
                {result.users.slice(0, 15).map((user) => (
                  <tr
                    key={user.id}
                    className={selected?.id === user.id ? 'selected' : ''}
                    onClick={() => setSelectedUser(user.id)}
                  >
                    <td>{user.id}</td>
                    <td>{user.risk}</td>
                    <td>
                      <span className="pill" style={{ background: LEVEL_COLORS[user.level] }}>
                        {user.level}
                      </span>
                    </td>
                    <td>{user.peak}</td>
                    <td>{user.anomalous_days}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="factors-panel">
              <h3>{selected ? `Top contributing factors for ${selected.id}` : 'Top contributing factors'}</h3>
              {(selected?.factors?.length ? selected.factors : result.global_factors.slice(0, 4)).map((factor) => (
                <div key={factor.feature} className="factor-row">
                  <div className="factor-label-row">
                    <span>{factor.feature}</span>
                    <strong>{Math.round((factor.share || 0) * 100)}%</strong>
                  </div>
                  <div className="bar-track">
                    <div className="bar-fill" style={{ width: `${Math.max(6, (factor.share || 0) * 100)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="placeholder">No ranked users yet.</p>
        )}
      </section>

      <section className="panel security-panel">
        <div className="panel-header">
          <h2>5. Security review access</h2>
        </div>

        {result ? (
          <>
            <p className="muted">
              Reveal the real identity of a flagged employee only after authorized access is granted.
            </p>

            <div className="identity-lock-row">
              <div className="identity-field">
                <label>Selected employee</label>
                <input value={selectedUser ?? ''} readOnly />
              </div>
              <div className="identity-field">
                <label>Password</label>
                <input
                  type="password"
                  value={identityPassword}
                  onChange={(event) => setIdentityPassword(event.target.value)}
                  placeholder="Enter admin password"
                />
              </div>
              <button type="button" onClick={handleIdentityLookup}>Unlock identity</button>
            </div>

            <div className="identity-helper">Demo password: insider-secure-2026</div>

            {identityError && <div className="identity-warning">{identityError}</div>}

            {identityResult && (
              <div className="identity-box">
                <span className="identity-label">Authorized employee identity</span>
                <div className="identity-name">{identityResult.name}</div>
                <div className="identity-meta">User ID: {identityResult.user_id}</div>
              </div>
            )}
          </>
        ) : (
          <p className="placeholder">Run a risk analysis to unlock a monitored employee's identity.</p>
        )}
      </section>

      <section className="panel assistant-panel">
        <div className="panel-header">
          <h2>6. Risk Assistant</h2>
        </div>

        <div className="chat-box">
          {chat.map((entry, index) => (
            <p key={`${entry.speaker}-${index}`} className={entry.speaker === 'user' ? 'user-msg' : 'assistant-msg'}>
              <strong>{entry.speaker === 'user' ? 'You' : 'Assistant'}:</strong> {entry.text}
            </p>
          ))}
        </div>

        <div className="chat-input-row">
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Who is the highest-risk employee?"
            onKeyDown={(event) => {
              if (event.key === 'Enter') handleAsk()
            }}
          />
          <button type="button" onClick={handleAsk}>Ask</button>
        </div>
      </section>
    </main>
  )
}

export default App
