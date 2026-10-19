import { Catalog, Game, CoverStyle } from '../types';
import fallbackCatalogData from '../../../catalog/data/catalog.json';

export class CatalogService {
  private static catalog: Catalog = fallbackCatalogData as Catalog;

  public static async loadCatalog(): Promise<Catalog> {
    try {
      const response = await fetch('./catalog.json');
      if (response.ok) {
        const data = await response.json();
        if (data.schemaVersion === 1) {
          this.catalog = data as Catalog;
        }
      }
    } catch {
      // Fallback gracefully to bundled catalog
      console.info('Using bundled catalog data');
    }
    return this.catalog;
  }

  public static getCatalog(): Catalog {
    return this.catalog;
  }

  public static search(query: string, style?: CoverStyle | 'All'): Game[] {
    const q = query.trim().toLowerCase();
    
    return this.catalog.games.filter(game => {
      // Title match or Title ID match
      const matchesQuery = !q || 
        game.title.toLowerCase().includes(q) || 
        game.titleId.toLowerCase().includes(q) ||
        (game.publisher && game.publisher.toLowerCase().includes(q));

      if (!matchesQuery) return false;

      // Style filter
      if (!style || style === 'All') return true;

      return game.variants.some(v => v.style === style);
    });
  }

  public static formatBytes(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  public static formatDuration(sec: number): string {
    const mins = Math.floor(sec / 60);
    const remainingSecs = Math.floor(sec % 60);
    if (mins > 0) {
      return `${mins}:${remainingSecs.toString().padStart(2, '0')}`;
    }
    return `${sec.toFixed(0)}s`;
  }
}
