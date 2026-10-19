import React, { useState } from 'react';
import { Game } from '../types';
import { CatalogService } from '../services/catalogService';
import { X, Download, ShieldCheck, Copy, Check, Info } from 'lucide-react';

interface GameModalProps {
  game: Game;
  onClose: () => void;
}

export const GameModal: React.FC<GameModalProps> = ({ game, onClose }) => {
  const [selectedVariantIdx, setSelectedVariantIdx] = useState(0);
  const [copiedHash, setCopiedHash] = useState(false);

  const variant = game.variants[selectedVariantIdx] || game.variants[0];

  const handleCopyHash = () => {
    if (variant?.sha256) {
      navigator.clipboard.writeText(variant.sha256);
      setCopiedHash(true);
      setTimeout(() => setCopiedHash(false), 2000);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2 style={{ fontSize: '24px', fontWeight: 800 }}>{game.title}</h2>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 6 }}>
              <span className="code-snippet">{game.titleId}</span>
              <span style={{ color: '#9AA4B2', fontSize: '13px' }}>{game.publisher || 'Nintendo Switch'}</span>
            </div>
          </div>
          <button className="btn-secondary" onClick={onClose} style={{ padding: 8 }}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          {/* Variant Selector Chips */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
            {game.variants.map((v, idx) => (
              <button
                key={v.id}
                className={`chip ${selectedVariantIdx === idx ? 'active' : ''}`}
                onClick={() => setSelectedVariantIdx(idx)}
              >
                {v.name} ({v.style})
              </button>
            ))}
          </div>

          {variant && (
            <div className="variant-card">
              <div className="variant-card-header">
                <div>
                  <div className="variant-name">{variant.name}</div>
                  <div style={{ color: '#9AA4B2', fontSize: '13px', marginTop: 2 }}>
                    Автор: <strong style={{ color: '#FFFFFF' }}>{variant.author}</strong> | Версия: {variant.version}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#10B981', fontSize: '13px', fontWeight: 600 }}>
                  <ShieldCheck size={18} />
                  <span>Проверено для 4IFIR</span>
                </div>
              </div>

              {/* Video Player */}
              <div style={{ width: '100%', height: 320, background: '#121418', borderRadius: 8, overflow: 'hidden', marginBottom: 16 }}>
                <video
                  key={variant.url}
                  src={variant.url}
                  poster={variant.previewUrl}
                  controls
                  loop
                  muted
                  playsInline
                  style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                />
              </div>

              {/* Specs Grid */}
              <div className="variant-meta-row">
                <div>Разрешение: <strong style={{ color: '#FFF' }}>{variant.width}x{variant.height}</strong></div>
                <div>Частота: <strong style={{ color: '#FFF' }}>{variant.fps} fps</strong></div>
                <div>Кодек: <strong style={{ color: '#FFF' }}>{variant.codec.toUpperCase()}</strong></div>
                <div>Длительность: <strong style={{ color: '#FFF' }}>{CatalogService.formatDuration(variant.durationSec)}</strong></div>
                <div>Размер: <strong style={{ color: '#FFF' }}>{CatalogService.formatBytes(variant.sizeBytes)}</strong></div>
              </div>

              {variant.notes && (
                <div style={{ fontSize: '13px', color: '#9AA4B2', marginBottom: 16, background: '#1B1F26', padding: '10px 14px', borderRadius: 6 }}>
                  <Info size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: -2 }} />
                  {variant.notes}
                </div>
              )}

              {/* Action Buttons */}
              <div className="variant-actions">
                <a 
                  href={variant.url} 
                  download={`${game.titleId}.mp4`}
                  className="btn-primary"
                  style={{ textDecoration: 'none' }}
                >
                  <Download size={16} />
                  <span>Скачать MP4 ({game.titleId}.mp4)</span>
                </a>

                <button className="btn-secondary" onClick={handleCopyHash}>
                  {copiedHash ? <Check size={16} color="#10B981" /> : <Copy size={16} />}
                  <span>{copiedHash ? 'Хэш скопирован' : 'Копировать SHA-256'}</span>
                </button>
              </div>

              {/* Manual Installation Instructions */}
              <div className="instructions-banner">
                <strong>Ручная установка на Nintendo Switch (4IFIR):</strong>
                <ol style={{ paddingLeft: 20, marginTop: 8, lineHeight: 1.6 }}>
                  <li>Скачайте видеофайл выше.</li>
                  <li>Убедитесь, что имя файла строго соответствует Title ID: <span className="code-snippet">{game.titleId}.mp4</span></li>
                  <li>Поместите файл на MicroSD карту в папку: <span className="code-snippet">sdmc:/recordings/covers/</span></li>
                  <li>Перезапустите меню Switch или обновите экран 4IFIR.</li>
                </ol>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
