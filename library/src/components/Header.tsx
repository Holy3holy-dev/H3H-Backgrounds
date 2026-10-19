import React from 'react';
import { Tv, PlusCircle, Github } from 'lucide-react';

interface HeaderProps {
  onSubmitClick: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onSubmitClick }) => {
  return (
    <header className="header">
      <div className="container header-inner">
        <div className="logo">
          <Tv size={24} color="#00E5FF" />
          <span className="logo-title">H3H Backgrounds</span>
          <span className="logo-badge">4IFIR</span>
        </div>

        <div className="header-actions">
          <button className="btn-secondary" onClick={onSubmitClick}>
            <PlusCircle size={16} />
            <span>Предложить видеофон</span>
          </button>

          <a 
            href="https://github.com/h3h-backgrounds" 
            target="_blank" 
            rel="noopener noreferrer" 
            className="btn-secondary"
            title="GitHub Repository"
          >
            <Github size={16} />
            <span>GitHub</span>
          </a>
        </div>
      </div>
    </header>
  );
};
