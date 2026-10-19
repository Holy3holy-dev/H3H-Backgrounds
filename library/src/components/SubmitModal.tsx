import React, { useState } from 'react';
import { X, Copy, Check, ExternalLink } from 'lucide-react';

interface SubmitModalProps {
  onClose: () => void;
}

const TITLE_ID_REGEX = /^0100[0-9A-Fa-f]{12}$/;

export const SubmitModal: React.FC<SubmitModalProps> = ({ onClose }) => {
  const [title, setTitle] = useState('');
  const [titleId, setTitleId] = useState('');
  const [variantName, setVariantName] = useState('');
  const [style, setStyle] = useState('Cinematic');
  const [author, setAuthor] = useState('');
  const [videoUrl, setVideoUrl] = useState('');
  const [copiedSnippet, setCopiedSnippet] = useState(false);

  const isValidTitleId = TITLE_ID_REGEX.test(titleId.trim());
  const isValidUrl = videoUrl.trim().startsWith('https://');

  const generatedJson = JSON.stringify({
    title: title.trim() || 'Game Title',
    titleId: titleId.trim().toUpperCase() || '0100XXXXXXXXXXXXXXXX',
    variant: {
      id: variantName.toLowerCase().replace(/[^a-z0-9]/g, '-').slice(0, 32) || 'variant-slug',
      name: variantName.trim() || 'Variant Name',
      style: style,
      version: '1.0',
      url: videoUrl.trim() || 'https://...',
      previewUrl: videoUrl.trim() || 'https://...',
      author: author.trim() || 'Contributor',
      codec: 'h264',
      width: 1280,
      height: 720,
      fps: 30.0,
      hasAudio: false
    }
  }, null, 2);

  const handleCopy = () => {
    navigator.clipboard.writeText(generatedJson);
    setCopiedSnippet(true);
    setTimeout(() => setCopiedSnippet(false), 2000);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 720 }}>
        <div className="modal-header">
          <div>
            <h2 style={{ fontSize: '22px', fontWeight: 800 }}>Предложить видеофон в каталог</h2>
            <p style={{ color: '#9AA4B2', fontSize: '13px', marginTop: 4 }}>
              Все материалы проходят автоматическую проверку FFprobe и модерацию перед публикацией.
            </p>
          </div>
          <button className="btn-secondary" onClick={onClose} style={{ padding: 8 }}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          {/* Workflow stages */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 24 }}>
            <div style={{ background: '#252B35', padding: 12, borderRadius: 8, fontSize: '12px' }}>
              <div style={{ color: '#00E5FF', fontWeight: 700, marginBottom: 2 }}>1. Заявка</div>
              <div style={{ color: '#9AA4B2' }}>Создание заявки с метаданными и ссылкой на MP4</div>
            </div>
            <div style={{ background: '#252B35', padding: 12, borderRadius: 8, fontSize: '12px' }}>
              <div style={{ color: '#F59E0B', fontWeight: 700, marginBottom: 2 }}>2. CI Тесты</div>
              <div style={{ color: '#9AA4B2' }}>Проверка кодека H.264, профиля и SHA-256</div>
            </div>
            <div style={{ background: '#252B35', padding: 12, borderRadius: 8, fontSize: '12px' }}>
              <div style={{ color: '#10B981', fontWeight: 700, marginBottom: 2 }}>3. Публикация</div>
              <div style={{ color: '#9AA4B2' }}>Включение в каталог и доступ в Switch Homebrew</div>
            </div>
          </div>

          {/* Form */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ fontSize: '13px', color: '#9AA4B2', display: 'block', marginBottom: 4 }}>Название игры:</label>
              <input
                type="text"
                className="search-input"
                style={{ padding: '10px 14px' }}
                placeholder="Например: The Legend of Zelda: Tears of the Kingdom"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <label style={{ fontSize: '13px', color: '#9AA4B2' }}>16-значный Title ID игры:</label>
                {titleId && (
                  <span style={{ fontSize: '12px', color: isValidTitleId ? '#10B981' : '#EF4444' }}>
                    {isValidTitleId ? 'Корректный Title ID' : 'Должен быть 16 шестн. символов (начиная с 0100)'}
                  </span>
                )}
              </div>
              <input
                type="text"
                className="search-input"
                style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)' }}
                placeholder="01005CA01580E000"
                value={titleId}
                onChange={(e) => setTitleId(e.target.value)}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <div>
                <label style={{ fontSize: '13px', color: '#9AA4B2', display: 'block', marginBottom: 4 }}>Название варианта:</label>
                <input
                  type="text"
                  className="search-input"
                  style={{ padding: '10px 14px' }}
                  placeholder="Intro Animation / Streets Fight"
                  value={variantName}
                  onChange={(e) => setVariantName(e.target.value)}
                />
              </div>

              <div>
                <label style={{ fontSize: '13px', color: '#9AA4B2', display: 'block', marginBottom: 4 }}>Стиль / Категория:</label>
                <select
                  className="search-input"
                  style={{ padding: '10px 14px', background: '#1B1F26' }}
                  value={style}
                  onChange={(e) => setStyle(e.target.value)}
                >
                  <option value="Cinematic">Cinematic</option>
                  <option value="Gameplay">Gameplay</option>
                  <option value="Animated Art">Animated Art</option>
                  <option value="Minimal">Minimal</option>
                  <option value="Dark">Dark</option>
                  <option value="Retro">Retro</option>
                  <option value="Music">Music</option>
                </select>
              </div>
            </div>

            <div>
              <label style={{ fontSize: '13px', color: '#9AA4B2', display: 'block', marginBottom: 4 }}>Автор / Никнейм:</label>
              <input
                type="text"
                className="search-input"
                style={{ padding: '10px 14px' }}
                placeholder="Ваш никнейм для указания авторства"
                value={author}
                onChange={(e) => setAuthor(e.target.value)}
              />
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <label style={{ fontSize: '13px', color: '#9AA4B2' }}>Прямая HTTPS ссылка на MP4:</label>
                {videoUrl && (
                  <span style={{ fontSize: '12px', color: isValidUrl ? '#10B981' : '#EF4444' }}>
                    {isValidUrl ? 'HTTPS URL корректен' : 'Ссылка должна начинаться с https://'}
                  </span>
                )}
              </div>
              <input
                type="url"
                className="search-input"
                style={{ padding: '10px 14px' }}
                placeholder="https://github.com/.../video.mp4"
                value={videoUrl}
                onChange={(e) => setVideoUrl(e.target.value)}
              />
            </div>
          </div>

          {/* Generated Snippet */}
          <div style={{ marginTop: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <span style={{ fontSize: '13px', color: '#9AA4B2' }}>Сгенерированные метаданные:</span>
              <button className="btn-secondary" style={{ padding: '4px 10px', fontSize: '12px' }} onClick={handleCopy}>
                {copiedSnippet ? <Check size={14} color="#10B981" /> : <Copy size={14} />}
                <span>{copiedSnippet ? 'Скопировано' : 'Копировать JSON'}</span>
              </button>
            </div>
            <pre style={{
              background: '#121418',
              padding: 12,
              borderRadius: 6,
              fontSize: '12px',
              fontFamily: 'var(--font-mono)',
              overflowX: 'auto',
              border: '1px solid #2D3540'
            }}>
              {generatedJson}
            </pre>
          </div>

          {/* Action button */}
          <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
            <button className="btn-secondary" onClick={onClose}>
              Отмена
            </button>
            <a
              href={`https://github.com/h3h-backgrounds/catalog/issues/new?title=Submission:+${encodeURIComponent(title || 'New+Cover')}&body=${encodeURIComponent("```json\n" + generatedJson + "\n```")}`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary"
              style={{ textDecoration: 'none' }}
            >
              <ExternalLink size={16} />
              <span>Отправить через GitHub Issues</span>
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};
