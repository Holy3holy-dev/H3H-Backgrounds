import React from 'react';
import { Search, X } from 'lucide-react';
import { CoverStyle } from '../types';

interface SearchBarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  selectedStyle: CoverStyle | 'All';
  onStyleSelect: (style: CoverStyle | 'All') => void;
}

const STYLES: (CoverStyle | 'All')[] = [
  'All',
  'Cinematic',
  'Gameplay',
  'Animated Art',
  'Minimal',
  'Dark',
  'Retro'
];

export const SearchBar: React.FC<SearchBarProps> = ({
  searchQuery,
  onSearchChange,
  selectedStyle,
  onStyleSelect,
}) => {
  return (
    <div className="search-container">
      <div className="search-input-wrapper">
        <Search className="search-icon" size={20} />
        <input
          type="text"
          className="search-input"
          placeholder="Поиск по названию игры или 16-значному Title ID (например: 01005CA01580E000)..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
        />
        {searchQuery && (
          <button 
            onClick={() => onSearchChange('')}
            style={{ position: 'absolute', right: 18, top: '50%', transform: 'translateY(-50%)', color: '#687385' }}
          >
            <X size={18} />
          </button>
        )}
      </div>

      <div className="filter-chips">
        {STYLES.map((style) => (
          <button
            key={style}
            className={`chip ${selectedStyle === style ? 'active' : ''}`}
            onClick={() => onStyleSelect(style)}
          >
            {style === 'All' ? 'Все категории' : style}
          </button>
        ))}
      </div>
    </div>
  );
};
