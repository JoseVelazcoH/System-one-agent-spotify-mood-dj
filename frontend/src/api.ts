import type {
  MeResponse,
  PlaylistRecommendResponse,
  PlaylistSummary,
  PrepareStatus,
  RecommendResponse,
} from "./types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function parseErrorDetail(response: Response): Promise<string> {
  const body = await response.json().catch(() => ({ detail: response.statusText }));
  return body.detail ?? response.statusText ?? "Request failed";
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorDetail(response));
  }

  return response.json();
}

export function loginUrl(): string {
  return `${API_BASE_URL}/auth/login`;
}

export async function fetchMe(): Promise<MeResponse> {
  return requestJson<MeResponse>("/auth/me");
}

export async function logout(): Promise<void> {
  await requestJson<{ logged_out: boolean }>("/auth/logout", { method: "POST" });
}

export async function fetchRecommendation(prompt: string): Promise<RecommendResponse> {
  return requestJson<RecommendResponse>("/recommend", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
}

export async function fetchPlaylists(): Promise<PlaylistSummary[]> {
  return requestJson<PlaylistSummary[]>("/playlists");
}

export async function preparePlaylist(playlistId: string): Promise<{ started: boolean }> {
  return requestJson<{ started: boolean }>(`/playlists/${playlistId}/prepare`, {
    method: "POST",
  });
}

export async function fetchPrepareStatus(playlistId: string): Promise<PrepareStatus> {
  return requestJson<PrepareStatus>(`/playlists/${playlistId}/status`);
}

export async function fetchPlaylistRecommendation(
  playlistId: string,
  prompt: string,
): Promise<PlaylistRecommendResponse> {
  return requestJson<PlaylistRecommendResponse>(`/playlists/${playlistId}/recommend`, {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
}
