import React, { useState, useEffect } from 'react';
import { Game, CoverStyle, Catalog } from './types';
import { CatalogService } from './services/catalogService';
import { Header } from './components/Header';
import { StatsBanner } from './components/StatsBanner';
import { SearchBar } from './components/SearchBar';
import { GameCard } from './components/GameCard';
import { GameModal } from './components/GameModal';
import { SubmitModal } from './components/SubmitModal';

export const App: React.FC = () => {
  const [catalog, setCatalog] = useState<Catalog>(CatalogService.getCatalog());
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStyle, setSelectedStyle] = useState<CoverStyle | 'All'>('All');
  const [selectedGame, setSelectedGame] = useState<Game | null>(null);
  const [isSubmitOpen, setIsSubmitOpen] = useState(false);

  useEffect(() => {
    CatalogService.loadCatalog().then((loaded) => {
      setCatalog(loaded);
    });
  }, []);

  const filteredGames = CatalogService.search(searchQuery, selectedStyle);

  return (
    <div>
      <Header onSubmitClick={() => setIsSubmitOpen(true)} />

      <main>
        <StatsBanner
          totalGames={catalog.totalGames || catalog.games.length}
          totalVariants={catalog.totalVariants || catalog.games.reduce((acc, g) => acc + g.variants.length, 0)}
        />

        <div className="container">
          <SearchBar
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            selectedStyle={selectedStyle}
            onStyleSelect={setSelectedStyle}
          />

          {filteredGames.length > 0 ? (
            <div className="games-grid">
              {filteredGames.map((game) => (
                <GameCard
                  key={game.titleId}
                  game={game}
                  onSelect={setSelectedGame}
                />
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '64px 0', color: '#9AA4B2' }}>
              <p style={{ fontSize: '18px', fontWeight: 600 }}>По вашему запросу ничего не найдено</p>
              <p style={{ fontSize: '14px', marginTop: 8 }}>
                Попробуйте изменить поисковую фразу или предложите видеофон для этой игры через кнопку выше.
              </p>
            </div>
          )}
        </div>
      </main>

      <footer style={{ borderTop: '1px solid #2D3540', padding: '32px 0', marginTop: 64, textAlign: 'center', color: '#687385', fontSize: '13px' }}>
        <div className="container">
          <p>H3H Backgrounds — открытая экосистема видеофонов для Nintendo Switch (4IFIR CFW).</p>
          <p style={{ marginTop: 6 }}>
            Все видеоматериалы принадлежат их законным правообладателям и предназначены для персонализации домашнего меню.
          </p>
        </div>
      </footer>

      {selectedGame && (
        <GameModal
          game={selectedGame}
          onClose={() => setSelectedGame(null)}
        />
      )}

      {isSubmitOpen && (
        <SubmitModal
          onClose={() => setIsSubmitOpen(false)}
        />
      )}
    </div>
  );
};

export default App;
