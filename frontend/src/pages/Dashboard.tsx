import { useState, useEffect, useCallback } from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import api from '../api/client';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { format } from 'date-fns';
import FailureDetails from './FailureDetails';

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  permissions: string[];
}

interface DashboardProps {
  user: User;
  onLogout: () => void;
}

interface Overview {
  stats: {
    total_events: number;
    failures_24h: number;
    fixes_generated_24h: number;
    fixes_approved_24h: number;
    success_rate_7d: number;
    avg_fix_time_minutes: number;
  };
  recent_failures: Array<{
    id: string;
    repository: string;
    branch: string;
    status: string;
    ci_provider: string;
    created_at: string;
    error_snippet?: string;
  }>;
  pending_approvals: number;
  active_fixes: number;
}

export default function Dashboard({ user, onLogout }: DashboardProps) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [trends, setTrends] = useState<any[]>([]);
  const [repoStats, setRepoStats] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [sseConnected, setSseConnected] = useState(false);
  const location = useLocation();

  const fetchData = useCallback(async () => {
    try {
      const [overviewData, trendsData, repoData] = await Promise.all([
        api.getOverview(),
        api.getTrends(7),
        api.getRepoStats(),
      ]);
      setOverview(overviewData);
      setTrends(trendsData);
      setRepoStats(repoData);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();

    // Connect to SSE for real-time updates
    const eventSource = api.connectToEventStream((event) => {
      if (event.type === 'connected') {
        setSseConnected(true);
      } else if (event.type === 'heartbeat') {
        // Keep alive
      } else {
        // New event - refresh data
        fetchData();
      }
    });

    return () => {
      eventSource.close();
      setSseConnected(false);
    };
  }, [fetchData]);

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner"></div>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <nav className="sidebar">
        <div className="sidebar-header">
          <h1>🔧 SRE Agent</h1>
          <span className={`connection-status ${sseConnected ? 'connected' : ''}`}>
            {sseConnected ? '● Live' : '○ Offline'}
          </span>
        </div>

        <ul className="nav-links">
          <li className={location.pathname === '/' ? 'active' : ''}>
            <Link to="/">📊 Dashboard</Link>
          </li>
          <li className={location.pathname === '/events' ? 'active' : ''}>
            <Link to="/events">📋 Events</Link>
          </li>
          <li className={location.pathname === '/approvals' ? 'active' : ''}>
            <Link to="/approvals">✅ Approvals</Link>
          </li>
          <li className={location.pathname === '/notifications' ? 'active' : ''}>
            <Link to="/notifications">🔔 Notifications</Link>
          </li>
          {user.permissions.includes('view_users') && (
            <li className={location.pathname === '/users' ? 'active' : ''}>
              <Link to="/users">👥 Users</Link>
            </li>
          )}
        </ul>

        <div className="sidebar-footer">
          <div className="user-info">
            <span className="user-name">{user.name}</span>
            <span className="user-role">{user.role}</span>
          </div>
          <button onClick={onLogout} className="logout-btn">Logout</button>
        </div>
      </nav>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<OverviewPage overview={overview} trends={trends} repoStats={repoStats} />} />
          <Route path="/events" element={<EventsPage />} />
          <Route path="/failures/:failureId" element={<FailureDetails />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/users" element={<UsersPage />} />
        </Routes>
      </main>
    </div>
  );
}

