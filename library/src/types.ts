export type CoverStyle = 
  | 'Cinematic'
  | 'Gameplay'
  | 'Animated Art'
  | 'Minimal'
  | 'Dark'
  | 'Retro'
  | 'Music';

export interface Variant {
  id: string;
  name: string;
  style: CoverStyle;
  version: string;
  url: string;
  previewUrl: string;
  sizeBytes: number;
  sha256: string;
  durationSec: number;
  author: string;
  codec: string;
  width: number;
  height: number;
  fps: number;
  hasAudio?: boolean;
  notes?: string;
}

export interface Game {
  titleId: string;
  title: string;
  publisher?: string;
  iconUrl?: string;
  variants: Variant[];
}

export interface Catalog {
  schemaVersion: number;
  updatedAt: string;
  totalGames: number;
  totalVariants: number;
  games: Game[];
}
