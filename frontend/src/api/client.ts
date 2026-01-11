/**
 * API client for SRE Agent Dashboard
 */

const API_BASE = '/api/v1';

interface FetchOptions {
  method?: string;
  body?: any;
  headers?: Record<string, string>;
}

class ApiClient {
  private token: string | null = null;

  setToken(token: string) {
    this.token = token;
    localStorage.setItem('auth_token', token);
  }

  getToken(): string | null {
    if (!this.token) {
      this.token = localStorage.getItem('auth_token');
    }
    return this.token;
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem('auth_token');
  }

  private async fetch<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    const token = this.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: options.method || 'GET',
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });

    if (response.status === 401) {
      this.clearToken();
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || 'Request failed');
    }

    return response.json();
  }

  // Auth
  async login(email: string, password: string) {
    const result = await this.fetch<{
      access_token: string;
      refresh_token: string;
      expires_in: number;
    }>('/auth/login', {
      method: 'POST',
      body: { email, password },
    });
    this.setToken(result.access_token);
    localStorage.setItem('refresh_token', result.refresh_token);
    return result;
  }

  async logout() {
    await this.fetch('/auth/logout', { method: 'POST' }).catch(() => {});
    this.clearToken();
  }

  async getProfile() {
    return this.fetch<{
      id: string;
      email: string;
      name: string;
      role: string;
      permissions: string[];
    }>('/auth/me');
  }

  // Dashboard
  async getOverview() {
    return this.fetch<{
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
    }>('/dashboard/overview');
  }

  async getEvents(params: {
    status?: string;
    repository?: string;
    limit?: number;
    offset?: number;
  } = {}) {
    const query = new URLSearchParams();
    if (params.status) query.set('status', params.status);
    if (params.repository) query.set('repository', params.repository);
    if (params.limit) query.set('limit', params.limit.toString());
    if (params.offset) query.set('offset', params.offset.toString());

    const queryStr = query.toString();
    return this.fetch<{
      events: Array<{
        id: string;
        repository: string;
        branch: string;
        status: string;
        ci_provider: string;
        created_at: string;
        error_snippet?: string;
      }>;
      total: number;
      limit: number;
      offset: number;
      has_more: boolean;
    }>(`/dashboard/events${queryStr ? `?${queryStr}` : ''}`);
  }

  async getTrends(days: number = 7) {
    return this.fetch<Array<{
      date: string;
      count: number;
      success_count: number;
      failure_count: number;
    }>>(`/dashboard/trends?days=${days}`);
  }

  async getRepoStats() {
    return this.fetch<Array<{
      repository: string;
      total_events: number;
      failures: number;
      success_rate: number;
      last_event_at?: string;
    }>>('/dashboard/repos');
  }

  async getSystemHealth() {
    return this.fetch<{
      status: string;
      timestamp: string;
      components: Record<string, any>;
    }>('/dashboard/health');
  }

  // Notifications
  async listNotificationChannels() {
    return this.fetch<Array<{
      name: string;
      enabled: boolean;
      valid: boolean;
      type: string;
    }>>('/notifications/channels');
  }

  async testNotificationChannel(channelName: string) {
    return this.fetch(`/notifications/channels/${channelName}/test`, {
      method: 'POST',
    });
  }

  // Users
  async listUsers(params: { limit?: number; offset?: number; search?: string } = {}) {
    const query = new URLSearchParams();
    if (params.limit) query.set('limit', params.limit.toString());
    if (params.offset) query.set('offset', params.offset.toString());
    if (params.search) query.set('search', params.search);

    const queryStr = query.toString();
    return this.fetch<{
      users: Array<{
        id: string;
        email: string;
        name: string;
        role: string;
        is_active: boolean;
        created_at: string;
      }>;
      total: number;
    }>(`/users${queryStr ? `?${queryStr}` : ''}`);
  }

  // SSE Stream
  connectToEventStream(onMessage: (event: any) => void): EventSource {
    const token = this.getToken();
    const eventSource = new EventSource(
      `${API_BASE}/dashboard/stream${token ? `?token=${token}` : ''}`
    );

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (e) {
        console.error('Failed to parse SSE message', e);
      }
    };

    eventSource.onerror = () => {
      console.error('SSE connection error');
    };

    return eventSource;
  }
}

export const api = new ApiClient();
export default api;