// Overview Page
function OverviewPage({ overview, trends, repoStats }: {
  overview: Overview | null;
  trends: any[];
  repoStats: any[];
}) {
  if (!overview) return null;

  const { stats, recent_failures } = overview;

  return (
    <div className="page overview-page">
      <h2>Dashboard Overview</h2>

      {/* Stats Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <span className="stat-value">{stats.total_events}</span>
          <span className="stat-label">Total Events</span>
        </div>
        <div className="stat-card warning">
          <span className="stat-value">{stats.failures_24h}</span>
          <span className="stat-label">Failures (24h)</span>
        </div>
        <div className="stat-card success">
          <span className="stat-value">{stats.fixes_generated_24h}</span>
          <span className="stat-label">Fixes Generated</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{stats.success_rate_7d}%</span>
          <span className="stat-label">Success Rate (7d)</span>
        </div>
      </div>

      {/* Charts Row */}
      <div className="charts-row">
        <div className="chart-card">
          <h3>Event Trends (7 Days)</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={trends}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="date" stroke="#888" />
              <YAxis stroke="#888" />
              <Tooltip
                contentStyle={{ background: '#1a1a2e', border: '1px solid #333' }}
              />
              <Line type="monotone" dataKey="count" stroke="#8b5cf6" strokeWidth={2} />
              <Line type="monotone" dataKey="failure_count" stroke="#ef4444" strokeWidth={2} />
              <Line type="monotone" dataKey="success_count" stroke="#22c55e" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h3>Top Repositories</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={repoStats.slice(0, 5)} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis type="number" stroke="#888" />
              <YAxis dataKey="repository" type="category" stroke="#888" width={100} />
              <Tooltip
                contentStyle={{ background: '#1a1a2e', border: '1px solid #333' }}
              />
              <Bar dataKey="total_events" fill="#8b5cf6" />
              <Bar dataKey="failures" fill="#ef4444" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent Failures Table */}
      <div className="table-card">
        <h3>Recent Failures</h3>
        <table>
          <thead>
            <tr>
              <th>Repository</th>
              <th>Branch</th>
              <th>CI Provider</th>
              <th>Time</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {recent_failures.map((event) => (
              <tr key={event.id}>
                <td><Link to={`/failures/${event.id}`} className="link">{event.repository}</Link></td>
                <td>{event.branch}</td>
                <td>{event.ci_provider}</td>
                <td>{format(new Date(event.created_at), 'MMM d, HH:mm')}</td>
                <td>
                  <span className={`status-badge ${event.status}`}>
                    {event.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Events Page
function EventsPage() {
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const limit = 20;

  useEffect(() => {
    const fetchEvents = async () => {
      setLoading(true);
      const data = await api.getEvents({ limit, offset: page * limit });
      setEvents(data.events);
      setTotal(data.total);
      setLoading(false);
    };
    fetchEvents();
  }, [page]);

  return (
    <div className="page events-page">
      <h2>Pipeline Events</h2>

      <div className="table-card">
        {loading ? (
          <div className="loading-spinner"></div>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>Repository</th>
                  <th>Branch</th>
                  <th>CI Provider</th>
                  <th>Time</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td><Link to={`/failures/${event.id}`} className="link">{event.repository}</Link></td>
                    <td>{event.branch}</td>
                    <td>{event.ci_provider}</td>
                    <td>{format(new Date(event.created_at), 'MMM d, HH:mm')}</td>
                    <td>
                      <span className={`status-badge ${event.status}`}>
                        {event.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="pagination">
              <button
                disabled={page === 0}
                onClick={() => setPage(p => p - 1)}
              >
                Previous
              </button>
              <span>Page {page + 1} of {Math.ceil(total / limit)}</span>
              <button
                disabled={(page + 1) * limit >= total}
                onClick={() => setPage(p => p + 1)}
              >
                Next
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// Approvals Page
function ApprovalsPage() {
  return (
    <div className="page">
      <h2>Pending Approvals</h2>
      <div className="empty-state">
        <span className="empty-icon">✅</span>
        <p>No pending approvals</p>
      </div>
    </div>
  );
}

// Notifications Page
function NotificationsPage() {
  const [channels, setChannels] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchChannels = async () => {
      const data = await api.listNotificationChannels();
      setChannels(data);
      setLoading(false);
    };
    fetchChannels();
  }, []);

  const testChannel = async (name: string) => {
    try {
      await api.testNotificationChannel(name);
      alert('Test notification sent!');
    } catch (err: any) {
      alert('Failed to send test: ' + err.message);
    }
  };

  return (
    <div className="page">
      <h2>Notification Channels</h2>

      <div className="channels-grid">
        {loading ? (
          <div className="loading-spinner"></div>
        ) : channels.length === 0 ? (
          <div className="empty-state">
            <span className="empty-icon">🔔</span>
            <p>No notification channels configured</p>
          </div>
        ) : (
          channels.map((channel) => (
            <div key={channel.name} className="channel-card">
              <div className="channel-header">
                <span className="channel-name">{channel.name}</span>
                <span className={`channel-status ${channel.enabled ? 'enabled' : 'disabled'}`}>
                  {channel.enabled ? 'Enabled' : 'Disabled'}
                </span>
              </div>
              <div className="channel-type">{channel.type}</div>
              <div className="channel-valid">
                {channel.valid ? '✓ Valid config' : '✗ Invalid config'}
              </div>
              <button
                onClick={() => testChannel(channel.name)}
                className="test-btn"
              >
                Send Test
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// Users Page
function UsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    const fetchUsers = async () => {
      setLoading(true);
      const data = await api.listUsers({ search: search || undefined });
      setUsers(data.users);
      setLoading(false);
    };
    fetchUsers();
  }, [search]);

  return (
    <div className="page">
      <h2>User Management</h2>

      <div className="search-bar">
        <input
          type="text"
          placeholder="Search users..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="table-card">
        {loading ? (
          <div className="loading-spinner"></div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.name}</td>
                  <td>{user.email}</td>
                  <td>
                    <span className={`role-badge ${user.role}`}>
                      {user.role}
                    </span>
                  </td>
                  <td>
                    <span className={user.is_active ? 'active' : 'inactive'}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>
                    <button className="action-btn">Edit</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
