import React from 'react';
import { Gamepad2, Film, CheckCircle2 } from 'lucide-react';

interface StatsBannerProps {
  totalGames: number;
  totalVariants: number;
}

export const StatsBanner: React.FC<StatsBannerProps> = ({ totalGames, totalVariants }) => {
  return (
    <section className="hero">
      <div className="container">
        <h1 className="hero-title">Библиотека видеофонов для 4IFIR</h1>
        <p className="hero-subtitle">
          Коллекция проверенных циклических MP4 фонов для меню Nintendo Switch. 
          Аппаратное декодирование Tegra X1, профиль H.264 720p и безопасная установка.
        </p>

        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Поддерживаемых игр</div>
            <div className="stat-value" style={{ color: '#FFFFFF' }}>
              <Gamepad2 size={24} style={{ display: 'inline', marginRight: 8, verticalAlign: -3, color: '#3B82F6' }} />
              {totalGames}
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-label">Доступных видеофонов</div>
            <div className="stat-value" style={{ color: '#00E5FF' }}>
              <Film size={24} style={{ display: 'inline', marginRight: 8, verticalAlign: -3, color: '#00E5FF' }} />
              {totalVariants}
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-label">Стандарт 4IFIR</div>
            <div className="stat-value" style={{ color: '#10B981', fontSize: '24px', paddingTop: '6px' }}>
              <CheckCircle2 size={24} style={{ display: 'inline', marginRight: 8, verticalAlign: -3, color: '#10B981' }} />
              H.264 / 720p / 30fps
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
