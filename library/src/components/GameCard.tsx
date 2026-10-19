import React from 'react';
import { Game } from '../types';
import { Film, Copy, Check } from 'lucide-react';

interface GameCardProps {
  game: Game;
  onSelect: (game: Game) => void;
}

export const GameCard: React.FC<GameCardProps> = ({ game, onSelect }) => {
  const [copied, setCopied] = React.useState(false);

  const handleCopyTitleId = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(game.titleId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="game-card" onClick={() => onSelect(game)}>
      <div className="game-card-thumb">
        {game.iconUrl ? (
          <img 
            src={game.iconUrl} 
            alt={game.title} 
            loading="lazy" 
            onError={(e) => {
              // Graceful fallback to stylish placeholder
              e.currentTarget.style.display = 'none';
            }}
          />
        ) : null}
        <div className="variant-count-badge">
          <Film size={12} style={{ display: 'inline', marginRight: 4, verticalAlign: -1 }} />
          {game.variants.length} {game.variants.length === 1 ? 'фон' : 'фона'}
        </div>
      </div>

      <div className="game-card-body">
        <h3 className="game-card-title">{game.title}</h3>
        <p className="game-card-publisher">{game.publisher || 'Nintendo Switch'}</p>

        <div className="game-card-footer">
          <span className="title-id-badge">{game.titleId}</span>
          <button 
            className="btn-secondary" 
            style={{ padding: '4px 8px', fontSize: '11px' }}
            onClick={handleCopyTitleId}
            title="Копировать Title ID"
          >
            {copied ? <Check size={12} color="#10B981" /> : <Copy size={12} />}
            <span>{copied ? 'Скопировано' : 'Copy ID'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
