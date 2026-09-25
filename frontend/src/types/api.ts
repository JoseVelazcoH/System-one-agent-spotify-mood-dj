export interface Track {
  id: string;
  name: string;
  artist: string;
  album: string;
  energy: number;
  valence: number;
  tempo: number;
  danceability: number;
  acousticness: number;
  instrumentalness: number;
  cover_url: string | null;
  external_url: string | null;
  keep_probability: number | null;
}

export interface Profile {
  energy: number;
  valence: number;
  tempo: number;
  instrumentalness: number;
}

export interface Stage {
  name: string;
  profile: Profile;
  tracks: Track[];
}

export interface RecommendResponse {
  strategy: string;
  strategy_probabilities: Record<string, number>;
  stages: Stage[];
}

export interface MeResponse {
  logged_in: boolean;
}

export interface PlaylistSummary {
  id: string;
  name: string;
  image_url: string | null;
  track_count: number;
  snapshot_id: string;
}

export type PrepareState = "idle" | "running" | "done" | "error";

export interface PrepareStatus {
  state: PrepareState;
  total: number;
  processed: number;
  with_lyrics: number;
  instrumental: number;
  missing: number;
  error: string | null;
}

export interface PlaylistTrack {
  id: string;
  name: string;
  artist: string;
  album: string;
  cover_url: string | null;
  external_url: string | null;
  keep_probability: number;
  tone: number;
}

export interface PlaylistStage {
  name: string;
  tracks: PlaylistTrack[];
}

export interface Excluded {
  no_lyrics: number;
  instrumental: number;
}

export interface PlaylistRecommendResponse {
  strategy: string;
  signals: Record<string, number>;
  stages: PlaylistStage[];
  excluded: Excluded;
}
